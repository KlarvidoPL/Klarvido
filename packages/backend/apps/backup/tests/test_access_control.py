"""
Backups may only be used by members of the organization they belong to, holding the backup permission - checked
end to end through the real request path (JWT cookie -> TenantUserRoleMiddleware -> permission classes).
"""

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.backup.models import BackupConfig, BackupRecord, RestoreRecord
from apps.multitenancy.constants import TenantType, TenantUserRole
from common.storages import get_exports_storage

pytestmark = pytest.mark.django_db

DOWNLOAD = '''
    mutation Download($backupId: ID!, $tenantId: ID!) {
      downloadBackupDecrypted(backupId: $backupId, tenantId: $tenantId) { ok content error }
    }
'''
DELETE = '''
    mutation Delete($backupId: ID!, $tenantId: ID!) {
      deleteBackup(backupId: $backupId, tenantId: $tenantId) { ok error }
    }
'''
RESTORE = '''
    mutation Restore($backupId: ID!, $tenantId: ID!) {
      restoreBackup(backupId: $backupId, tenantId: $tenantId, conflictStrategy: SKIP) { ok error restoreId }
    }
'''
TRIGGER = '''
    mutation Trigger($tenantId: ID!) {
      triggerBackup(tenantId: $tenantId) { ok error }
    }
'''
UPDATE_CONFIG = '''
    mutation UpdateConfig($input: BackupConfigInput!) {
      updateBackupConfig(input: $input) { ok error }
    }
'''
BACKUP_XML = b'<?xml version="1.0"?><backup><data/></backup>'


def gid(type_name, obj):
    return to_global_id(type_name, str(obj.pk))


def post(user, query, variables):
    client = APIClient()
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    return client.post("/api/graphql/", {"query": query, "variables": variables}, format="json").json()


def assert_denied(response):
    assert response["errors"][0]["message"] == "permission_denied", response


@pytest.fixture
def owner(user_factory):
    return user_factory()


@pytest.fixture
def outsider(user_factory):
    """Owner of a different organization - backup permissions there, but not in `organization`."""
    return user_factory()


@pytest.fixture
def organization(tenant_factory, tenant_membership_factory, owner):
    tenant = tenant_factory(name="Acme", type=TenantType.ORGANIZATION)
    tenant_membership_factory(tenant=tenant, user=owner, role=TenantUserRole.OWNER)
    return tenant


@pytest.fixture
def other_organization(tenant_factory, tenant_membership_factory, outsider):
    tenant = tenant_factory(name="Other", type=TenantType.ORGANIZATION)
    tenant_membership_factory(tenant=tenant, user=outsider, role=TenantUserRole.OWNER)
    return tenant


@pytest.fixture
def backup(organization):
    file_path = get_exports_storage().save("tenant_backups/acme.xml", ContentFile(BACKUP_XML))
    return BackupRecord.objects.create(
        tenant=organization,
        status=BackupRecord.Status.COMPLETED,
        file_path=file_path,
        file_size=len(BACKUP_XML),
        is_encrypted=False,
    )


class TestDownload:
    def test_member_with_permission_can_download(self, owner, organization, backup):
        response = post(
            owner, DOWNLOAD, {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", organization)}
        )

        assert response["data"]["downloadBackupDecrypted"]["ok"] is True
        assert "<backup>" in response["data"]["downloadBackupDecrypted"]["content"]

    def test_outsider_naming_the_organization_is_denied(self, outsider, other_organization, organization, backup):
        response = post(
            outsider,
            DOWNLOAD,
            {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", organization)},
        )

        assert_denied(response)

    def test_outsider_using_their_own_organization_does_not_find_it(
        self, outsider, other_organization, organization, backup
    ):
        response = post(
            outsider,
            DOWNLOAD,
            {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", other_organization)},
        )

        result = response["data"]["downloadBackupDecrypted"]
        assert result["ok"] is False
        assert result["content"] is None
        assert "not found" in result["error"].lower()

    def test_member_without_backup_permission_is_denied(
        self, user_factory, tenant_membership_factory, organization, backup
    ):
        member = user_factory()
        tenant_membership_factory(tenant=organization, user=member, role=TenantUserRole.MEMBER)

        response = post(
            member, DOWNLOAD, {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", organization)}
        )

        assert_denied(response)


class TestDelete:
    def test_member_with_permission_can_delete(self, owner, organization, backup):
        response = post(
            owner, DELETE, {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", organization)}
        )

        assert response["data"]["deleteBackup"]["ok"] is True
        assert not BackupRecord.objects.filter(pk=backup.pk).exists()

    @pytest.mark.parametrize("use_own_organization", [False, True])
    def test_outsider_cannot_delete(self, outsider, other_organization, organization, backup, use_own_organization):
        tenant = other_organization if use_own_organization else organization
        post(outsider, DELETE, {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", tenant)})

        assert BackupRecord.objects.filter(pk=backup.pk).exists()
        assert get_exports_storage().exists(backup.file_path)


class TestRestore:
    @pytest.mark.parametrize("use_own_organization", [False, True])
    def test_outsider_cannot_restore(
        self, mocker, outsider, other_organization, organization, backup, use_own_organization
    ):
        restore_task = mocker.patch("apps.backup.tasks.restore_backup.delay")
        tenant = other_organization if use_own_organization else organization

        response = post(
            outsider, RESTORE, {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", tenant)}
        )

        assert "errors" in response or response["data"]["restoreBackup"]["ok"] is False
        restore_task.assert_not_called()
        assert not RestoreRecord.objects.exists()

    def test_member_with_permission_can_restore(self, mocker, owner, organization, backup):
        restore_task = mocker.patch("apps.backup.tasks.restore_backup.delay")

        response = post(
            owner, RESTORE, {"backupId": gid("BackupRecordType", backup), "tenantId": gid("TenantType", organization)}
        )

        assert response["data"]["restoreBackup"]["ok"] is True, response
        restore_task.assert_called_once()


class TestTriggerAndConfig:
    def test_outsider_cannot_trigger_a_backup(self, mocker, outsider, other_organization, organization):
        create_task = mocker.patch("apps.backup.tasks.create_backup.delay")

        assert_denied(post(outsider, TRIGGER, {"tenantId": gid("TenantType", organization)}))
        create_task.assert_not_called()

    def test_member_with_permission_can_trigger_a_backup(self, mocker, owner, organization):
        create_task = mocker.patch("apps.backup.tasks.create_backup.delay")

        response = post(owner, TRIGGER, {"tenantId": gid("TenantType", organization)})

        assert response["data"]["triggerBackup"]["ok"] is True
        create_task.assert_called_once_with(tenant_id=str(organization.pk), config_id=None)

    def test_outsider_cannot_change_the_backup_settings(self, outsider, other_organization, organization):
        config = {
            "tenantId": gid("TenantType", organization),
            "enabled": True,
            "backupIntervalHours": 24,
            "retentionDays": 7,
            "emailRecipients": [gid("UserType", outsider)],
        }

        assert_denied(post(outsider, UPDATE_CONFIG, {"input": config}))
        assert not BackupConfig.objects.filter(tenant=organization).exists()
