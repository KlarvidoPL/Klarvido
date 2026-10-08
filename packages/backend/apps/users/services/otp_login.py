"""Server-side, one-use pending OTP login proof.

Issued once a user has produced a real first factor (password or completed social
login) for an OTP-enabled account, and consumed exactly once - atomically with the
session it authorizes - by ValidateOTPMutation. See PendingOTPLogin for why this
replaces the previous self-signed JWT approach.
"""

import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.users.models import PendingOTPLogin, User
from apps.users.services.credentials import credential_version

OTP_LOGIN_TTL = settings.OTP_AUTH_TOKEN_LIFETIME_MINUTES


@transaction.atomic
def begin_otp_login(user, auth_method):
    """Create the pending proof and return the raw (unhashed) cookie token."""
    account = User.objects.select_for_update().get(pk=user.pk)
    # Only the newest pending login is usable - keeps storage bounded per account
    # and means starting a fresh login invalidates any earlier abandoned attempt.
    PendingOTPLogin.objects.filter(user=account).delete()
    token = secrets.token_urlsafe(32)
    PendingOTPLogin.objects.create(
        user=account,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        auth_method=auth_method,
        credential_version=credential_version(account),
        expires_at=timezone.now() + OTP_LOGIN_TTL,
    )
    return token


def _lookup(queryset, raw_token):
    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 128:
        return None
    pending = (
        queryset.select_related('user')
        .filter(
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if pending is None or pending.credential_version != credential_version(pending.user):
        return None
    return pending


def find_pending_login(raw_token):
    """Look up (without consuming or locking) a usable pending proof.

    Returns None if the token is missing/malformed, expired, already used, matches
    no account at all, or was issued against credentials that have since changed
    (password reset/change, OTP enabled/disabled/replaced, deactivation) - any of
    which must invalidate it.
    """
    return _lookup(PendingOTPLogin.objects, raw_token)


@transaction.atomic
def consume_pending_login(raw_token):
    """Re-validate and atomically mark the pending proof used. Must be called inside
    the same transaction that issues the resulting session/tokens, and only after
    the OTP code itself has already been checked.

    Returns the consumed row, or None if it can no longer be used (including by a
    concurrent request that consumed it first).
    """
    pending = _lookup(PendingOTPLogin.objects.select_for_update(), raw_token)
    if pending is None:
        return None
    pending.used_at = timezone.now()
    pending.save(update_fields=['used_at'])
    return pending
