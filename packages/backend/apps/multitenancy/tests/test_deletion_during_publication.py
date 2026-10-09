from concurrent.futures import ThreadPoolExecutor
from threading import Event
from zipfile import ZipFile

import pytest
from django.db import connection, connections
from django.core.files.storage import FileSystemStorage

from apps.backup.models import BackupRecord
from apps.backup.tasks import create_backup
from apps.demo.models import DocumentDemoItem
from common.storages import get_exports_storage
from ..models import ActionLogExport, ResourceCleanup, Tenant
from ..permissions import seed_permissions
from ..tasks import export_action_logs, process_due_resource_cleanups
from .test_tenant_deletion import delete_tenant

# Separate connections and actual commits are essential to test PostgreSQL row locks.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def isolate_external_services(mocker, tmp_path):
    mocker.patch.object(DocumentDemoItem._meta.get_field('file'), 'storage', FileSystemStorage(location=tmp_path))
    mocker.patch('apps.multitenancy.schema.close_old_connections')
    mocker.patch('apps.multitenancy.services.deletion.subscriptions.get_schedule', return_value=None)
    mocker.patch('apps.multitenancy.notifications.TenantDeletedEmail')
    mocker.patch('apps.multitenancy.cleanup.current_app.send_task')
    service = mocker.patch('apps.multitenancy.cleanup.get_backup_encryption_service').return_value
    service.delete_tenant_key.return_value = True


@pytest.fixture
def organization(user, tenant_factory, tenant_membership_factory):
    # Transactional tests flush migration-seeded data between cases.
    seed_permissions()
    tenant = tenant_factory(type='organization')
    tenant_membership_factory(tenant=tenant, user=user, role='OWNER')
    return tenant


def prepare_job(kind, organization, user, mocker):
    if kind == 'backup':
        generator = mocker.patch('apps.backup.tasks.BackupService').return_value
        generator.generate_xml.return_value = '<backup />'
        generator.model_counts = {}
        encryption = mocker.patch('apps.backup.tasks.get_backup_encryption_service').return_value
        encryption.encrypt_backup.return_value = b'encrypted'
        return lambda: create_backup.run(str(organization.pk)), generator, encryption
    job = ActionLogExport.objects.create(tenant=organization, requested_by=user)
    return lambda: export_action_logs.run(str(job.pk)), None, None


def in_worker_thread(fn):
    try:
        return fn()
    finally:
        connections.close_all()


@pytest.mark.parametrize('kind', ['backup', 'export'])
def test_deletion_waits_for_upload_and_collects_its_committed_path(kind, organization, user, graphene_client, mocker):
    tenant_id = str(organization.pk)
    run, _, _ = prepare_job(kind, organization, user, mocker)
    storage = get_exports_storage()
    upload_started = Event()
    finish_upload = Event()
    deletion_lock_requested = Event()
    saved = []

    def upload(path, content):
        upload_started.set()
        assert finish_upload.wait(timeout=15), 'Test never released upload'
        actual_path = storage.save(path, content)
        saved.append(actual_path)
        return actual_path

    task_module = 'apps.backup.tasks' if kind == 'backup' else 'apps.multitenancy.tasks'
    task_storage = mocker.patch(f'{task_module}.get_exports_storage').return_value
    task_storage.save.side_effect = upload
    task_storage.exists.side_effect = storage.exists
    task_storage.url.return_value = 'https://example.test/export'

    def observe_deletion_lock(execute, sql, params, many, context):
        if 'multitenancy_tenant' in sql and 'FOR UPDATE' in sql:
            deletion_lock_requested.set()
        return execute(sql, params, many, context)

    def delete():
        with connection.execute_wrapper(observe_deletion_lock):
            return delete_tenant(graphene_client, user, organization)

    with ThreadPoolExecutor(max_workers=2) as executor:
        publisher = executor.submit(in_worker_thread, run)
        try:
            assert upload_started.wait(timeout=15)
            deleter = executor.submit(in_worker_thread, delete)
            assert deletion_lock_requested.wait(timeout=15)
        finally:
            finish_upload.set()
        publication_result = publisher.result(timeout=15)
        deletion_result = deleter.result(timeout=15)

    assert publication_result.get('success', True)
    assert publication_result.get('status', 'completed') == 'completed'
    assert not deletion_result.get('errors'), deletion_result
    assert not Tenant.objects.filter(pk=tenant_id).exists()
    assert len(saved) == 1
    assert ResourceCleanup.objects.filter(
        organization_id=tenant_id, resource_type='export_file', resource_path=saved[0]
    ).exists()
    # A persisted path from the in-flight upload is actually removed by cleanup.
    assert storage.exists(saved[0])
    mocker.patch('apps.multitenancy.cleanup.get_exports_storage', return_value=storage)
    process_due_resource_cleanups.run()
    assert not storage.exists(saved[0])


@pytest.mark.parametrize('kind', ['backup', 'export'])
@pytest.mark.parametrize('generation_fails', [False, True])
def test_job_stops_if_deletion_commits_during_content_generation(
    kind, generation_fails, organization, user, graphene_client, mocker
):
    tenant_id = str(organization.pk)
    run, generator, encryption = prepare_job(kind, organization, user, mocker)
    task_module = 'apps.backup.tasks' if kind == 'backup' else 'apps.multitenancy.tasks'
    storage = mocker.patch(f'{task_module}.get_exports_storage').return_value

    def delete_organization():
        result = delete_tenant(graphene_client, user, organization)
        assert not result.get('errors'), result

    if kind == 'backup':

        def generate():
            delete_organization()
            if generation_fails:
                raise OSError('generation interrupted')
            return '<backup />'

        generator.generate_xml.side_effect = generate
    else:

        def zip_after_deletion(*args, **kwargs):
            delete_organization()
            if generation_fails:
                raise OSError('generation interrupted')
            return ZipFile(*args, **kwargs)

        mocker.patch('apps.multitenancy.tasks.zipfile.ZipFile', side_effect=zip_after_deletion)

    result = run()
    assert result['status'] == 'cancelled'
    storage.save.assert_not_called()
    if encryption is not None:
        encryption.encrypt_backup.assert_not_called()  # Cannot recreate a deleted encryption key.
    assert not Tenant.objects.filter(pk=tenant_id).exists()
    assert not BackupRecord.objects.filter(tenant_id=tenant_id).exists()
    assert not ActionLogExport.objects.filter(tenant_id=tenant_id).exists()


@pytest.mark.parametrize('kind', ['backup', 'export'])
def test_failed_publication_after_writing_registers_durable_cleanup(kind, organization, user, mocker):
    run, _, _ = prepare_job(kind, organization, user, mocker)
    storage = get_exports_storage()
    saved = []

    def upload(path, content):
        actual_path = storage.save(path, content)
        saved.append(actual_path)
        return actual_path

    task_module = 'apps.backup.tasks' if kind == 'backup' else 'apps.multitenancy.tasks'
    task_storage = mocker.patch(f'{task_module}.get_exports_storage').return_value
    task_storage.save.side_effect = upload
    task_storage.exists.return_value = True
    task_storage.url.return_value = 'https://example.test/export'
    # Force failure after storage succeeds, while the publication transaction is open.
    outcome_logger = 'log_backup_result' if kind == 'backup' else 'log_export_result'
    mocker.patch(f'{task_module}.{outcome_logger}', side_effect=[RuntimeError('publication failed'), None])
    task = create_backup if kind == 'backup' else export_action_logs
    mocker.patch.object(task, 'retry', side_effect=RuntimeError('retry'))
    with pytest.raises(RuntimeError, match='retry'):
        run()
    assert len(saved) == 1
    assert ResourceCleanup.objects.filter(resource_type='export_file', resource_path=saved[0]).exists()
    mocker.patch('apps.multitenancy.cleanup.get_exports_storage', return_value=storage)
    process_due_resource_cleanups.run()
    assert not storage.exists(saved[0])
