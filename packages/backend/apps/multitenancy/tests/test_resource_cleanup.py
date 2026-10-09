import uuid
from datetime import timedelta

import pytest
from botocore.exceptions import ClientError
from django.contrib.admin.models import LogEntry
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.backup.encryption import BackupEncryptionService
from apps.backup.models import BackupRecord
from apps.demo.models import DocumentDemoItem
from common.secrets.service import SecretsService
from common.storages import get_exports_storage
from ..cleanup import LEASE_DURATION, process_resource_cleanup, schedule_resource_cleanup
from ..models import ActionLogExport, ResourceCleanup, Tenant
from ..tasks import process_due_resource_cleanups
from .test_tenant_deletion import delete_tenant

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def queue(mocker):
    return mocker.patch('apps.multitenancy.cleanup.current_app.send_task')


def test_cleanup_and_deleted_resource_are_rolled_back_together(
    document_demo_item_factory, django_capture_on_commit_callbacks, queue
):
    document = document_demo_item_factory()
    pk = document.pk
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError), transaction.atomic():
        document.delete()
        assert ResourceCleanup.objects.count() == 1
        raise RuntimeError('rollback')
    assert DocumentDemoItem.objects.filter(pk=pk).exists()
    assert not ResourceCleanup.objects.exists()
    queue.assert_not_called()


def test_queue_failure_preserves_cleanup_and_does_not_fail_deletion_or_notifications(
    graphene_client,
    user,
    user_factory,
    tenant_factory,
    tenant_membership_factory,
    document_demo_item_factory,
    mocker,
    queue,
    django_capture_on_commit_callbacks,
):
    tenant = tenant_factory(type='organization')
    tenant_pk = str(tenant.pk)
    tenant_membership_factory(tenant=tenant, user=user, role='OWNER')
    member = user_factory()
    tenant_membership_factory(tenant=tenant, user=member)
    BackupRecord.objects.create(tenant=tenant, file_path='backups/example.xml')
    ActionLogExport.objects.create(tenant=tenant, requested_by=user, file_path='exports/example.zip')
    document_demo_item_factory(tenant=tenant)
    mocker.patch('apps.multitenancy.schema.close_old_connections')
    email = mocker.patch('apps.multitenancy.notifications.TenantDeletedEmail')
    queue.side_effect = ConnectionError('broker offline')

    with django_capture_on_commit_callbacks(execute=True):
        result = delete_tenant(graphene_client, user, tenant)
    assert not result.get('errors'), result
    assert not Tenant.objects.filter(pk=tenant_pk).exists()
    jobs = ResourceCleanup.objects.filter(organization_id=tenant_pk)
    assert jobs.count() == 4
    assert set(jobs.values_list('last_error', flat=True)) == {'queue_submission_failed'}
    assert email.call_count == 2
    assert LogEntry.objects.filter(object_id=tenant_pk, action_flag=3).exists()

    storage = mocker.patch('apps.multitenancy.cleanup.get_exports_storage').return_value
    document_storage = mocker.patch.object(DocumentDemoItem._meta.get_field('file'), 'storage')
    key = mocker.patch('apps.multitenancy.cleanup.get_backup_encryption_service').return_value
    key.delete_tenant_key.return_value = True
    # No successful enqueue is needed: the periodic task processes the persisted work.
    process_due_resource_cleanups.run()
    assert jobs.filter(completed_at__isnull=True).count() == 0
    assert storage.delete.call_count == 2
    assert document_storage.delete.call_count == 1
    key.delete_tenant_key.assert_called_once_with(tenant_pk, strict=True)


def test_failed_file_is_retried_independently_with_backoff(mocker, freezer):
    storage = mocker.patch('apps.multitenancy.cleanup.get_exports_storage').return_value
    failed = ResourceCleanup.objects.create(resource_type='export_file', resource_path='bad.xml')
    successful = ResourceCleanup.objects.create(resource_type='export_file', resource_path='ok.zip')
    storage.delete.side_effect = [OSError('signed URL or credentials'), None, OSError('retry'), None]

    process_due_resource_cleanups.run()
    failed.refresh_from_db()
    successful.refresh_from_db()
    assert successful.completed_at is not None
    assert failed.completed_at is None
    assert failed.attempts == 1
    assert failed.last_error == 'OSError'
    assert failed.next_attempt_at == timezone.now() + timedelta(seconds=30)
    process_due_resource_cleanups.run()
    assert storage.delete.call_count == 2  # Backoff prevents an early retry.
    freezer.tick(timedelta(seconds=30))
    process_due_resource_cleanups.run()
    failed.refresh_from_db()
    assert failed.attempts == 2
    assert failed.next_attempt_at == timezone.now() + timedelta(seconds=60)
    freezer.tick(timedelta(seconds=60))
    process_due_resource_cleanups.run()
    failed.refresh_from_db()
    assert failed.completed_at is not None
    assert failed.attempts == 3
    assert failed.last_error == ''
    process_due_resource_cleanups.run()
    assert storage.delete.call_count == 4  # Completed files are never repeated.


def test_failed_key_cleanup_is_not_marked_completed(mocker, freezer):
    key = mocker.patch('apps.multitenancy.cleanup.get_backup_encryption_service').return_value
    key.delete_tenant_key.side_effect = [
        False,
        ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'DeleteSecret'),
        True,
    ]
    job = ResourceCleanup.objects.create(resource_type='backup_key', organization_id='gone')
    process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.last_error == 'RuntimeError'
    assert job.completed_at is None
    freezer.tick(timedelta(seconds=30))
    process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.last_error == 'ClientError'
    assert job.completed_at is None
    freezer.tick(timedelta(seconds=60))
    process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.completed_at is not None


def test_long_outages_keep_retrying_with_a_capped_delay(mocker, freezer):
    storage = mocker.patch('apps.multitenancy.cleanup.get_exports_storage').return_value
    storage.delete.side_effect = [OSError('still unavailable'), None]
    job = ResourceCleanup.objects.create(resource_type='export_file', resource_path='example.xml', attempts=50)
    process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.attempts == 51
    assert job.completed_at is None
    assert job.next_attempt_at == timezone.now() + timedelta(hours=1)
    freezer.tick(timedelta(hours=1))
    process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.completed_at is not None


def test_failure_to_record_queue_error_does_not_lose_cleanup(mocker, queue, django_capture_on_commit_callbacks):
    queue.side_effect = ConnectionError('broker offline')
    # Simulate a second outage while storing the queue error after commit.
    mocker.patch.object(ResourceCleanup.objects, 'filter', side_effect=ConnectionError('DB temporarily offline'))
    with django_capture_on_commit_callbacks(execute=True):
        job = schedule_resource_cleanup(ResourceCleanup.ResourceType.EXPORT_FILE, resource_path='example.xml')
    job.refresh_from_db()
    assert job.completed_at is None
    assert job.attempts == 0
    assert job.next_attempt_at <= timezone.now()


def test_periodic_worker_recovers_an_expired_lease(mocker, freezer):
    storage = mocker.patch('apps.multitenancy.cleanup.get_exports_storage').return_value
    job = ResourceCleanup.objects.create(
        resource_type='export_file',
        resource_path='example.xml',
        attempts=1,
        lease_token=uuid.uuid4(),
        next_attempt_at=timezone.now() + LEASE_DURATION,
    )
    process_due_resource_cleanups.run()
    storage.delete.assert_not_called()
    freezer.tick(LEASE_DURATION)
    process_due_resource_cleanups.run()
    job.refresh_from_db()
    assert job.attempts == 2
    assert job.completed_at is not None
    assert job.lease_token is None


def test_duplicate_worker_cannot_claim_an_active_job(mocker):
    job = ResourceCleanup.objects.create(resource_type='export_file', resource_path='example.xml')
    storage = mocker.patch('apps.multitenancy.cleanup.get_exports_storage').return_value
    storage.delete.side_effect = lambda path: process_resource_cleanup(job.pk)
    assert process_resource_cleanup(job.pk) is True
    storage.delete.assert_called_once_with('example.xml')
    job.refresh_from_db()
    assert job.attempts == 1


def test_expired_worker_cannot_overwrite_newer_attempt(mocker, freezer):
    job = ResourceCleanup.objects.create(resource_type='export_file', resource_path='example.xml')
    storage = mocker.patch('apps.multitenancy.cleanup.get_exports_storage').return_value

    def expire_and_reclaim(path):
        freezer.tick(LEASE_DURATION)
        storage.delete.side_effect = OSError('second worker failed')
        process_resource_cleanup(job.pk)

    storage.delete.side_effect = expire_and_reclaim
    assert process_resource_cleanup(job.pk) is False
    job.refresh_from_db()
    assert job.attempts == 2
    assert job.completed_at is None
    assert job.last_error == 'OSError'


def test_cleanup_is_safe_when_a_file_was_already_removed():
    storage = get_exports_storage()
    path = storage.save('backups/idempotent.xml', ContentFile(b'backup'))
    storage.delete(path)
    job = ResourceCleanup.objects.create(resource_type='export_file', resource_path=path)
    assert process_resource_cleanup(job.pk) is True


def test_sweep_is_bounded(mocker):
    ResourceCleanup.objects.bulk_create(
        [ResourceCleanup(resource_type='export_file', resource_path=f'{i}.xml') for i in range(101)]
    )
    mocker.patch('apps.multitenancy.cleanup.get_exports_storage')
    process_due_resource_cleanups.run()
    assert ResourceCleanup.objects.filter(completed_at__isnull=False).count() == 100
    process_due_resource_cleanups.run()
    assert ResourceCleanup.objects.filter(completed_at__isnull=True).count() == 0


@pytest.mark.parametrize(
    'error_code, succeeds', [('ResourceNotFoundException', True), ('AccessDeniedException', False)]
)
def test_strict_secret_cleanup_distinguishes_missing_secret_from_failure(mocker, error_code, succeeds):
    mocker.patch.object(SecretsService, '_init_client')
    service = SecretsService('backup')
    service.client = mocker.Mock()
    service.client.delete_secret.side_effect = ClientError({'Error': {'Code': error_code}}, 'DeleteSecret')
    if succeeds:
        assert service.delete_secret_by_name('gone', 'encryption_key', force=True, strict=True)
    else:
        with pytest.raises(ClientError):
            service.delete_secret_by_name('gone', 'encryption_key', force=True, strict=True)


def test_strict_key_cleanup_reinitializes_client_and_preserves_unavailability(mocker):
    service = BackupEncryptionService()
    service.secrets_service = mocker.Mock(client=None)
    mocker.patch.object(service, '_get_fernet', return_value=None)
    with pytest.raises(RuntimeError):
        service.delete_tenant_key('gone', strict=True)
    service.secrets_service._init_client.assert_called_once_with()


def test_database_only_key_cleanup_can_complete_without_aws(mocker):
    service = BackupEncryptionService()
    service.secrets_service = mocker.Mock(client=None)
    mocker.patch.object(service, '_get_fernet', return_value=mocker.Mock())
    assert service.delete_tenant_key('gone', strict=True)
    service.secrets_service.delete_secret_by_name.assert_not_called()
