"""Browser-bound provider linking after a fresh login to an existing account."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from social_django.models import UserSocialAuth

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog
from apps.users import notifications
from apps.users.models import PendingSocialAccountLink, User, LanguageChoices
from apps.users.services.credentials import credential_version
from apps.users.utils import reset_auth_cookie

LINK_COOKIE = 'pending_social_link'
LINK_TTL = timedelta(minutes=5)


def login_redirect(request, code):
    locale = getattr(request, 'session', {}).get('locale', 'en')
    if locale not in LanguageChoices.values:
        locale = 'en'
    response = HttpResponseRedirect(f'{settings.WEB_APP_URL}/{locale}/auth/login?social={code}')
    response['Cache-Control'] = 'no-store'
    reset_auth_cookie(response)
    response.delete_cookie(settings.OTP_AUTH_TOKEN_COOKIE, samesite=settings.COOKIE_SAMESITE)
    response.delete_cookie(LINK_COOKIE, samesite=settings.COOKIE_SAMESITE)
    return response


@transaction.atomic
def begin_link(backend, user, uid):
    request = backend.strategy.request
    account = User.objects.select_for_update().get(pk=user.pk)
    if not account.is_active:
        return login_redirect(request, 'failed')
    if not account.is_confirmed:
        # No automatic reclaim: the account may genuinely belong to this person
        # (they just never clicked the confirmation link) and could already hold
        # real data/org memberships. Point them at the normal verify-then-link
        # path, and leave a trail in case they instead contact support claiming
        # the account isn't theirs - see apps.users.services.account_reclaim.
        SSOAuditLog.log_event(
            SSOAuditEventType.SSO_LOGIN_FAILED,
            user=account,
            description='Social login blocked: matching account is not yet confirmed',
            metadata={'provider': backend.name, 'reason': 'unconfirmed_account'},
            success=False,
        )
        return login_redirect(request, 'unconfirmed_account')
    if not isinstance(uid, str) or not uid or len(uid) > 255:
        return login_redirect(request, 'failed')
    # Only the newest confirmation is usable. Keep storage bounded per account.
    PendingSocialAccountLink.objects.filter(user=account).delete()
    token = secrets.token_urlsafe(32)
    PendingSocialAccountLink.objects.create(
        user=account,
        provider=backend.name,
        uid=uid,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        credential_version=credential_version(account),
        expires_at=timezone.now() + LINK_TTL,
    )
    response = login_redirect(request, 'link_required')
    response.set_cookie(
        LINK_COOKIE,
        token,
        max_age=int(LINK_TTL.total_seconds()),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )
    return response


def _link_cookie(request):
    # Most callers pass a real Django/DRF request, where .COOKIES is always a dict.
    # Some internal call paths (e.g. the GraphQL test context) use a lighter stand-in
    # that only carries it when a test opts in, so this must not assume it's present -
    # every caller below is a routine login with no pending link to complete, and must
    # not be broken by that absence.
    return getattr(request, 'COOKIES', {}).get(LINK_COOKIE)


@transaction.atomic
def complete_link(request, user):
    """Call only after full fresh password/OTP or verified-UV passkey authentication.

    The caller's session issuance must share this transaction so storage failures
    cannot link a provider while reporting a failed login.
    """
    token = _link_cookie(request)
    if not token:
        return False
    if not isinstance(token, str) or len(token) > 128:
        raise PermissionDenied('Account confirmation failed. Please sign in again.')
    account = User.objects.select_for_update().get(pk=user.pk)
    pending = (
        PendingSocialAccountLink.objects.select_for_update()
        .filter(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user=account,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if (
        pending is None
        or not account.is_active
        or not account.is_confirmed
        or pending.credential_version != credential_version(account)
    ):
        raise PermissionDenied('Account confirmation failed. Please sign in again.')
    try:
        with transaction.atomic():
            association, _ = UserSocialAuth.objects.get_or_create(
                provider=pending.provider,
                uid=pending.uid,
                defaults={'user': account},
            )
    except IntegrityError:
        raise PermissionDenied('Account confirmation failed. Please sign in again.') from None
    if association.user_id != account.pk:
        raise PermissionDenied('Account confirmation failed. Please sign in again.')
    pending.used_at = timezone.now()
    pending.save(update_fields=['used_at'])
    SSOAuditLog.log_event(
        SSOAuditEventType.SSO_LOGIN_SUCCESS,
        user=account,
        description='Social identity linked after fresh authentication',
        metadata={'provider': pending.provider, 'action': 'account_linked', 'association_id': str(association.pk)},
    )
    notifications.send_after_commit(
        notifications.SocialAccountLinkedEmail(user=account, data={'provider': pending.provider})
    )
    request.delete_cookies = [*getattr(request, 'delete_cookies', []), LINK_COOKIE]
    return True


def cancel_link(request):
    token = _link_cookie(request) or ''
    if isinstance(token, str) and token and len(token) <= 128:
        PendingSocialAccountLink.objects.filter(token_hash=hashlib.sha256(token.encode()).hexdigest()).delete()
