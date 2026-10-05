"""
Celery tasks for session management.
"""

import logging

from celery import shared_task

from .models import TenantDomain
from .constants import SSODomainStatus
from .services import SessionService
from .services.domain_verification import dns_check_bypassed, recheck_domain

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


@shared_task(ignore_result=True)
def recheck_verified_domains():
    """
    Re-check the DNS record of every verified SSO domain (scheduled daily in CELERY_BEAT_SCHEDULE).

    A domain whose record disappears for several checks lapses, and its SSO connections are deactivated.
    Skipped entirely when the development DNS bypass is on, so local data is never lapsed.
    """
    if dns_check_bypassed():
        return 0

    checked = 0
    domains = TenantDomain.objects.select_related("tenant").filter(status=SSODomainStatus.VERIFIED)
    for tenant_domain in domains.iterator():
        recheck_domain(tenant_domain)
        checked += 1
    logger.info("Re-checked %s verified SSO domains", checked)
    return checked
