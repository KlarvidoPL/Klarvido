from unittest.mock import Mock, call
import uuid

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.utils import timezone
from storages.backends.s3boto3 import S3Boto3Storage

from apps.demo.models import DocumentDemoItem
from common.storages import OrganizationDocumentPathGenerator, delete_storage_prefix, organization_document_prefix
from ..cleanup import process_resource_cleanup, schedule_organization_prefix_cleanup
from ..models import ResourceCleanup

pytestmark = pytest.mark.django_db


def test_s3_pagination_uses_exact_keys_and_storage_location():
    storage = Mock(spec=S3Boto3Storage)
    storage.location = 'exports'
    storage.bucket_name = 'private-files'
    client = storage.connection.meta.client
    prefix = 'exports/tenant_backups/abc/'
    keys = [f'{prefix}{i}.xml' for i in range(1001)] + [f'{prefix}../odd.xml']
    client.get_paginator.return_value.paginate.return_value = [
        {'Contents': [{'Key': key} for key in keys[:1000]]},
        {'Contents': [{'Key': key} for key in keys[1000:]]},
    ]
    progress = Mock()
    delete_storage_prefix(storage, 'tenant_backups/abc/', progress=progress)
    client.get_paginator.assert_called_once_with('list_objects_v2')
    client.get_paginator.return_value.paginate.assert_called_once_with(
        Bucket='private-files', Prefix=prefix, PaginationConfig={'PageSize': 1000}
    )
    assert client.delete_object.call_args_list == [call(Bucket='private-files', Key=key) for key in keys]
    assert progress.call_count > 2


def test_s3_refuses_a_listing_outside_the_requested_prefix():
    storage = Mock(spec=S3Boto3Storage)
    storage.location = ''
    storage.bucket_name = 'private-files'
    storage.connection.meta.client.get_paginator.return_value.paginate.return_value = [
        {'Contents': [{'Key': 'tenant_backups/abcd/keep.xml'}]}
    ]
    with pytest.raises(ValueError):
        delete_storage_prefix(storage, 'tenant_backups/abc/')
    storage.connection.meta.client.delete_object.assert_not_called()


@pytest.mark.parametrize('prefix', ['', '/', 'documents', '../org/', 'documents//org/'])
def test_invalid_prefix_is_rejected(tmp_path, prefix):
    with pytest.raises(ValueError):
        delete_storage_prefix(FileSystemStorage(location=tmp_path), prefix)


def test_untracked_files_are_removed_only_inside_deleted_organization_prefixes(tmp_path, mocker):
    storage = FileSystemStorage(location=tmp_path)
    mocker.patch('apps.multitenancy.cleanup.get_exports_storage', return_value=storage)
    mocker.patch.object(DocumentDemoItem._meta.get_field('file'), 'storage', storage)
    mocker.patch('apps.multitenancy.cleanup.current_app.send_task')
    deleted = [
        'tenant_backups/abc/orphan.xml',
        'action_logs/abc/nested/orphan.zip',
        'documents/organizations/abc/random/orphan.pdf',
    ]
    retained = [
        'tenant_backups/abcd/keep.xml',
        'action_logs/other/keep.zip',
        'documents/organizations/other/keep.pdf',
        'documents/legacy/unknown.pdf',
    ]
    for path in deleted + retained:
        storage.save(path, ContentFile(b'file'))
    schedule_organization_prefix_cleanup('abc')
    for job in ResourceCleanup.objects.all():
        assert process_resource_cleanup(job.pk)
    assert all(not storage.exists(path) for path in deleted)
    assert all(storage.exists(path) for path in retained)


def test_partial_scan_failure_is_durable_and_retryable(tmp_path, mocker):
    storage = FileSystemStorage(location=tmp_path)
    mocker.patch('apps.multitenancy.cleanup.get_exports_storage', return_value=storage)
    paths = ['tenant_backups/abc/first.xml', 'tenant_backups/abc/second.xml']
    for path in paths:
        storage.save(path, ContentFile(b'file'))
    actual_delete = storage.delete
    calls = []

    def fail_after_first_file(path):
        calls.append(path)
        if len(calls) == 2:
            raise OSError('storage unavailable')
        actual_delete(path)

    delete = mocker.patch.object(storage, 'delete', side_effect=fail_after_first_file)
    job = ResourceCleanup.objects.create(
        resource_type='export_prefix', organization_id='abc', resource_path='tenant_backups/abc/'
    )
    assert not process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.completed_at is None
    assert job.last_error == 'OSError'
    assert job.next_attempt_at > timezone.now()
    assert sum(storage.exists(path) for path in paths) == 1
    delete.side_effect = actual_delete
    ResourceCleanup.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now())
    assert process_resource_cleanup(job.pk)
    assert all(not storage.exists(path) for path in paths)


def test_existing_organization_and_mismatched_prefix_cannot_be_scanned(tenant, mocker):
    scan = mocker.patch('apps.multitenancy.cleanup.delete_storage_prefix')
    for prefix in [f'tenant_backups/{tenant.pk}/', 'tenant_backups/other/']:
        job = ResourceCleanup.objects.create(
            resource_type='export_prefix', organization_id=str(tenant.pk), resource_path=prefix
        )
        assert not process_resource_cleanup(job.pk)
    scan.assert_not_called()


def test_prefix_jobs_roll_back_with_deletion(mocker, django_capture_on_commit_callbacks):
    queue = mocker.patch('apps.multitenancy.cleanup.current_app.send_task')
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError), transaction.atomic():
        schedule_organization_prefix_cleanup('abc')
        assert ResourceCleanup.objects.count() == 3
        raise RuntimeError('rollback')
    assert not ResourceCleanup.objects.exists()
    queue.assert_not_called()


def test_storage_listing_failure_remains_pending(mocker):
    mocker.patch('apps.multitenancy.cleanup.delete_storage_prefix', side_effect=OSError('listing unavailable'))
    job = ResourceCleanup.objects.create(
        resource_type='export_prefix', organization_id='abc', resource_path='tenant_backups/abc/'
    )
    assert not process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.completed_at is None
    assert job.last_error == 'OSError'
    assert job.lease_token is None


def test_scan_stops_when_another_worker_owns_the_lease(mocker):
    job = ResourceCleanup.objects.create(
        resource_type='export_prefix', organization_id='abc', resource_path='tenant_backups/abc/'
    )
    replacement_token = uuid.uuid4()

    def replace_lease(storage, prefix, *, progress):
        ResourceCleanup.objects.filter(pk=job.pk).update(lease_token=replacement_token)
        progress()

    mocker.patch('apps.multitenancy.cleanup.delete_storage_prefix', side_effect=replace_lease)
    assert not process_resource_cleanup(job.pk)
    job.refresh_from_db()
    assert job.lease_token == replacement_token
    assert job.completed_at is None
    assert job.last_error == ''


def test_local_scan_rejects_symlinked_parent(tmp_path):
    storage = FileSystemStorage(location=tmp_path / 'storage')
    outside = tmp_path / 'outside'
    (outside / 'abc').mkdir(parents=True)
    (outside / 'abc' / 'keep.xml').write_bytes(b'keep')
    (tmp_path / 'storage').mkdir()
    (tmp_path / 'storage' / 'tenant_backups').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        delete_storage_prefix(storage, 'tenant_backups/abc/')
    assert (outside / 'abc' / 'keep.xml').exists()


def test_new_documents_use_canonical_organization_prefix(tenant):
    generator = OrganizationDocumentPathGenerator()
    document = DocumentDemoItem(tenant=tenant)
    assert generator(document, 'report.pdf').startswith(organization_document_prefix(tenant.pk))
    document.tenant_id = int(tenant.pk)
    assert generator(document, 'report.pdf').startswith(organization_document_prefix(tenant.pk))
    document.tenant_id = None
    assert generator(document, 'legacy.pdf').startswith('documents/')
    assert not generator(document, 'legacy.pdf').startswith('documents/organizations/')
