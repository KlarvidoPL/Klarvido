"""Activity coverage across activity_request operations and background outcomes."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.contrib.admin.models import LogEntry, DELETION
from graphql_relay import to_global_id

from apps.backup.models import BackupRecord, RestoreRecord
from apps.backup.schema import (
    UpdateBackupConfigMutation,
    TriggerBackupMutation,
    DeleteBackupMutation,
    DownloadBackupDecryptedMutation,
    RestoreBackupMutation,
)
from apps.backup.tasks import create_backup, restore_backup
from apps.finances.serializers import UpdateDefaultPaymentMethodSerializer
from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import (
    ActionLog,
    ActionLogExport,
    TenantMembership,
    Permission,
    OrganizationRole,
    TenantMembershipRole,
)
from apps.multitenancy.schema import (
    UpdateTenantActionLoggingMutation,
    DeleteTenantMutation,
    ExportActionLogsMutation,
    CreateOrganizationRoleMutation,
)
from apps.multitenancy.serializers import (
    log_invitation,
    AcceptTenantInvitationSerializer,
    DeclineTenantInvitationSerializer,
    CreateTenantInvitationSerializer,
    ResendTenantInvitationSerializer,
)
from apps.multitenancy.tasks import export_action_logs
from common.action_logging.service import compute_changes, log_request_action
from apps.sso.models import TenantSSOConnection

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization(tenant_factory):
    return tenant_factory(type=TenantType.ORGANIZATION, action_logging_enabled=True)


@pytest.fixture
def activity_request(user, organization, tenant_membership_factory):
    tenant_membership_factory(tenant=organization, user=user, role=TenantUserRole.OWNER)
    return SimpleNamespace(
        user=user, tenant=organization, is_ai_agent_request=False, is_superuser_cross_tenant_access=False
    )


def event(organization, operation):
    return ActionLog.objects.get(tenant=organization, metadata__operation=operation)


@pytest.mark.parametrize(
    'flag,actor', [('is_ai_agent_request', 'AI_AGENT'), ('is_superuser_cross_tenant_access', 'SUPERUSER')]
)
def test_request_actor_retains_user(activity_request, organization, flag, actor):
    setattr(activity_request, flag, True)
    log_request_action(
        activity_request, tenant_id=organization.pk, action_type='UPDATE', entity_type='tenant', entity_id='1'
    )
    log = ActionLog.objects.get(tenant=organization)
    assert log.actor_type == actor
    assert log.actor_user == activity_request.user
    assert log.actor_email == activity_request.user.email


def test_logging_toggle_records_both_transitions(activity_request, organization):
    info = SimpleNamespace(context=activity_request)
    gid = to_global_id('TenantType', str(organization.pk))
    UpdateTenantActionLoggingMutation.mutate(None, info, gid, False)
    UpdateTenantActionLoggingMutation.mutate(None, info, gid, True)
    assert event(organization, 'logging_disabled').changes['action_logging_enabled'] == {'old': True, 'new': False}
    assert event(organization, 'logging_enabled').changes['action_logging_enabled'] == {'old': False, 'new': True}
    UpdateTenantActionLoggingMutation.mutate(None, info, gid, True)
    assert organization.action_logs.count() == 2


@pytest.mark.parametrize(
    'operation,serializer',
    [
        ('invitation_accepted', AcceptTenantInvitationSerializer),
        ('invitation_declined', DeclineTenantInvitationSerializer),
    ],
)
def test_invitation_response_logged(
    activity_request, organization, tenant_membership_factory, serializer, operation, mocker, user_factory
):
    activity_request.user = user_factory()
    membership = tenant_membership_factory(tenant=organization, user=activity_request.user, is_accepted=False)
    mocker.patch('apps.multitenancy.notifications.send_accepted_tenant_invitation_notification')
    mocker.patch('apps.multitenancy.notifications.send_declined_tenant_invitation_notification')
    serializer(context={'request': activity_request}).create({'id': membership.pk})
    log = event(organization, operation)
    assert log.entity_name == activity_request.user.email
    assert log.entity_id == str(membership.pk)
    assert 'token' not in log.metadata
    assert 'role' not in log.metadata
    assert isinstance(log.metadata['roles'], list)


def test_invitation_send_and_resend_logged(activity_request, organization, user_factory, mocker):
    invitee = user_factory()
    mocker.patch('apps.multitenancy.notifications.TenantInvitationEmail.send')
    mocker.patch('apps.multitenancy.notifications.send_tenant_invitation_notification')
    CreateTenantInvitationSerializer(context={'request': activity_request}).create(
        {'email': invitee.email, 'role': TenantUserRole.MEMBER}
    )
    log = event(organization, 'invitation_sent')
    membership = TenantMembership.objects.get_all().get(user=invitee, tenant=organization)
    ResendTenantInvitationSerializer(context={'request': activity_request}).create({'membership': membership})
    assert event(organization, 'invitation_resent').entity_id == log.entity_id


def test_backup_configuration_diff_and_noop(activity_request, organization):
    info = SimpleNamespace(context=activity_request)
    data = {'enabled': True, 'backup_interval_hours': 24, 'retention_days': 7}
    assert UpdateBackupConfigMutation.mutate(None, info, data).ok
    assert event(organization, 'backup_settings_changed').changes['enabled']['new'] is True
    assert UpdateBackupConfigMutation.mutate(None, info, data).ok
    assert organization.action_logs.count() == 1


def test_backup_request_and_restore_request(activity_request, organization, mocker):
    mocker.patch('apps.backup.tasks.create_backup.delay')
    mocker.patch('apps.backup.tasks.restore_backup.delay')
    info = SimpleNamespace(context=activity_request)
    gid = to_global_id('TenantType', str(organization.pk))
    assert TriggerBackupMutation.mutate(None, info, gid).ok
    backup = BackupRecord.objects.create(tenant=organization, status='completed', file_path='test.xml')
    # Use the actual model's status constant rather than an arbitrary label.
    backup.status = BackupRecord.Status.COMPLETED
    backup.save()
    assert RestoreBackupMutation.mutate(None, info, to_global_id('BackupRecordType', str(backup.pk)), 'SKIP', gid).ok
    assert event(organization, 'backup_requested').actor_user == activity_request.user
    assert event(organization, 'restore_requested').metadata['backup_id'] == str(backup.pk)


def test_backup_download_does_not_log_content_and_delete_preserves_id(activity_request, organization, mocker):
    storage = MagicMock()
    storage.open.return_value.__enter__.return_value.read.return_value = b'<backup>private data</backup>'
    mocker.patch('common.storages.get_exports_storage', return_value=storage)
    backup = BackupRecord.objects.create(tenant=organization, file_path='test.xml', is_encrypted=False)
    gid = to_global_id('BackupRecordType', str(backup.pk))
    info = SimpleNamespace(context=activity_request)
    assert DownloadBackupDecryptedMutation.mutate(None, info, gid, '').ok
    assert event(organization, 'backup_downloaded').metadata == {'operation': 'backup_downloaded'}
    pk = str(backup.pk)
    assert DeleteBackupMutation.mutate(None, info, gid, '').ok
    assert event(organization, 'backup_deleted').entity_id == pk


def test_backup_denied_target_creates_no_success_event(activity_request, organization, tenant_factory):
    other_backup = BackupRecord.objects.create(tenant=tenant_factory())
    result = DownloadBackupDecryptedMutation.mutate(
        None, SimpleNamespace(context=activity_request), to_global_id('BackupRecordType', str(other_backup.pk)), ''
    )
    assert result.ok is False
    assert not organization.action_logs.exists()


def test_backup_failure_is_logged_by_system(organization, mocker):
    mocker.patch('apps.backup.tasks.BackupService.generate_xml', side_effect=ValueError('sensitive payload'))
    mocker.patch.object(create_backup, 'retry', side_effect=RuntimeError('retry'))
    with pytest.raises(RuntimeError):
        create_backup.run(str(organization.pk))
    log = event(organization, 'backup_failed')
    assert log.actor_type == 'SYSTEM:scheduled_task'
    assert 'sensitive payload' not in str(log.metadata)


def test_restore_failure_is_logged(organization, mocker):
    backup = BackupRecord.objects.create(tenant=organization, file_path='')
    record = RestoreRecord.objects.create(tenant=organization, backup_record=backup)
    mocker.patch.object(restore_backup, 'retry', side_effect=RuntimeError('retry'))
    with pytest.raises(RuntimeError):
        restore_backup.run(str(backup.pk), str(record.pk), 'SKIP')
    assert event(organization, 'restore_failed').entity_id == str(record.pk)


def test_export_completion_is_logged(activity_request, organization, mocker):
    storage = MagicMock()
    storage.save.return_value = 'exports/test.zip'
    mocker.patch('apps.multitenancy.tasks.get_exports_storage', return_value=storage)
    job = ActionLogExport.objects.create(tenant=organization, requested_by=activity_request.user)
    assert export_action_logs.run(str(job.pk))['status'] == 'completed'
    assert event(organization, 'export_completed').actor_type == 'SYSTEM:scheduled_task'


def test_export_failure_is_logged(activity_request, organization, mocker):
    mocker.patch('apps.multitenancy.tasks.get_exports_storage', side_effect=ValueError('storage unavailable'))
    mocker.patch.object(export_action_logs, 'retry', side_effect=RuntimeError('retry'))
    job = ActionLogExport.objects.create(tenant=organization, requested_by=activity_request.user)
    with pytest.raises(RuntimeError):
        export_action_logs.run(str(job.pk))
    assert event(organization, 'export_failed').metadata['status'] == ActionLogExport.Status.FAILED


def test_default_payment_method_change_is_logged(activity_request, organization, mocker):
    customer = SimpleNamespace(default_payment_method_id='pm_old')
    mocker.patch('apps.finances.serializers.djstripe_models.Customer.get_or_create', return_value=(customer, False))
    mocker.patch('apps.finances.serializers.customers.set_default_payment_method')
    payment_method = SimpleNamespace(pk='pm_new')
    UpdateDefaultPaymentMethodSerializer(context={'request': activity_request}).update(payment_method, {})
    assert event(organization, 'default_payment_method_changed').changes == {
        'default_payment_method': {'old': 'pm_old', 'new': 'pm_new'},
    }


def test_organization_deletion_has_durable_admin_audit(activity_request, organization, mocker):
    mocker.patch('apps.multitenancy.services.deletion.subscriptions.get_schedule', return_value=None)
    mocker.patch('apps.multitenancy.schema.close_old_connections')
    pk = str(organization.pk)
    gid = to_global_id('TenantType', pk)
    DeleteTenantMutation.mutate_and_get_payload(None, SimpleNamespace(context=activity_request), gid, tenant_id=gid)
    audit = LogEntry.objects.get(object_id=pk, action_flag=DELETION)
    assert audit.user == activity_request.user
    assert 'organization_deleted' in audit.change_message
    assert not ActionLog.objects.filter(tenant_id=pk).exists()


def test_sensitive_fields_excluded_from_changes(organization):
    instance = TenantSSOConnection(tenant=organization, name='Identity provider', oidc_client_secret='private value')
    changes = compute_changes(None, instance)
    assert 'oidc_client_secret' not in changes
    assert 'private value' not in str(changes)


def test_crud_create_update_delete_logged(graphene_client, activity_request, organization):
    graphene_client.force_authenticate(activity_request.user)
    graphene_client.set_tenant_dependent_context(organization, TenantUserRole.OWNER)
    tenant_id = to_global_id('TenantType', str(organization.pk))
    created = graphene_client.mutate(
        '''mutation($input: CreateCrudDemoItemMutationInput!) {
      createCrudDemoItem(input: $input) { crudDemoItem { id } }
    }''',
        variable_values={'input': {'tenantId': tenant_id, 'name': 'Original'}},
    )
    assert 'errors' not in created, created
    item_id = created['data']['createCrudDemoItem']['crudDemoItem']['id']
    updated = graphene_client.mutate(
        '''mutation($input: UpdateCrudDemoItemMutationInput!) {
      updateCrudDemoItem(input: $input) { crudDemoItem { name } }
    }''',
        variable_values={'input': {'id': item_id, 'tenantId': tenant_id, 'name': 'Renamed'}},
    )
    assert 'errors' not in updated, updated
    update = organization.action_logs.get(action_type='UPDATE')
    assert update.changes['name'] == {'old': 'Original', 'new': 'Renamed'}
    deleted = graphene_client.mutate(
        '''mutation($input: DeleteCrudDemoItemMutationInput!) {
      deleteCrudDemoItem(input: $input) { deletedIds }
    }''',
        variable_values={'input': {'id': item_id, 'tenantId': tenant_id}},
    )
    assert 'errors' not in deleted, deleted
    assert set(organization.action_logs.values_list('action_type', flat=True)) == {'CREATE', 'UPDATE', 'DELETE'}


def test_backup_completion_is_logged(organization, mocker):
    mocker.patch('apps.backup.tasks.BackupService.generate_xml', return_value='<backup/>')
    encryption = MagicMock()
    encryption.encrypt_backup.return_value = b'encrypted'
    mocker.patch('apps.backup.tasks.get_backup_encryption_service', return_value=encryption)
    storage = MagicMock()
    storage.save.return_value = 'backup.xml'
    mocker.patch('apps.backup.tasks.get_exports_storage', return_value=storage)
    assert create_backup.run(str(organization.pk))['success'] is True
    assert event(organization, 'backup_completed').metadata['status'] == BackupRecord.Status.COMPLETED


@pytest.mark.parametrize('failed,operation', [(0, 'restore_completed'), (1, 'restore_partial')])
def test_restore_outcomes_are_logged(organization, mocker, failed, operation):
    storage = MagicMock()
    storage.open.return_value.__enter__.return_value.read.return_value = b'<backup/>'
    mocker.patch('apps.backup.tasks.get_exports_storage', return_value=storage)
    mocker.patch(
        'apps.backup.restore.RestoreService.restore_from_xml',
        return_value={
            'demo.CrudDemoItem': {'created': 2, 'failed': failed},
        },
    )
    backup = BackupRecord.objects.create(tenant=organization, file_path='backup.xml', is_encrypted=False)
    record = RestoreRecord.objects.create(tenant=organization, backup_record=backup)
    assert restore_backup.run(str(backup.pk), str(record.pk), 'SKIP')['success'] is True
    assert event(organization, operation).metadata['model_counts']['demo.CrudDemoItem']['failed'] == failed


def test_export_request_is_logged(activity_request, organization, mocker):
    mocker.patch('apps.multitenancy.tasks.export_action_logs.delay')
    result = ExportActionLogsMutation.mutate(
        None,
        SimpleNamespace(context=activity_request),
        to_global_id('TenantType', str(organization.pk)),
        search='example',
    )
    assert result.ok
    assert event(organization, 'export_requested').metadata['filters'] == {'search': 'example'}


def test_role_creation_records_granted_permissions(activity_request, organization):
    permission = Permission.objects.get(code='members.view')
    result = CreateOrganizationRoleMutation.mutate(
        None,
        SimpleNamespace(context=activity_request),
        to_global_id('TenantType', str(organization.pk)),
        'Auditor',
        [to_global_id('PermissionType', str(permission.pk))],
        description='Read members',
    )
    assert result.ok
    log = organization.action_logs.get(entity_type='organization_role')
    assert log.changes['permissions'] == {'old': [], 'new': ['members.view']}
    assert log.changes['description']['new'] == 'Read members'


@pytest.mark.parametrize(
    'entity_type',
    [
        'tenant_invitation',
        'backup_config',
        'backup',
        'backup_restore',
        'activity_log_export',
        'crud_item',
    ],
)
def test_new_entity_filters_are_scoped_to_organization(
    graphene_client, activity_request, organization, tenant_factory, entity_type
):
    expected = ActionLog.objects.create(
        tenant=organization, entity_type=entity_type, entity_id='expected', action_type='UPDATE'
    )
    ActionLog.objects.create(tenant=organization, entity_type='tenant', entity_id='other_type', action_type='UPDATE')
    ActionLog.objects.create(
        tenant=organization, entity_type=entity_type, entity_id='other_action', action_type='CREATE'
    )
    ActionLog.objects.create(
        tenant=tenant_factory(), entity_type=entity_type, entity_id='other_org', action_type='UPDATE'
    )
    graphene_client.force_authenticate(activity_request.user)
    graphene_client.set_tenant_dependent_context(organization, TenantUserRole.OWNER)
    response = graphene_client.query(
        '''query($tenantId: ID!, $entityType: String, $actionType: String) {
      allActionLogs(tenantId: $tenantId, entityType: $entityType, actionType: $actionType, first: 20) {
        totalCount edges { node { entityId } }
      }
    }''',
        variable_values={
            'tenantId': to_global_id('TenantType', str(organization.pk)),
            'entityType': entity_type,
            'actionType': 'UPDATE',
        },
    )
    assert 'errors' not in response, response
    result = response['data']['allActionLogs']
    assert result['totalCount'] == 1
    assert result['edges'] == [{'node': {'entityId': expected.entity_id}}]


def test_invitation_roles_snapshot_preserves_custom_names(activity_request, organization, tenant_membership_factory):
    membership = tenant_membership_factory(tenant=organization, user=None, invitee_email_address='invited@example.com')
    custom_role = OrganizationRole.objects.create(tenant=organization, name='Auditor', system_role_type='')
    membership.membership_roles.all().delete()
    TenantMembershipRole.objects.create(membership=membership, role=custom_role)
    log_invitation(activity_request, membership, 'invitation_sent', 'CREATE')
    assert event(organization, 'invitation_sent').metadata['roles'] == [{'name': 'Auditor', 'system_role_type': ''}]
