"""
Celery tasks for session management.
"""

import logging

from celery import shared_task
from django.utils import timezone
from .models import PasskeyManagementGrant, WebAuthnChallenge

from .services import SessionService

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def cleanup_expired_sessions():
    """
    Delete expired sessions (scheduled daily in CELERY_BEAT_SCHEDULE).

    They're already hidden from "Active sessions" once expired; this just stops the rows piling up.
    """
    PasskeyManagementGrant.objects.filter(expires_at__lt=timezone.now()).delete()
    count = SessionService.cleanup_expired_sessions()
    logger.info("Deleted %s expired sessions", count)
    return count


@shared_task(ignore_result=True)
def cleanup_passkey_challenges():
    """Bound cleanup work; expired challenges and their dependent grants are unusable."""
    now = timezone.now()
    # Bounded batches also work on stateless containers and all deployment targets.
    count = 0
    for _ in range(10):
        ids = list(WebAuthnChallenge.objects.filter(expires_at__lt=now).values_list('pk', flat=True)[:1000])
        if not ids:
            break
        WebAuthnChallenge.objects.filter(pk__in=ids).delete()
        count += len(ids)
    for _ in range(10):
        ids = list(PasskeyManagementGrant.objects.filter(expires_at__lt=now).values_list('pk', flat=True)[:1000])
        if not ids:
            break
        PasskeyManagementGrant.objects.filter(pk__in=ids).delete()
    logger.info("Deleted %s expired passkey challenges", count)
    return count
