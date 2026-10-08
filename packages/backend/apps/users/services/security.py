"""Account security records and retryable notification delivery."""

import functools
import ipaddress
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.sso.models import SSOAuditLog
from apps.sso.services.sessions import parse_user_agent
from apps.users.models import SecurityEmailOutbox, User
from apps.users import tokens
from common.emails import deliver_email_message

logger = logging.getLogger(__name__)

AUTH_EVENTS = (
    'auth_signup',
    'auth_email_confirmation',
    'auth_password_login',
    'auth_otp_challenge',
    'auth_otp_verification',
    'auth_password_reset_request',
    'auth_password_reset',
    'auth_password_change',
    'auth_otp_management',
)


def email_identifier(email):
    return salted_hmac('authentication-audit-email', email.strip().casefold(), algorithm='sha256').hexdigest()


def client_ip(request):
    """Only accept forwarded chains from configured trusted proxy networks."""
    if request is None:
        return None
    request = getattr(request, '_request', request)
    try:
        peer = ipaddress.ip_address(request.META.get('REMOTE_ADDR', ''))
        networks = [ipaddress.ip_network(value) for value in settings.AUTH_AUDIT_TRUSTED_PROXIES]
        if any(peer in network for network in networks):
            chain = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')
            for raw in reversed(chain):
                if not raw.strip():
                    continue
                peer = ipaddress.ip_address(raw.strip())
                if not any(peer in network for network in networks):
                    break
        return str(peer)
    except ValueError:
        return None


def record(event, *, request=None, user=None, email='', success=True, outcome='completed', method='', actor=None):
    request = getattr(request, '_request', request)
    if request is not None:
        if not getattr(request, '_security_correlation_id', None):
            request._security_correlation_id = str(uuid.uuid4())
        correlation = request._security_correlation_id
    else:
        correlation = str(uuid.uuid4())
    metadata = {'correlation_id': correlation, 'outcome': outcome, 'auth_method': method}
    if user:
        metadata['account_id'] = str(user.pk)
    if actor:
        metadata['actor_id'] = str(actor.pk)
    elif request is not None and getattr(getattr(request, 'user', None), 'is_authenticated', False):
        metadata['actor_id'] = str(request.user.pk)
    if 'actor_id' not in metadata:
        verified_actor = success and event in (
            'auth_password_login',
            'auth_otp_challenge',
            'auth_otp_verification',
            'auth_password_change',
            'auth_password_reset',
            'auth_email_confirmation',
            'auth_otp_management',
        )
        metadata['actor_id'] = str(user.pk) if user and verified_actor else 'anonymous'
    if email:
        metadata['email_identifier'] = email_identifier(email)
    return SSOAuditLog.log_event(
        event,
        user=user,
        success=success,
        ip_address=client_ip(request),
        user_agent=str(parse_user_agent(request.META.get('HTTP_USER_AGENT', '')[:512])) if request else '',
        metadata=metadata,
    )


def audit_failures(event):
    """Run outside mutation transactions so rejected operations retain a record."""

    def decorate(function):
        @functools.wraps(function)
        def wrapped(cls, root, info, **data):
            try:
                return function(cls, root, info, **data)
            except Exception:
                request = info.context._request
                if getattr(request, '_otp_failure_audited', False):
                    request._otp_failure_audited = False
                    raise
                account = getattr(request, 'user', None)
                if not getattr(account, 'is_authenticated', False):
                    account = None
                if account is None and data.get('email'):
                    account = User.objects.filter(email__iexact=data['email'].strip()).first()
                record(
                    event, request=request, user=account, email=data.get('email', ''), success=False, outcome='rejected'
                )
                raise

        return wrapped

    return decorate


def enqueue_email(user, kind, *, event=None):
    """Persist in the caller's transaction. Broker availability is irrelevant."""
    return SecurityEmailOutbox.objects.create(
        user=user,
        recipient=user.email,
        kind=kind,
        language=getattr(getattr(user, 'profile', None), 'language', 'en') or 'en',
        event_id=str(event.pk) if event else str(uuid.uuid4()),
    )


def process_outbox():
    """Bound each sweep; row locks serialize concurrent workers and retries."""
    ids = list(
        SecurityEmailOutbox.objects.filter(
            sent_at__isnull=True,
            failed_at__isnull=True,
            cancelled_at__isnull=True,
            next_attempt_at__lte=timezone.now(),
        ).values_list('pk', flat=True)[:100]
    )
    for pk in ids:
        with transaction.atomic():
            row = (
                SecurityEmailOutbox.objects.select_for_update(skip_locked=True)
                .filter(
                    pk=pk,
                    sent_at__isnull=True,
                    failed_at__isnull=True,
                    cancelled_at__isnull=True,
                )
                .first()
            )
            if row is None or row.next_attempt_at > timezone.now():
                continue
            row.attempts += 1
            try:
                if deliver_email(row):
                    row.sent_at = timezone.now()
                else:
                    row.cancelled_at = timezone.now()
                row.last_error = ''
            except Exception:
                # Never persist renderer output, provider errors, or token-bearing payloads.
                row.last_error = 'delivery_failed'
                if row.attempts >= 8:
                    row.failed_at = timezone.now()
                    logger.error('Security email retries exhausted: outbox_id=%s', row.pk)
                row.next_attempt_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2**row.attempts))
            row.save(
                update_fields=['attempts', 'sent_at', 'failed_at', 'cancelled_at', 'last_error', 'next_attempt_at']
            )


def deliver_email(row):
    if row.user_id is None:
        return False  # Deleted accounts must not receive fresh account proofs.
    user = User.objects.get(pk=row.user_id)
    if user.email.casefold() != row.recipient.casefold():
        return False
    if not user.is_active and row.kind in ('ACCOUNT_ACTIVATION', 'SIGNUP_GUIDANCE', 'PASSWORD_RESET'):
        return False
    data = {}
    if row.kind == 'ACCOUNT_ACTIVATION':
        if user.is_confirmed:
            return False
        data = {'user_id': str(user.pk), 'token': tokens.account_activation_token.make_token(user)}
    elif row.kind == 'PASSWORD_RESET':
        data = {'user_id': str(user.pk), 'token': tokens.password_reset_token.make_token(user)}
    result = deliver_email_message(row.recipient, row.kind, data, row.language)
    if not result or not result.get('sent_emails_count'):
        raise RuntimeError('delivery_failed')
    return True
