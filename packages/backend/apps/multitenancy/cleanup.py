"""Transactional cleanup outbox. Remote I/O never runs in the deletion transaction."""

import logging
import uuid
from datetime import timedelta

from celery import current_app
from django.db import transaction
from django.utils import timezone

from apps.backup.encryption import get_backup_encryption_service
from apps.demo.models import DocumentDemoItem
from common.storages import get_exports_storage, delete_storage_prefix, organization_document_prefix
from .models import ResourceCleanup, Tenant

logger = logging.getLogger(__name__)
LEASE_DURATION = timedelta(minutes=10)


class CleanupLeaseLost(Exception):
    """A recovered worker now owns this cleanup job."""


def schedule_organization_prefix_cleanup(organization_id):
    # Validation also ensures that an identifier cannot escape its directory.
    document_prefix = organization_document_prefix(organization_id)
    for prefix in (f'tenant_backups/{organization_id}/', f'action_logs/{organization_id}/'):
        schedule_resource_cleanup(
            ResourceCleanup.ResourceType.EXPORT_PREFIX, organization_id=organization_id, resource_path=prefix
        )
    schedule_resource_cleanup(
        ResourceCleanup.ResourceType.DOCUMENT_PREFIX, organization_id=organization_id, resource_path=document_prefix
    )


def clean_organization_prefix(cleanup, token):
    document_prefix = organization_document_prefix(cleanup.organization_id)
    if cleanup.resource_type == ResourceCleanup.ResourceType.EXPORT_PREFIX:
        allowed_prefixes = (f'tenant_backups/{cleanup.organization_id}/', f'action_logs/{cleanup.organization_id}/')
        storage = get_exports_storage()
    else:
        allowed_prefixes = (document_prefix,)
        storage = DocumentDemoItem._meta.get_field('file').storage
    if cleanup.resource_path not in allowed_prefixes:
        raise ValueError('Cleanup prefix does not match its organization')
    if Tenant.objects.filter(pk=cleanup.organization_id).exists():
        raise ValueError('Cannot scan storage for an existing organization')

    def renew_lease():
        if not ResourceCleanup.objects.filter(pk=cleanup.pk, lease_token=token, completed_at__isnull=True).update(
            next_attempt_at=timezone.now() + LEASE_DURATION, updated_at=timezone.now()
        ):
            raise CleanupLeaseLost()

    delete_storage_prefix(storage, cleanup.resource_path, progress=renew_lease)


def schedule_resource_cleanup(resource_type, *, organization_id='', resource_path=''):
    """Call inside the deletion transaction so rollback also discards cleanup work."""
    cleanup = ResourceCleanup.objects.create(
        resource_type=resource_type, organization_id=str(organization_id or ''), resource_path=resource_path
    )
    transaction.on_commit(lambda: enqueue_resource_cleanup(str(cleanup.pk)))
    return cleanup


def enqueue_resource_cleanup(cleanup_id):
    try:
        current_app.send_task('apps.multitenancy.tasks.process_resource_cleanup', args=[cleanup_id], retry=False)
    except Exception as exc:
        # Deletion already committed. The periodic sweep recovers the durable row.
        logger.warning('Cleanup queue submission failed: cleanup_id=%s error_type=%s', cleanup_id, type(exc).__name__)
        try:
            ResourceCleanup.objects.filter(pk=cleanup_id, attempts=0, completed_at__isnull=True).update(
                last_error='queue_submission_failed', updated_at=timezone.now()
            )
        except Exception as persist_exc:
            # Even if the DB briefly fails here, the already-committed outbox row
            # remains due. Do not report a failed organization deletion or skip notifications.
            logger.warning(
                'Could not record queue failure: cleanup_id=%s error_type=%s', cleanup_id, type(persist_exc).__name__
            )


def process_resource_cleanup(cleanup_id):
    """Claim briefly under a row lock, then delete idempotently outside the transaction."""
    now = timezone.now()
    token = uuid.uuid4()
    with transaction.atomic():
        cleanup = (
            ResourceCleanup.objects.select_for_update(skip_locked=True)
            .filter(pk=cleanup_id, completed_at__isnull=True, next_attempt_at__lte=now)
            .first()
        )
        if cleanup is None:
            return False
        cleanup.attempts += 1
        cleanup.lease_token = token
        # If this worker dies, the row becomes claimable again when the lease expires.
        cleanup.next_attempt_at = now + LEASE_DURATION
        cleanup.save(update_fields=['attempts', 'lease_token', 'next_attempt_at', 'updated_at'])

    try:
        if cleanup.resource_type == ResourceCleanup.ResourceType.EXPORT_FILE:
            get_exports_storage().delete(cleanup.resource_path)
        elif cleanup.resource_type == ResourceCleanup.ResourceType.DOCUMENT_FILE:
            DocumentDemoItem._meta.get_field('file').storage.delete(cleanup.resource_path)
        elif cleanup.resource_type == ResourceCleanup.ResourceType.BACKUP_KEY:
            if not get_backup_encryption_service().delete_tenant_key(cleanup.organization_id, strict=True):
                raise RuntimeError('Backup key deletion was not confirmed')
        elif cleanup.resource_type in (
            ResourceCleanup.ResourceType.EXPORT_PREFIX,
            ResourceCleanup.ResourceType.DOCUMENT_PREFIX,
        ):
            clean_organization_prefix(cleanup, token)
        else:
            raise ValueError('Unknown cleanup resource type')
    except CleanupLeaseLost:
        return False
    except Exception as exc:
        # Keep only the exception type: provider messages can contain credentials or signed URLs.
        retry_delay = min(3600, 30 * 2 ** min(cleanup.attempts - 1, 7))
        ResourceCleanup.objects.filter(pk=cleanup.pk, lease_token=token, completed_at__isnull=True).update(
            lease_token=None,
            next_attempt_at=timezone.now() + timedelta(seconds=retry_delay),
            last_error=type(exc).__name__[:120],
            updated_at=timezone.now(),
        )
        logger.warning('Cleanup failed, will retry: cleanup_id=%s error_type=%s', cleanup.pk, type(exc).__name__)
        return False

    # A slow, expired worker must not overwrite a newer worker's attempt/outcome.
    updated = ResourceCleanup.objects.filter(pk=cleanup.pk, lease_token=token, completed_at__isnull=True).update(
        lease_token=None, completed_at=timezone.now(), last_error='', updated_at=timezone.now()
    )
    if updated:
        logger.info('Cleanup completed: cleanup_id=%s', cleanup.pk)
    return bool(updated)


def process_due_resource_cleanups():
    ids = list(
        ResourceCleanup.objects.filter(completed_at__isnull=True, next_attempt_at__lte=timezone.now())
        .order_by('next_attempt_at', 'created_at')
        .values_list('pk', flat=True)[:100]
    )
    for cleanup_id in ids:
        process_resource_cleanup(cleanup_id)
