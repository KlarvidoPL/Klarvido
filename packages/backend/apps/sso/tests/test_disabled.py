"""Regression tests for the enterprise SSO/SCIM shutdown boundary."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib import admin
from django.core.cache import cache
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.multitenancy.constants import SystemRoleType, TenantUserRole
from apps.multitenancy.middleware import get_current_tenant_with_membership_check
from apps.multitenancy.models import (
    OrganizationRole,
    OrganizationRolePermission,
    Permission,
    TenantMembershipRole,
    get_user_permissions_for_tenant,
    user_has_permission,
)
from apps.notifications.models import Notification
from apps.notifications.sender import send_notification
from apps.notifications.services import NotificationService
from apps.sso.models import SCIMToken, SSOUserLink, TenantSSOConnection
from apps.sso.tests.factories import SSOSessionFactory, TenantSSOConnectionFactory
from apps.users.authentication import JSONWebTokenChannelsAuthentication
from config.schema import schema

pytestmark = pytest.mark.django_db

ENTERPRISE_PATHS = [
    'saml/connection/metadata',
    'saml/connection/login',
    'saml/connection/acs',
    'saml/connection/slo',
    'oidc/connection/login',
    'oidc/connection/callback',
    'scim/v2/Users',
    'scim/v2/Users/user',
    'scim/v2/Groups',
    'scim/v2/Groups/group',
]


@pytest.mark.parametrize('path', ENTERPRISE_PATHS)
@pytest.mark.parametrize('authenticated', [False, True])
@pytest.mark.parametrize('method', ['get', 'post'])
def test_enterprise_endpoints_are_unavailable(path, authenticated, method, user):
    client = APIClient()
    if authenticated:
        client.force_authenticate(user)
    response = getattr(client, method)(f'/api/sso/{path}')
    assert response.status_code == 404


@pytest.mark.parametrize('type_name', ['SSOConnectionType', 'SCIMTokenType', 'SSODiscoveryResultType'])
def test_enterprise_graphql_types_are_unavailable(type_name):
    assert schema.graphql_schema.get_type(type_name) is None


def test_enterprise_graphql_fields_are_unavailable():
    query = schema.graphql_schema.query_type.fields
    mutation = schema.graphql_schema.mutation_type.fields
    assert not {'ssoDiscover', 'ssoConnections', 'ssoConnection', 'scimTokens'} & query.keys()
    assert (
        not {
            'createSsoConnection',
            'updateSsoConnection',
            'deleteSsoConnection',
            'activateSsoConnection',
            'deactivateSsoConnection',
            'testSsoConnection',
            'createScimToken',
            'revokeScimToken',
        }
        & mutation.keys()
    )
    assert {'myPasskeys', 'mySessions', 'myDevices', 'ssoAuditLogs'} <= query.keys()
    assert {'revokeSession', 'revokeAllSessions', 'deletePasskey'} <= mutation.keys()


@pytest.mark.parametrize('type_name', ['SSOConnectionType', 'SCIMTokenType'])
def test_enterprise_relay_nodes_are_unavailable(type_name, graphene_client, user, tenant):
    connection = TenantSSOConnectionFactory(tenant=tenant, status='active')
    token, _ = SCIMToken.create_for_tenant(tenant=tenant, name='Legacy', sso_connection=connection)
    pk = connection.pk if type_name == 'SSOConnectionType' else token.pk
    graphene_client.force_authenticate(user)
    result = graphene_client.query(
        'query($id: ID!) { node(id: $id) { id } }',
        variable_values={'id': to_global_id(type_name, pk)},
    )
    assert result.get('errors') or result['data']['node'] is None


@pytest.mark.parametrize('transport', ['header', 'cookie', 'websocket', 'refresh'])
def test_existing_sso_tokens_are_rejected(transport, user):
    refresh = RefreshToken.for_user(user)
    refresh['auth_method'] = 'sso'
    access = str(refresh.access_token)
    client = APIClient()
    if transport == 'websocket':
        scope = {'headers': [(b'cookie', f'{settings.ACCESS_TOKEN_COOKIE}={access}'.encode())]}
        assert JSONWebTokenChannelsAuthentication().authenticate(scope) is None
    elif transport == 'refresh':
        response = client.post('/api/auth/token-refresh/', {'refresh': str(refresh)}, format='json')
        assert response.status_code == 401
    else:
        if transport == 'header':
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        else:
            client.cookies[settings.ACCESS_TOKEN_COOKIE] = access
        response = client.post('/api/graphql/', {'query': 'query { currentUser { email } }'}, format='json')
        assert response.status_code == 401 or response.json().get('data', {}).get('currentUser') is None


@pytest.mark.parametrize('auth_method', ['password', 'oauth', 'passkey', None])
def test_supported_tokens_and_refresh_still_work(auth_method, user):
    refresh = RefreshToken.for_user(user)
    if auth_method:
        refresh['auth_method'] = auth_method
    SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    response = client.post('/api/graphql/', {'query': 'query { currentUser { email } }'}, format='json')
    assert response.json()['data']['currentUser']['email'] == user.email
    response = APIClient().post('/api/auth/token-refresh/', {'refresh': str(refresh)}, format='json')
    assert response.status_code == 200
    assert response.json() == {'success': True}
    rotated = response.cookies[settings.REFRESH_TOKEN_COOKIE].value
    assert RefreshToken(rotated).get('auth_method', 'password') == (auth_method or 'password')


def test_legacy_enforcement_no_longer_blocks_members(user, tenant, tenant_membership_factory):
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True)
    TenantSSOConnectionFactory(
        tenant=tenant,
        status='active',
        enforce_sso=True,
        allowed_domains=[user.email.rsplit('@', 1)[-1]],
    )
    request = SimpleNamespace(auth={'auth_method': 'password'})
    assert get_current_tenant_with_membership_check(tenant.pk, user, request) == tenant


@pytest.fixture
def legacy_sso_permission():
    permission, _ = Permission.objects.get_or_create(
        code='security.sso.manage',
        defaults={'name': 'Manage SSO', 'category': 'SECURITY', 'description': 'Legacy SSO'},
    )
    return permission


def test_dormant_permission_is_filtered_from_cached_and_owner_permissions(
    user,
    tenant,
    tenant_membership_factory,
    legacy_sso_permission,
):
    membership = tenant_membership_factory(user=user, tenant=tenant, is_accepted=True)
    owner = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)
    TenantMembershipRole.objects.get_or_create(membership=membership, role=owner)
    key = f'user_permissions:{user.id}:{tenant.id}'
    cache.delete(key)
    assert 'security.sso.manage' not in get_user_permissions_for_tenant(user, tenant)
    cache.set(key, {'security.sso.manage', 'security.logs.view', 'security.*'}, 300)
    assert get_user_permissions_for_tenant(user, tenant) == {'security.logs.view', 'security.*'}
    assert not user_has_permission(user, tenant, 'security.sso.manage')
    assert not owner.has_permission('security.sso.manage')
    cache.delete(key)


def test_dormant_permission_is_absent_from_catalog_roles_and_relay(
    graphene_client,
    user,
    tenant,
    legacy_sso_permission,
    tenant_membership_factory,
):
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True)
    role = OrganizationRole.objects.create(tenant=tenant, name='Legacy role')
    OrganizationRolePermission.objects.create(role=role, permission=legacy_sso_permission)
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
    result = graphene_client.query('query { allPermissions { edges { node { code } } } }')
    assert not result.get('errors')
    assert 'security.sso.manage' not in [edge['node']['code'] for edge in result['data']['allPermissions']['edges']]
    result = graphene_client.query(
        'query($id: ID!) { organizationRole(id: $id) { permissions { code } } }',
        variable_values={'id': to_global_id('OrganizationRoleType', role.pk)},
    )
    assert not result.get('errors')
    assert result['data']['organizationRole']['permissions'] == []
    result = graphene_client.query(
        'query($id: ID!) { node(id: $id) { id } }',
        variable_values={'id': to_global_id('PermissionType', legacy_sso_permission.pk)},
    )
    assert result.get('errors') or result['data']['node'] is None


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_dormant_permission_cannot_be_assigned(
    operation, graphene_client, user, tenant, legacy_sso_permission, tenant_membership_factory
):
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
    membership = tenant_membership_factory(user=user, tenant=tenant, is_accepted=True)
    owner = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)
    TenantMembershipRole.objects.get_or_create(membership=membership, role=owner)
    role = OrganizationRole.objects.create(tenant=tenant, name='Editable role')
    inputs = {
        'tenantId': to_global_id('TenantType', tenant.pk),
        'permissionIds': [to_global_id('PermissionType', legacy_sso_permission.pk)],
    }
    if operation == 'create':
        inputs['name'] = 'New role'
    else:
        inputs['id'] = to_global_id('OrganizationRoleType', role.pk)
    # The repository's role mutations use ordinary arguments, not serializer input objects.
    arguments = 'tenantId: $tenantId, permissionIds: $permissionIds'
    variables = '$tenantId: ID!, $permissionIds: [ID]!'
    if operation == 'create':
        variables += ', $name: String!'
        arguments += ', name: $name'
    else:
        variables += ', $id: ID!'
        arguments += ', id: $id'
    query = f'mutation({variables}) {{ {operation}OrganizationRole({arguments}) {{ role {{ id }} }} }}'
    result = graphene_client.mutate(query, variable_values=inputs)
    assert result.get('errors')
    assert any('not available' in str(error) for error in result['errors'])
    assert not role.permissions.exists()


def test_enterprise_admin_models_are_unregistered():
    for model in (TenantSSOConnection, SCIMToken, SSOUserLink):
        assert not admin.site.is_registered(model)


def test_sso_notifications_are_not_created_or_counted(user, tenant):
    with patch('apps.notifications.sender.get_enabled_strategies') as strategies:
        send_notification(user, 'SSO_CONNECTION_ACTIVATED', {'connection_name': 'Old'}, None)
        strategies.assert_not_called()
    Notification._base_manager.create(user=user, type='SSO_CONNECTION_ACTIVATED', data={})
    Notification.objects.create(user=user, type='PASSKEY_REGISTERED', data={})
    assert Notification._base_manager.filter(user=user).count() == 2
    assert Notification.objects.filter_by_user(user).count() == 1
    assert NotificationService.get_unread_notifications_count(user) == 1
    assert NotificationService.user_has_unread_notifications(user)
    with patch('apps.notifications.sender.send_notification') as notify:
        TenantSSOConnectionFactory(tenant=tenant, status='active')
        notify.assert_not_called()


def test_legacy_role_can_be_edited_without_reassigning_sso(
    graphene_client,
    user,
    tenant,
    tenant_membership_factory,
    legacy_sso_permission,
):
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True)
    supported = Permission.objects.get(code='security.logs.view')
    role = OrganizationRole.objects.create(tenant=tenant, name='Legacy editor')
    OrganizationRolePermission.objects.create(role=role, permission=legacy_sso_permission)
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
    result = graphene_client.mutate(
        '''mutation($id: ID!, $tenantId: ID!, $permissionIds: [ID]) {
            updateOrganizationRole(id: $id, tenantId: $tenantId, permissionIds: $permissionIds) {
                ok role { permissions { code } }
            }
        }''',
        variable_values={
            'id': to_global_id('OrganizationRoleType', role.pk),
            'tenantId': to_global_id('TenantType', tenant.pk),
            'permissionIds': [to_global_id('PermissionType', supported.pk)],
        },
    )
    assert not result.get('errors')
    assert result['data']['updateOrganizationRole']['ok']
    assert result['data']['updateOrganizationRole']['role']['permissions'] == [{'code': 'security.logs.view'}]
    # Preserve the old assignment for future review, but keep it dormant.
    assert role.permissions.filter(pk=legacy_sso_permission.pk).exists()
