"""Fresh authentication grants for passkey management, shared by REST and GraphQL."""

import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from graphql_relay import from_global_id
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.users.exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure
from apps.users.services.otp import validate_otp
from apps.sso.models import PasskeyManagementGrant, UserPasskey, WebAuthnChallenge
from apps.sso.exceptions import PasskeyReauthenticationError
from .webauthn import WebAuthnService


GRANT_TTL = timedelta(minutes=5)


def action_target(user, data):
    if not isinstance(data, dict):
        raise ValidationError("Invalid authentication request")
    action = data.get("action")
    if not isinstance(action, str) or action not in {"register", "delete"}:
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


def issue_grant(grant):
    token = secrets.token_urlsafe(32)
    grant.token_hash = hashlib.sha256(token.encode()).hexdigest()
    grant.expires_at = timezone.now() + GRANT_TTL
    grant.save(update_fields=["token_hash", "expires_at"])
    return token


def password_grant(user, data):
    action, passkey = action_target(user, data)
    password = data.get("password")
    if not user.is_active:
        raise PermissionDenied("Fresh authentication failed")
    if not isinstance(password, str) or not user.check_password(password):
        raise PasskeyReauthenticationError('incorrect_password')
    if user.otp_enabled:
        if not isinstance(data.get("otpToken", ""), str):
            raise PermissionDenied("Fresh authentication failed")
        try:
            validate_otp(user, data.get("otpToken", ""))
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
    if grant is None or not user.is_active:
        raise PermissionDenied("Fresh authentication required")
    if challenge is not None and (
        grant.registration_challenge is None or grant.registration_challenge.challenge != challenge
    ):
        raise PermissionDenied("Fresh authentication required")
    return grant


def consume_grant(grant):
    grant.used_at = timezone.now()
    grant.save(update_fields=["used_at"])
