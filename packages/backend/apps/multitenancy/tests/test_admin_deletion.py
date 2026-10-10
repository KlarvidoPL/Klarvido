import json
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.contrib.admin.models import DELETION, LogEntry
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied

from apps.backup.models import BackupRecord
from apps.notifications.models import Notification
from ..admin import TenantAdmin
from ..constants import Notification as NotificationType
from ..models import ActionLogExport, ResourceCleanup, Tenant
from ..services.deletion import delete_organization
from ..deletion_notifications import process_due_deletion_notifications

pytestmark = pytest.mark.django_db


@pytest.fixture
def deletion_admin(user_factory, settings, mocker):
    settings.STORAGES = {
        **settings.STORAGES,
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    actor = user_factory(is_superuser=True, is_confirmed=True)
    client = Client()
    client.force_login(actor)
    mocker.patch('apps.multitenancy.services.deletion.subscriptions.get_schedule', return_value=None)
    queue = mocker.patch('apps.multitenancy.cleanup.current_app.send_task')
    email = mocker.patch('apps.multitenancy.notifications.TenantDeletedEmail')
    mocker.patch(
        'apps.multitenancy.deletion_notifications.enqueue_deletion_notifications',
        side_effect=lambda ids: process_due_deletion_notifications(),
    )
    return client, actor, queue, email


@pytest.mark.parametrize('bulk', [False, True])
def test_admin_deletion_cleans_resources_notifies_members_and_records_actor(
    bulk,
    deletion_admin,
    tenant_factory,
    tenant_membership_factory,
    user_factory,
    document_demo_item_factory,
    django_capture_on_commit_callbacks,
):
    client, actor, queue, email = deletion_admin
    tenant = tenant_factory(type='organization', name='Admin deleted')
    tenant_id = str(tenant.pk)
    member = user_factory()
    invited = user_factory()
    tenant_membership_factory(tenant=tenant, user=member, is_accepted=True)
    tenant_membership_factory(tenant=tenant, user=invited, is_accepted=False)
    BackupRecord.objects.create(tenant=tenant, file_path='legacy/backup.xml')
    ActionLogExport.objects.create(tenant=tenant, requested_by=member, file_path='legacy/export.zip')
    document = document_demo_item_factory(tenant=tenant)
    document_path = document.file.name
    # A superuser need not belong to the organization to use Django Admin.
    with django_capture_on_commit_callbacks(execute=True):
        if bulk:
            response = client.post(
                reverse('admin:multitenancy_tenant_changelist'),
                {
                    'action': 'delete_selected',
                    '_selected_action': [tenant_id],
                    'post': 'yes',
                },
            )
        else:
            response = client.post(reverse('admin:multitenancy_tenant_delete', args=[tenant_id]), {'post': 'yes'})
    assert response.status_code == 302
    assert not Tenant.objects.filter(pk=tenant_id).exists()
    jobs = ResourceCleanup.objects.filter(organization_id=tenant_id)
    assert set(jobs.values_list('resource_type', 'resource_path')) == {
        ('export_file', 'legacy/backup.xml'),
        ('export_file', 'legacy/export.zip'),
        ('document_file', document_path),
        ('backup_key', ''),
        ('export_prefix', f'tenant_backups/{tenant_id}/'),
        ('export_prefix', f'action_logs/{tenant_id}/'),
        ('document_prefix', f'documents/organizations/{tenant_id}/'),
    }
    assert queue.call_count == 7
    notice = Notification.objects.get(type=NotificationType.TENANT_DELETED.value)
    assert notice.user == member
    assert notice.issuer == actor
    assert email.call_count == 2  # Member and administrator confirmation.
    audit = LogEntry.objects.get(object_id=tenant_id, action_flag=DELETION)
    assert audit.user == actor
    assert json.loads(audit.change_message)['actor_type'] == 'SUPERUSER'


def test_bulk_admin_deletes_each_selected_organization(
    deletion_admin, tenant_factory, django_capture_on_commit_callbacks
):
    client, _, queue, email = deletion_admin
    tenants = tenant_factory.create_batch(2, type='organization')
    ids = [str(tenant.pk) for tenant in tenants]
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse('admin:multitenancy_tenant_changelist'),
            {
                'action': 'delete_selected',
                '_selected_action': ids,
                'post': 'yes',
            },
        )
    assert response.status_code == 302
    assert not Tenant.objects.filter(pk__in=ids).exists()
    assert ResourceCleanup.objects.filter(organization_id__in=ids).count() == 8
    assert queue.call_count == 8
    assert email.call_count == 2


@pytest.mark.parametrize('bulk', [False, True])
def test_admin_cannot_delete_default_personal_tenant(
    bulk, deletion_admin, tenant_factory, django_capture_on_commit_callbacks
):
    client, _, queue, email = deletion_admin
    personal = tenant_factory(type='default')
    organization = tenant_factory(type='organization')
    with django_capture_on_commit_callbacks(execute=True):
        if bulk:
            response = client.post(
                reverse('admin:multitenancy_tenant_changelist'),
                {
                    'action': 'delete_selected',
                    '_selected_action': [str(personal.pk), str(organization.pk)],
                    'post': 'yes',
                },
            )
        else:
            response = client.post(
                reverse('admin:multitenancy_tenant_delete', args=[str(personal.pk)]), {'post': 'yes'}
            )
    assert response.status_code in (200, 403)
    assert Tenant.objects.filter(pk=personal.pk).exists()
    assert Tenant.objects.filter(pk=organization.pk).exists()
    assert not ResourceCleanup.objects.exists()
    queue.assert_not_called()
    email.assert_not_called()


def test_direct_bulk_hook_rolls_back_all_deletions_on_failure(
    deletion_admin, tenant_factory, django_capture_on_commit_callbacks, mocker
):
    _, actor, queue, email = deletion_admin
    tenants = tenant_factory.create_batch(2, type='organization')
    ids = [tenant.pk for tenant in tenants]
    real_delete = delete_organization
    calls = []

    def fail_second(tenant_id, request, **kwargs):
        calls.append(tenant_id)
        if len(calls) == 2:
            raise RuntimeError('delete failed')
        return real_delete(tenant_id, request, **kwargs)

    mocker.patch('apps.multitenancy.admin.delete_organization', side_effect=fail_second)
    model_admin = TenantAdmin(Tenant, admin.site)
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError):
        model_admin.delete_queryset(SimpleNamespace(user=actor), Tenant.objects.filter(pk__in=ids))
    assert Tenant.objects.filter(pk__in=ids).count() == 2
    assert not ResourceCleanup.objects.exists()
    assert not LogEntry.objects.filter(object_id__in=[str(pk) for pk in ids], action_flag=DELETION).exists()
    queue.assert_not_called()
    email.assert_not_called()


def test_admin_service_does_not_allow_unprivileged_bypass(user, tenant_factory):
    tenant = tenant_factory(type='organization')
    with pytest.raises(PermissionDenied):
        delete_organization(tenant.pk, SimpleNamespace(user=user), via_admin=True)
    assert Tenant.objects.filter(pk=tenant.pk).exists()
    assert not ResourceCleanup.objects.exists()


def test_direct_admin_service_protects_default_tenant(deletion_admin, tenant_factory):
    _, actor, _, _ = deletion_admin
    tenant = tenant_factory(type='default')
    with pytest.raises(ValidationError):
        delete_organization(tenant.pk, SimpleNamespace(user=actor), via_admin=True)
    assert Tenant.objects.filter(pk=tenant.pk).exists()


@pytest.mark.parametrize('bulk', [False, True])
def test_admin_confirmation_does_not_delete_or_schedule_cleanup(bulk, deletion_admin, tenant_factory):
    client, _, queue, email = deletion_admin
    tenant = tenant_factory(type='organization')
    if bulk:
        response = client.post(
            reverse('admin:multitenancy_tenant_changelist'),
            {'action': 'delete_selected', '_selected_action': [str(tenant.pk)]},
        )
    else:
        response = client.get(reverse('admin:multitenancy_tenant_delete', args=[str(tenant.pk)]))
    assert response.status_code == 200
    assert Tenant.objects.filter(pk=tenant.pk).exists()
    assert not ResourceCleanup.objects.exists()
    queue.assert_not_called()
    email.assert_not_called()
