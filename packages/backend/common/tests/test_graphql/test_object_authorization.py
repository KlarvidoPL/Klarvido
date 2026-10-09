"""End-to-end authorization regressions using synthetic customer data."""

from types import SimpleNamespace

import pytest
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from graphql import GraphQLError

from apps.demo.models import CrudDemoItem, DocumentDemoItem
from apps.notifications.models import Notification
from apps.multitenancy.constants import TenantUserRole, TenantType
from apps.multitenancy.models import ActionLogExport, OrganizationRole
from common.graphql.acl import permission_classes, requires, permission_required
from common.graphql.acl.decorators import RBACPermission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def production_settings(settings):
    settings.DEBUG = False


def execute(user, query, variables=None):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client.post('/api/graphql/', {'query': query, 'variables': variables or {}}, format='json').json()


def node(user, type_name, obj, fields):
    return execute(
        user,
        'query($id: ID!) { node(id: $id) { ... on ' + type_name + ' { ' + fields + ' } } }',
        {'id': to_global_id(type_name, str(obj.pk))},
    )


@pytest.mark.parametrize(
    'resource', ['profile', 'notification', 'document', 'crud', 'export', 'role', 'backup', 'billing']
)
@pytest.mark.parametrize('access', ['foreign', 'owner', 'pending', 'member', 'anonymous'])
def test_node_access(resource, access, user_factory, tenant_factory, tenant_membership_factory, mocker):
    from apps.backup.models import BackupRecord
    from apps.finances.tests.factories import PaymentMethodFactory, CustomerFactory

    owner = user_factory()
    attacker = user_factory()
    tenant = tenant_factory()
    tenant_membership_factory(user=owner, tenant=tenant, role=TenantUserRole.OWNER)
    if access in {'pending', 'member'}:
        tenant_membership_factory(
            user=attacker, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=access == 'member'
        )
    requester = owner if access == 'owner' else None if access == 'anonymous' else attacker
    download_resolver = None
    if resource == 'profile':
        obj, kind, fields = owner.profile, 'UserProfileType', 'email'
    elif resource == 'notification':
        obj = Notification.objects.create(user=owner, type='security_test', data={'private': 'synthetic'})
        kind, fields = 'NotificationType', 'data'
    elif resource == 'document':
        obj = DocumentDemoItem.objects.create(created_by=owner, tenant=tenant, file='documents/synthetic.txt')
        kind, fields = 'DocumentDemoItemType', 'file { url }'
    elif resource == 'crud':
        obj = CrudDemoItem.objects.create(tenant=tenant, created_by=owner, name='Synthetic confidential item')
        kind, fields = 'CrudDemoItemType', 'name'
    elif resource == 'export':
        obj = ActionLogExport.objects.create(tenant=tenant, requested_by=owner, status='COMPLETED')
        download_resolver = mocker.patch.object(
            ActionLogExport, 'get_download_url', return_value='https://synthetic.invalid/export'
        )
        kind, fields = 'ActionLogExportType', 'downloadUrl'
    elif resource == 'role':
        obj = OrganizationRole.objects.filter(tenant=tenant).first()
        kind, fields = 'OrganizationRoleType', 'name'
    elif resource == 'backup':
        obj = BackupRecord.objects.create(tenant=tenant)
        download_resolver = mocker.patch.object(
            BackupRecord, 'get_download_url', return_value='https://synthetic.invalid/backup'
        )
        kind, fields = 'BackupRecordType', 'downloadUrl'
    else:
        obj = PaymentMethodFactory(customer=CustomerFactory(subscriber=tenant))
        kind, fields = 'StripePaymentMethodType', 'billingDetails'
    result = node(requester, kind, obj, fields)
    allowed = access == 'owner' or (access == 'member' and resource in {'crud', 'role', 'document'})
    if allowed:
        assert not result.get('errors'), result
        assert result['data']['node'] is not None, result
    else:
        assert result.get('data', {}).get('node') is None, result
        if download_resolver is not None:
            download_resolver.assert_not_called()


@pytest.mark.parametrize('operation', ['export', 'logging'])
@pytest.mark.parametrize('access', ['foreign', 'owner', 'pending', 'member', 'anonymous'])
def test_audit_mutations_authorize_before_side_effects(
    operation, access, user_factory, tenant_factory, tenant_membership_factory, mocker
):
    owner = user_factory()
    outsider = user_factory()
    tenant = tenant_factory(action_logging_enabled=True)
    tenant_membership_factory(user=owner, tenant=tenant, role=TenantUserRole.OWNER)
    if access in {'member', 'pending'}:
        tenant_membership_factory(
            user=outsider, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=access == 'member'
        )
    user = owner if access == 'owner' else None if access == 'anonymous' else outsider
    dispatch = mocker.patch('apps.multitenancy.tasks.export_action_logs.delay')
    field = 'exportActionLogs' if operation == 'export' else 'updateTenantActionLogging'
    arguments = 'tenantId: $tenant' + (', enabled: false' if operation == 'logging' else '')
    result = execute(
        user,
        'mutation($tenant: ID!) { ' + field + '(' + arguments + ') { ok } }',
        {'tenant': to_global_id('TenantType', str(tenant.pk))},
    )
    tenant.refresh_from_db()
    if access == 'owner':
        assert not result.get('errors'), result
        assert result['data'][field]['ok']
        if operation == 'export':
            assert ActionLogExport.objects.filter(tenant=tenant, requested_by=owner).exists()
            dispatch.assert_called_once()
        else:
            assert not tenant.action_logging_enabled
    else:
        assert result.get('errors'), result
        assert tenant.action_logging_enabled
        assert not ActionLogExport.objects.filter(tenant=tenant).exists()
        dispatch.assert_not_called()


def test_sibling_query_cannot_read_foreign_role(user, tenant_factory, tenant_membership_factory):
    own, foreign = tenant_factory(), tenant_factory()
    tenant_membership_factory(user=user, tenant=own, role=TenantUserRole.OWNER)
    role = OrganizationRole.objects.create(tenant=foreign, name='Foreign role')
    result = execute(
        user,
        '''query($tenant: ID!, $role: ID!) {
        allOrganizationRoles(tenantId: $tenant) { edges { node { id } } }
        organizationRole(id: $role) { name }
    }''',
        {'tenant': to_global_id('TenantType', str(own.pk)), 'role': to_global_id('OrganizationRoleType', str(role.pk))},
    )
    assert result['data']['organizationRole'] is None, result
    assert result['data']['allOrganizationRoles'] is not None, result


def test_nested_download_requires_permission(user, tenant_factory, tenant_membership_factory, mocker):
    from common.graphql.authorization import ObjectAuthorizationMiddleware
    from apps.multitenancy.schema import ActionLogExportType

    tenant = tenant_factory()
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.MEMBER)
    export = ActionLogExport.objects.create(tenant=tenant, requested_by=user)
    resolver = mocker.Mock()
    info = SimpleNamespace(
        context=SimpleNamespace(user=user),
        parent_type=SimpleNamespace(graphene_type=ActionLogExportType),
        field_name='downloadUrl',
        path=SimpleNamespace(prev='export'),
    )
    with pytest.raises(GraphQLError, match='permission_denied'):
        ObjectAuthorizationMiddleware().resolve(resolver, export, info)
    resolver.assert_not_called()


def test_missing_tenant_permissions_fail_closed(user):
    info = SimpleNamespace(context=SimpleNamespace(user=user, tenant=None))
    assert not requires('security.logs.export')().has_permission(info.context, None)
    assert not RBACPermission(['security.logs.export']).has_permission(info.context, None)
    with pytest.raises(GraphQLError, match='permission'):
        permission_required('security.logs.export')(lambda root, info: True)(None, info)


def test_stacked_permissions_all_execute(mocker):
    calls = []

    class First(BasePermission):
        def has_permission(self, request, view):
            calls.append('first')
            return True

    class Second(BasePermission):
        def has_permission(self, request, view):
            calls.append('second')
            return False

    resolver = mocker.Mock()
    wrapped = permission_classes(Second)(permission_classes(First)(lambda root, info: resolver()))
    with pytest.raises(PermissionDenied, match='permission_denied'):
        wrapped(None, SimpleNamespace(context=SimpleNamespace(user=SimpleNamespace(is_authenticated=True))))
    assert calls == ['first', 'second']
    resolver.assert_not_called()


def test_public_queries_remain_public():
    result = execute(None, '{ availableLocales { code } allTenants { edges { node { id } } } }')
    assert not result.get('errors'), result


@pytest.mark.parametrize('access', ['foreign', 'pending', 'member', 'revoked'])
def test_queued_export_requires_current_authorization(access, user, tenant_factory, tenant_membership_factory, mocker):
    from apps.multitenancy.tasks import export_action_logs

    tenant = tenant_factory()
    if access != 'foreign':
        membership = tenant_membership_factory(
            user=user,
            tenant=tenant,
            role=TenantUserRole.OWNER if access == 'revoked' else TenantUserRole.MEMBER,
            is_accepted=access != 'pending',
        )
        if access == 'revoked':
            membership.delete()
    job = ActionLogExport.objects.create(tenant=tenant, requested_by=user)
    storage = mocker.patch('apps.multitenancy.tasks.get_exports_storage')
    result = export_action_logs.run(str(job.pk))
    job.refresh_from_db()
    assert result == {'error': 'permission_denied'}
    assert job.status == ActionLogExport.Status.FAILED
    storage.assert_not_called()
    assert not Notification.objects.filter(user=user, type='ACTION_LOG_EXPORT_READY').exists()


def test_unassigned_legacy_documents_are_not_exposed(user, tenant_factory, tenant_membership_factory):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    DocumentDemoItem.objects.create(created_by=user, file='documents/legacy.txt')
    result = execute(
        user,
        'query($tenantId: ID!) { allDocumentDemoItems(tenantId: $tenantId) { edges { node { id } } } }',
        {'tenantId': to_global_id('TenantType', tenant.pk)},
    )
    assert not result.get('errors'), result
    assert result['data']['allDocumentDemoItems']['edges'] == []


def test_class_and_field_permissions_accumulate():
    import graphene

    calls = []

    class FieldPermission(BasePermission):
        def has_permission(self, request, view):
            calls.append('field')
            return True

    class ClassPermission(BasePermission):
        def has_permission(self, request, view):
            calls.append('class')
            return False

    @permission_classes(ClassPermission)
    class Query(graphene.ObjectType):
        secret = permission_classes(FieldPermission)(
            graphene.Field(graphene.String, resolver=lambda root, info: 'secret')
        )

    result = graphene.Schema(query=Query).execute(
        '{ secret }', context_value=SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
    )
    assert result.data == {'secret': None}
    assert result.errors[0].message == 'permission_denied'
    assert calls == ['field', 'class']


def test_tenant_authorization_cache_isolated_by_operation_and_root_field(
    user, tenant_factory, tenant_membership_factory
):
    from graphql.pyutils import Path
    from common.graphql.authorization import tenant_ids

    tenant = tenant_factory()
    membership = tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    info = SimpleNamespace(context=SimpleNamespace(user=user), operation=object(), path=Path(None, 'first', None))
    assert tenant.pk in tenant_ids(info, 'security.logs.export')
    membership.delete()
    info.path = Path(None, 'second', None)
    assert tenant.pk not in tenant_ids(info, 'security.logs.export')
    info.operation = object()
    info.path = Path(None, 'first', None)
    assert tenant.pk not in tenant_ids(info, 'security.logs.export')


def test_unprotected_type_cannot_bypass_nested_authorization(user, tenant_factory):
    import graphene
    from graphene_django import DjangoObjectType
    from common.graphql.authorization import ObjectAuthorizationMiddleware

    export = ActionLogExport.objects.create(tenant=tenant_factory(), requested_by=user)

    class UnprotectedExportType(DjangoObjectType):
        class Meta:
            model = ActionLogExport
            fields = ('id', 'filters')

    class Query(graphene.ObjectType):
        export = graphene.Field(UnprotectedExportType, resolver=lambda root, info: export)

    result = graphene.Schema(query=Query).execute(
        '{ export { filters } }', context_value=SimpleNamespace(user=user), middleware=[ObjectAuthorizationMiddleware()]
    )
    assert result.errors
    assert result.errors[0].message == 'permission_denied'
    assert result.data in [{'export': None}, {'export': {'filters': None}}]
