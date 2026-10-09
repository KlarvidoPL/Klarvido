"""Atomic reset-email admission; public outcomes never disclose a recipient's state."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_ratelimit.core import is_ratelimited

from common.ratelimiting import get_rate_limit, RateLimitCategory
from apps.users.models import ResetEmailLimit
from .security import client_ip, email_identifier

logger = logging.getLogger(__name__)


def admit_reset(request, email, *, deliverable):
    request = getattr(request, '_request', request)
    try:
        if request is None:
            return 'limiter_unavailable'
        limited = is_ratelimited(
            request=request,
            group='auth.password_reset',
            key=lambda group, req: client_ip(req) or 'unknown',
            rate=get_rate_limit(RateLimitCategory.AUTH_PASSWORD_RESET),
            increment=True,
        )
        if limited:
            return 'ip_limited'
        with transaction.atomic():
            # All admissions use the same lock order; updates commit with the outbox write.
            global_limit, _ = ResetEmailLimit.objects.get_or_create(key='global')
            global_limit = ResetEmailLimit.objects.select_for_update().get(pk=global_limit.pk)
            key = email_identifier(email)
            recipient, _ = ResetEmailLimit.objects.get_or_create(key=key)
            recipient = ResetEmailLimit.objects.select_for_update().get(pk=key)
            now = timezone.now()
            if recipient.window_started_at.date() != now.date():
                recipient.window_started_at = now
                recipient.count = 0
            if recipient.last_queued_at and now - recipient.last_queued_at < timedelta(
                seconds=settings.RESET_EMAIL_COOLDOWN_SECONDS
            ):
                return 'recipient_cooldown'
            if recipient.count >= settings.RESET_EMAIL_DAILY_LIMIT:
                return 'recipient_limited'
            if now - global_limit.window_started_at >= timedelta(hours=1):
                global_limit.window_started_at = now
                global_limit.count = 0
            if global_limit.count >= settings.RESET_EMAIL_GLOBAL_HOURLY_LIMIT:
                return 'global_limited'
            recipient.last_queued_at = now
            recipient.count += 1
            recipient.save()
            if deliverable:
                global_limit.count += 1
                global_limit.save()
            return 'accepted'
    except Exception:
        # Never bypass limits or leak cache/database errors to the public response.
        logger.error('Password reset email admission unavailable')
        return 'limiter_unavailable'
