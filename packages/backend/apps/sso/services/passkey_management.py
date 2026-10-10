"""Fresh authentication grants for passkey management, shared by REST and GraphQL."""

import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from graphql_relay import from_global_id
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.users.exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure, PasswordBudgetExceeded
from apps.users.services import password_budget
from apps.users.services.otp import validate_otp
from apps.users.services.credentials import credential_version
from apps.sso.models import PasskeyManagementGrant, UserPasskey, WebAuthnChallenge
from apps.sso.exceptions import PasskeyReauthenticationError
from .webauthn import WebAuthnService


GRANT_TTL = timedelta(minutes=5)

MANAGEMENT_ACTIONS = {"register", "delete", "otp_setup", "otp_disable", "password_set", "account_delete"}


def action_target(user, data):
    if not isinstance(data, dict):
        raise ValidationError("Invalid authentication request")
    action = data.get("action")
    if not isinstance(action, str) or action not in MANAGEMENT_ACTIONS:
        raise ValidationError("Invalid passkey management action")
    passkey = None
    if action == "delete":
        identifier = data.get("passkeyId")
        if not isinstance(identifier, str):
            raise ValidationError("Passkey is required")
        type_name, pk = from_global_id(identifier)
        identifier = pk if type_name == "PasskeyType" else identifier
        passkey = UserPasskey.objects.filter(pk=identifier, user=user, is_active=True).first()
        if passkey is None:
            raise ValidationError("Passkey not found")
    return action, passkey


def user_can_reauthenticate(user):
    """Whether the user has a way to prove freshness other than their current OTP
    code - a usable password, or an active passkey."""
    return user.has_usable_password() or UserPasskey.objects.filter(user=user, is_active=True).exists()


def issue_grant(grant):
    token = secrets.token_urlsafe(32)
    grant.token_hash = hashlib.sha256(token.encode()).hexdigest()
    grant.credential_version = credential_version(grant.user)
    grant.expires_at = timezone.now() + GRANT_TTL
    grant.save(update_fields=["token_hash", "expires_at", "credential_version"])
    return token


def validate_password_proof(user, data):
    password = data.get("password")
    if not user.is_active:
        raise PermissionDenied("Fresh authentication failed")
    if not isinstance(password, str):
        raise PasskeyReauthenticationError('incorrect_password')
    try:
        # Shares the same account-wide budget as login (E05) - repeatedly guessing the
        # password here is exactly as much a brute-force avenue as the login form itself.
        correct = password_budget.check_password(user.email, lambda: user.check_password(password))
    except PasswordBudgetExceeded:
        raise PasskeyReauthenticationError('password_locked')
    if not correct:
        raise PasskeyReauthenticationError('incorrect_password')
    if user.otp_enabled and data.get("action") != "account_delete":
        if not isinstance(data.get("otpToken", ""), str):
            raise PermissionDenied("Fresh authentication failed")
        try:
            validate_otp(user, data.get("otpToken", ""))
        except OTPAttemptLimitExceeded:
            raise PasskeyReauthenticationError('otp_locked')
        except OTPVerificationFailure:
            raise PasskeyReauthenticationError('incorrect_otp')


def password_grant(user, data):
    action, passkey = action_target(user, data)
    validate_password_proof(user, data)
    grant = PasskeyManagementGrant.objects.create(
        user=user, action=action, passkey=passkey, expires_at=timezone.now() + GRANT_TTL
    )
    return issue_grant(grant)


def otp_only_grant(user, data):
    """Fresh-auth proof for otp_setup (replace)/otp_disable/password_set when the account has
    neither a usable password nor an active passkey - the current OTP code is the only factor
    such an account can produce (e.g. a Google-only account that enabled 2FA, now setting its
    first password). Never valid for register/delete (passkey management already requires a
    password path to exist) and never valid when the account *can* use a stronger path instead."""
    action, passkey = action_target(user, data)
    if action not in {"otp_setup", "otp_disable", "password_set"} or user_can_reauthenticate(user):
        raise PermissionDenied("Fresh authentication failed")
    if not user.otp_enabled or not user.otp_verified:
        raise PermissionDenied("Fresh authentication failed")
    otp_token = data.get("otpToken")
    if not isinstance(otp_token, str):
        raise PermissionDenied("Fresh authentication failed")
    try:
        validate_otp(user, otp_token)
    except OTPAttemptLimitExceeded:
        raise PasskeyReauthenticationError('otp_locked')
    except OTPVerificationFailure:
        raise PasskeyReauthenticationError('incorrect_otp')
    grant = PasskeyManagementGrant.objects.create(
        user=user, action=action, passkey=passkey, expires_at=timezone.now() + GRANT_TTL
    )
    return issue_grant(grant)


@transaction.atomic
def passkey_options(user, data):
    action, passkey = action_target(user, data)
    if not UserPasskey.objects.filter(user=user, is_active=True).exists():
        raise ValidationError("An existing passkey is required")
    options, challenge = WebAuthnService(user).create_authentication_options()
    record = WebAuthnChallenge.objects.get(challenge=challenge)
    record.challenge_type = "passkey-management"
    record.save(update_fields=["challenge_type"])
    PasskeyManagementGrant.objects.create(
        user=user, action=action, passkey=passkey, authentication_challenge=record, expires_at=record.expires_at
    )
    return options


def passkey_grant(user, data, ip_address):
    error = None
    with transaction.atomic():
        grant = (
            PasskeyManagementGrant.objects.select_for_update()
            .filter(user=user, authentication_challenge__challenge=data.get("challenge"), token_hash__isnull=True)
            .first()
        )
        if grant is None or grant.expires_at <= timezone.now() or not user.is_active:
            raise PermissionDenied("Fresh authentication failed")
        # Lock the credential as well as the challenge while checking counters and issuing proof.
        WebAuthnChallenge.objects.select_for_update().get(pk=grant.authentication_challenge_id)
        UserPasskey.objects.select_for_update().filter(user=user, credential_id=data.get("credentialId")).first()
        try:
            WebAuthnService(user).verify_authentication(
                challenge=data.get("challenge"),
                credential_id=data.get("credentialId"),
                authenticator_data=data.get("authenticatorData"),
                client_data_json=data.get("clientDataJSON"),
                signature=data.get("signature"),
                user_handle=data.get("userHandle"),
                ip_address=ip_address,
                challenge_type="passkey-management",
            )
        except ValueError as exc:
            # Commit failure audit records and clone deactivation before rejecting the proof.
            error = exc
        else:
            token = issue_grant(grant)
    if error is not None:
        raise error
    return token


def require_grant(request, user, action, passkey=None, challenge=None):
    """Must be called inside the transaction that performs the protected change."""
    token = request.headers.get("X-Passkey-Authorization", "")
    if not isinstance(token, str) or not token or len(token) > 128:
        raise PermissionDenied("Fresh authentication required")
    grant = (
        PasskeyManagementGrant.objects.select_for_update()
        .filter(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user=user,
            action=action,
            passkey=passkey,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if grant is None or not user.is_active or grant.credential_version != credential_version(user):
        raise PermissionDenied("Fresh authentication required")
    if challenge is not None and (
        grant.registration_challenge is None or grant.registration_challenge.challenge != challenge
    ):
        raise PermissionDenied("Fresh authentication required")
    return grant


def consume_grant(grant):
    grant.used_at = timezone.now()
    grant.save(update_fields=["used_at"])
