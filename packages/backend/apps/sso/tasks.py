"""
Celery tasks for session management.
"""

import logging

from celery import shared_task

from .services import SessionService

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def cleanup_expired_sessions():
    """
    Delete expired sessions (scheduled daily in CELERY_BEAT_SCHEDULE).

    They're already hidden from "Active sessions" once expired; this just stops the rows piling up.
    """
    count = SessionService.cleanup_expired_sessions()
    logger.info("Deleted %s expired sessions", count)
    return count
