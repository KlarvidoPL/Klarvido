from unittest.mock import call

import pytest
from django.core.files.base import ContentFile
from graphql_relay import to_global_id

from apps.backup.encryption import BackupEncryptionService
from apps.backup.models import BackupRecord
from apps.notifications.models import Notification
from common.storages import get_exports_storage

from ..constants import Notification as NotificationType, TenantType, TenantUserRole
from ..models import ActionLogExport, ResourceCleanup
from ..tasks import delete_tenant_files

pytestmark = pytest.mark.django_db

MUTATION = '''
    mutation DeleteTenant($input: DeleteTenantMutationInput!) {
      deleteTenant(input: $input) {
        deletedIds
      }
    }
'''


def delete_tenant(graphene_client, user, tenant):
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
    tenant_global_id = to_global_id("TenantType", tenant.id)
    return graphene_client.mutate(
        MUTATION, variable_values={"input": {"id": tenant_global_id, "tenantId": tenant_global_id}}
    )


@pytest.fixture(autouse=True)
def keep_test_connection(mocker):
    # The mutation's close_old_connections() would close the test's transaction-wrapped connection, dropping the
    # on_commit callbacks under test (in a real request the delete commits - and they run - before it's called)
    mocker.patch("apps.multitenancy.schema.close_old_connections")


@pytest.fixture
def email_mock(mocker):
    return mocker.patch("apps.multitenancy.notifications.TenantDeletedEmail")


@pytest.fixture
def delete_files_mock(mocker):
    return mocker.patch("apps.multitenancy.cleanup.current_app.send_task")


class TestTenantDeletedNotifications:
    def test_members_are_told_and_the_deleter_gets_a_confirmation(
        self,
        graphene_client,
        user,
        user_factory,
        tenant_factory,
        tenant_membership_factory,
        email_mock,
        delete_files_mock,
        django_capture_on_commit_callbacks,
    ):
        tenant = tenant_factory(name="Acme", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        member = user_factory()
        tenant_membership_factory(tenant=tenant, user=member, role=TenantUserRole.MEMBER)
        invited = user_factory()
        tenant_membership_factory(tenant=tenant, user=invited, role=TenantUserRole.MEMBER, is_accepted=False)

        with django_capture_on_commit_callbacks(execute=True):
            executed = delete_tenant(graphene_client, user, tenant)

        assert "errors" not in executed, executed
        # In-app: only the other (accepted) members - not the deleter, not a pending invitation
        notifications = Notification.objects.filter(type=NotificationType.TENANT_DELETED.value)
        assert [notification.user for notification in notifications] == [member]
        assert notifications[0].issuer == user
        assert notifications[0].data["tenant_name"] == "Acme"
        # Email: the member gets a heads-up, the deleter a confirmation
        deleted_by = str(user.profile) or str(user)
        email_mock.assert_has_calls(
            [
                call(member, data={"tenant_name": "Acme", "deleted_by": deleted_by, "is_deleter": False}),
                call().send(),
                call(user, data={"tenant_name": "Acme", "deleted_by": deleted_by, "is_deleter": True}),
                call().send(),
            ]
        )
        assert email_mock.call_count == 2

    def test_files_are_queued_for_deletion(
        self,
        graphene_client,
        user,
        tenant_factory,
        tenant_membership_factory,
        email_mock,
        delete_files_mock,
        django_capture_on_commit_callbacks,
    ):
        tenant = tenant_factory(name="Acme", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        BackupRecord.objects.create(tenant=tenant, file_path="backups/acme.xml.enc")
        BackupRecord.objects.create(tenant=tenant, file_path="")  # still pending, no file yet
        ActionLogExport.objects.create(tenant=tenant, requested_by=user, file_path="exports/acme-logs.zip")
        tenant_pk = str(tenant.pk)  # cleared on the instance by the delete

        with django_capture_on_commit_callbacks(execute=True):
            delete_tenant(graphene_client, user, tenant)

        jobs = ResourceCleanup.objects.filter(organization_id=tenant_pk)
        assert set(jobs.values_list('resource_type', 'resource_path')) == {
            (ResourceCleanup.ResourceType.EXPORT_FILE, 'backups/acme.xml.enc'),
            (ResourceCleanup.ResourceType.EXPORT_FILE, 'exports/acme-logs.zip'),
            (ResourceCleanup.ResourceType.BACKUP_KEY, ''),
            (ResourceCleanup.ResourceType.EXPORT_PREFIX, f'tenant_backups/{tenant_pk}/'),
            (ResourceCleanup.ResourceType.EXPORT_PREFIX, f'action_logs/{tenant_pk}/'),
            (ResourceCleanup.ResourceType.DOCUMENT_PREFIX, f'documents/organizations/{tenant_pk}/'),
        }
        assert delete_files_mock.call_count == 6
        for job in jobs:
            assert (
                call('apps.multitenancy.tasks.process_resource_cleanup', args=[str(job.pk)], retry=False)
                in delete_files_mock.call_args_list
            )

    def test_nothing_happens_when_the_delete_is_refused(
        self,
        graphene_client,
        user,
        user_factory,
        tenant_factory,
        tenant_membership_factory,
        email_mock,
        delete_files_mock,
        django_capture_on_commit_callbacks,
    ):
        tenant = tenant_factory(name="Personal", type=TenantType.DEFAULT)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership_factory(tenant=tenant, user=user_factory(), role=TenantUserRole.MEMBER)

        with django_capture_on_commit_callbacks(execute=True):
            executed = delete_tenant(graphene_client, user, tenant)

        assert "errors" in executed
        assert not ResourceCleanup.objects.exists()
        assert not Notification.objects.filter(type=NotificationType.TENANT_DELETED.value).exists()
        email_mock.assert_not_called()
        delete_files_mock.assert_not_called()


class TestDeleteTenantFilesTask:
    def test_deletes_files_and_tolerates_missing_ones(self, mocker):
        key_mock = mocker.patch("apps.multitenancy.cleanup.get_backup_encryption_service")
        storage = get_exports_storage()
        backup_path = storage.save("backups/acme.xml.enc", ContentFile(b"encrypted"))
        export_path = storage.save("exports/acme-logs.zip", ContentFile(b"zip"))

        delete_tenant_files([backup_path, export_path, "exports/already-gone.zip"], "tenant-1")

        assert not storage.exists(backup_path)
        assert not storage.exists(export_path)
        key_mock.return_value.delete_tenant_key.assert_called_once_with("tenant-1", strict=True)


class TestDeleteTenantKey:
    def test_deletes_the_secrets_manager_key(self, mocker):
        service = BackupEncryptionService()
        service.secrets_service = mocker.Mock()
        service.secrets_service.delete_secret_by_name.return_value = True

        assert service.delete_tenant_key("tenant-1") is True
        service.secrets_service.delete_secret_by_name.assert_called_once_with("tenant-1", "encryption_key", force=True)

    def test_nothing_to_delete_without_secrets_manager(self, mocker):
        service = BackupEncryptionService()
        service.secrets_service = mocker.Mock(client=None)

        assert service.delete_tenant_key("tenant-1") is False
        service.secrets_service.delete_secret_by_name.assert_not_called()
