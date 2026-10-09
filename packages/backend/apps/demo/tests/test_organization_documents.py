import importlib

import pytest
from django.apps import apps
from django.db import connection, transaction
from graphql_relay import to_global_id

from apps.backup.registry import BackupModelRegistry
from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import ActionLog
from ..models import DocumentDemoItem
from ..tasks import delete_document_file

pytestmark = pytest.mark.django_db


def test_organization_documents_are_shared_and_other_organizations_are_excluded(
    graphene_client, user, user_factory, tenant_factory, tenant_membership_factory, document_demo_item_factory
):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.MEMBER)
    shared = document_demo_item_factory(tenant=tenant, created_by=user_factory())
    document_demo_item_factory(tenant=tenant_factory(), created_by=user)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
    graphene_client.force_authenticate(user)
    result = graphene_client.query(
        'query($tenantId: ID!) { allDocumentDemoItems(tenantId: $tenantId) { edges { node { id } } } }',
        variable_values={'tenantId': to_global_id('TenantType', tenant.pk)},
    )
    assert not result.get('errors'), result
    assert result['data']['allDocumentDemoItems']['edges'] == [
        {'node': {'id': to_global_id('DocumentDemoItemType', shared.pk)}}
    ]


def test_document_manager_can_delete_another_members_document_and_logs_it(
    graphene_client, user, user_factory, tenant_factory, tenant_membership_factory, document_demo_item_factory
):
    tenant = tenant_factory(type=TenantType.ORGANIZATION, action_logging_enabled=True)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    document = document_demo_item_factory(tenant=tenant, created_by=user_factory())
    pk = str(document.pk)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
    graphene_client.force_authenticate(user)
    result = graphene_client.mutate(
        'mutation($input: DeleteDocumentDemoItemMutationInput!) { deleteDocumentDemoItem(input: $input) { deletedIds } }',
        variable_values={
            'input': {'id': to_global_id('DocumentDemoItemType', pk), 'tenantId': to_global_id('TenantType', tenant.pk)}
        },
    )
    assert not result.get('errors'), result
    assert not DocumentDemoItem.objects.filter(pk=pk).exists()
    assert ActionLog.objects.filter(
        tenant=tenant, entity_type='document', entity_id=pk, action_type='DELETE', actor_user=user
    ).exists()


def test_organization_deletion_queues_document_file_cleanup_after_commit(
    tenant_factory, document_demo_item_factory, mocker, django_capture_on_commit_callbacks
):
    tenant = tenant_factory()
    document = document_demo_item_factory(tenant=tenant)
    other = document_demo_item_factory(tenant=tenant_factory())
    path = document.file.name
    cleanup = mocker.patch('apps.demo.signals.delete_document_file.delay')
    with django_capture_on_commit_callbacks(execute=True):
        tenant.delete()
        cleanup.assert_not_called()
    cleanup.assert_called_once_with(path)
    assert not DocumentDemoItem.objects.filter(pk=document.pk).exists()
    assert DocumentDemoItem.objects.filter(pk=other.pk).exists()


def test_rolled_back_deletion_does_not_remove_document_file(
    document_demo_item_factory, mocker, django_capture_on_commit_callbacks
):
    document = document_demo_item_factory()
    pk = document.pk
    cleanup = mocker.patch('apps.demo.signals.delete_document_file.delay')
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError), transaction.atomic():
            document.delete()
            raise RuntimeError('rollback')
    assert DocumentDemoItem.objects.filter(pk=pk).exists()
    cleanup.assert_not_called()


def test_document_cleanup_uses_document_storage(mocker):
    storage = mocker.patch.object(DocumentDemoItem._meta.get_field('file'), 'storage')
    delete_document_file.run('documents/example.txt')
    storage.delete.assert_called_once_with('documents/example.txt')


def test_documents_are_included_in_organization_backup_registry():
    assert DocumentDemoItem in BackupModelRegistry.get_all_models()


@pytest.mark.parametrize('organization_count', [0, 1, 2])
def test_legacy_documents_are_assigned_only_to_a_sole_accepted_organization(
    organization_count, user, tenant_factory, tenant_membership_factory, document_demo_item_factory
):
    document = document_demo_item_factory(created_by=user)
    tenants = [tenant_factory(type=TenantType.ORGANIZATION) for _ in range(organization_count)]
    for tenant in tenants:
        tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.MEMBER)
    tenant_membership_factory(user=user, tenant=tenant_factory(type=TenantType.ORGANIZATION), is_accepted=False)
    migration = importlib.import_module('apps.demo.migrations.0004_organization_documents')
    with connection.schema_editor(atomic=False) as editor:
        migration.assign_existing_documents(apps, editor)
    document.refresh_from_db()
    assert document.tenant_id == (tenants[0].pk if organization_count == 1 else None)
