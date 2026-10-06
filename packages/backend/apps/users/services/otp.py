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
    otp_base32 = pyotp.random_base32()
    otp_auth_url = pyotp.totp.TOTP(otp_base32).provisioning_uri(
        name=user.email.lower(), issuer_name=settings.OTP_AUTH_ISSUER_NAME
    )

    user.otp_auth_url = otp_auth_url
    user.otp_base32 = otp_base32
    user.save(update_fields=["otp_auth_url", "otp_base32"])

    return otp_base32, otp_auth_url


def verify_otp(user: User, otp_token: str):
    _check_otp(user, otp_token, setup=True)


def validate_otp(user: User, otp_token: str):
    _check_otp(user, otp_token, setup=False)


def _check_otp(user: User, otp_token: str, *, setup: bool):
    # Persist counters before raising: rolling back failures would allow unlimited guesses.
    # The row lock serializes guesses across processes, IPs and newly issued login tokens.
    error = None
    with transaction.atomic():
        account = User.objects.select_for_update().get(pk=user.pk)
        now = timezone.now()
        if account.otp_locked_until and account.otp_locked_until > now:
            error = OTPAttemptLimitExceeded("Too many incorrect codes. Try again in 15 minutes.")
        elif not setup and not account.otp_verified:
            error = OTPVerificationFailure(OTPErrors.OTP_NOT_VERIFIED.value)
        else:
            if account.otp_locked_until:
                account.otp_failed_attempts = 0
                account.otp_locked_until = None
            valid = pyotp.TOTP(account.otp_base32).verify(otp_token, valid_window=0 if setup else 1)
            fields = ["otp_failed_attempts", "otp_locked_until"]
            if valid:
                account.otp_failed_attempts = 0
                if setup:
                    account.otp_enabled = account.otp_verified = True
                    fields += ["otp_enabled", "otp_verified"]
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

    user.save(update_fields=["otp_enabled", "otp_verified", "otp_base32", "otp_auth_url"])
