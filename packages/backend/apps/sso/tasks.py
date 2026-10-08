"""
Celery tasks for session management.
"""

import logging

from celery import shared_task
from django.utils import timezone
from .models import PasskeyManagementGrant

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
