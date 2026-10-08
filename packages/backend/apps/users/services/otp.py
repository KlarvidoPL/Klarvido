import hashlib
from typing import Tuple
from datetime import timedelta

import pyotp
from django.db import transaction
from django.utils import timezone
from apps.users.exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure
from apps.users.constants import OTPErrors
from apps.users.models import User
from config import settings

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def generate_otp(user: User) -> Tuple[str, str]:
    """Create a new secret and stage it as "pending" without touching the active
    factor - callers must still call verify_otp() with a code from it before it can
    ever be used to log in or replace the current secret."""
    otp_base32 = pyotp.random_base32()
    otp_auth_url = pyotp.totp.TOTP(otp_base32).provisioning_uri(
        name=user.email.lower(), issuer_name=settings.OTP_AUTH_ISSUER_NAME
    )

    user.otp_pending_base32 = otp_base32
    user.otp_pending_auth_url = otp_auth_url
    user.save(update_fields=["otp_pending_base32", "otp_pending_auth_url"])

    return otp_base32, otp_auth_url


def verify_otp(user: User, otp_token: str):
    """Confirm a code from the pending secret and, only on success, promote it to
    the active factor."""
    _check_otp(user, otp_token, setup=True)


def validate_otp(user: User, otp_token: str):
    _check_otp(user, otp_token, setup=False)


def _code_hash(otp_token) -> str:
    return hashlib.sha256(otp_token.encode()).hexdigest() if isinstance(otp_token, str) else ""


def _check_otp(user: User, otp_token: str, *, setup: bool):
    # Persist counters before raising: rolling back failures would allow unlimited guesses.
    # The row lock serializes guesses across processes, IPs and newly issued login tokens.
    error = None
    with transaction.atomic():
        account = User.objects.select_for_update().get(pk=user.pk)
        now = timezone.now()
        secret = account.otp_pending_base32 if setup else account.otp_base32
        if account.otp_locked_until and account.otp_locked_until > now:
            error = OTPAttemptLimitExceeded("Too many incorrect codes. Try again in 15 minutes.")
        elif not setup and not account.otp_verified:
            error = OTPVerificationFailure(OTPErrors.OTP_NOT_VERIFIED.value)
        elif setup and not secret:
            error = OTPVerificationFailure(OTPErrors.VERIFICATION_TOKEN_INVALID.value)
        else:
            if account.otp_locked_until:
                account.otp_failed_attempts = 0
                account.otp_locked_until = None
            code_hash = _code_hash(otp_token)
            # NIST SP 800-63B: each valid OTP is accepted at most once. A login code
            # that was just accepted cannot be submitted again - e.g. a captured
            # request or an already-consumed pending-login cookie being replayed -
            # even though it would otherwise still be inside its validity window.
            already_used = not setup and code_hash and code_hash == account.otp_last_used_code_hash
            valid = (
                bool(secret)
                and not already_used
                and pyotp.TOTP(secret).verify(otp_token, valid_window=0 if setup else 1)
            )
            fields = ["otp_failed_attempts", "otp_locked_until"]
            if valid:
                account.otp_failed_attempts = 0
                if setup:
                    account.otp_base32 = account.otp_pending_base32
                    account.otp_auth_url = account.otp_pending_auth_url
                    account.otp_pending_base32 = ""
                    account.otp_pending_auth_url = ""
                    account.otp_enabled = account.otp_verified = True
                    # A brand new secret has no accepted-code history of its own.
                    account.otp_last_used_code_hash = ""
                    fields += [
                        "otp_base32",
                        "otp_auth_url",
                        "otp_pending_base32",
                        "otp_pending_auth_url",
                        "otp_enabled",
                        "otp_verified",
                        "otp_last_used_code_hash",
                    ]
                else:
                    account.otp_last_used_code_hash = code_hash
                    fields += ["otp_last_used_code_hash"]
            else:
                account.otp_failed_attempts += 1
                if account.otp_failed_attempts >= MAX_FAILED_ATTEMPTS:
                    account.otp_locked_until = now + LOCKOUT_DURATION
                    error = OTPAttemptLimitExceeded("Too many incorrect codes. Try again in 15 minutes.")
                else:
                    error = OTPVerificationFailure(OTPErrors.VERIFICATION_TOKEN_INVALID.value)
            account.save(update_fields=fields)
            # Preserve the service's existing contract for callers holding this user instance.
            for field in fields:
                setattr(user, field, getattr(account, field))
    if error:
        raise error


def disable_otp(user: User):
    user.otp_enabled = False
    user.otp_verified = False
    user.otp_base32 = ""
    user.otp_auth_url = ""
    user.otp_pending_base32 = ""
    user.otp_pending_auth_url = ""
    user.otp_last_used_code_hash = ""

    user.save(
        update_fields=[
            "otp_enabled",
            "otp_verified",
            "otp_base32",
            "otp_auth_url",
            "otp_pending_base32",
            "otp_pending_auth_url",
            "otp_last_used_code_hash",
        ]
    )
