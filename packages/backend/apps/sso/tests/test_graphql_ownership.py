"""Security regressions for Relay lookups and manually resolved SSO objects."""

import json
from types import SimpleNamespace

import graphene
import pytest
from graphene_django import DjangoObjectType
from graphql_relay import to_global_id
from rest_framework.test import APIClient

from apps.multitenancy.constants import TenantUserRole
from apps.multitenancy.models import OrganizationRole
from apps.sso.models import UserPasskey
from common.graphql.authorization import ObjectAuthorizationMiddleware
from .factories import SSOSessionFactory, UserDeviceFactory, UserPasskeyFactory, SSOAuditLogFactory

pytestmark = pytest.mark.django_db


def execute(user, query, variables=None):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client.post(
        '/api/graphql/',
        {'query': query, 'variables': variables or {}},
        format='json',
        HTTP_AUTHORIZATION='Bearer test' if user else '',
    ).json()


@pytest.mark.parametrize(
    'factory,kind,field,listing',
    [
        (UserPasskeyFactory, 'PasskeyType', 'name', 'myPasskeys'),
        (SSOSessionFactory, 'SSOSessionType', 'sessionId', 'mySessions'),
        (UserDeviceFactory, 'UserDeviceType', 'deviceName', 'myDevices'),
    ],
)
@pytest.mark.parametrize('access', ['owner', 'foreign', 'admin', 'anonymous', 'inactive'])
def test_personal_node_ownership(
    factory, kind, field, listing, access, user_factory, tenant_factory, tenant_membership_factory
):
    owner = user_factory()
    other = user_factory(is_active=access != 'inactive')
    tenant = tenant_factory()
    tenant_membership_factory(user=owner, tenant=tenant, role=TenantUserRole.MEMBER)
    tenant_membership_factory(user=other, tenant=tenant, role=TenantUserRole.OWNER)
    obj = factory(user=owner)
    factory(user=other)
    requester = owner if access == 'owner' else None if access == 'anonymous' else other
    if access == 'admin':
        other.is_superuser = True
        other.save()
    result = execute(
        requester,
        'query($id: ID!) { node(id: $id) { ... on ' + kind + ' { ' + field + ' } } }',
        {'id': to_global_id(kind, str(obj.pk))},
    )
    if access == 'owner':
        assert not result.get('errors'), result
        assert result['data']['node'][field]
        result = execute(owner, '{ ' + listing + ' { edges { node { id } } } }')
        assert not result.get('errors'), result
        assert len(result['data'][listing]['edges']) == 1
    else:
        assert result.get('data', {}).get('node') is None, result


@pytest.mark.parametrize('access', ['owner', 'foreign', 'pending', 'member', 'no_permission', 'anonymous', 'personal'])
def test_audit_node_requires_tenant_permission(access, user_factory, tenant_factory, tenant_membership_factory):
    actor = user_factory()
    requester = user_factory()
    tenant = tenant_factory()
    tenant_membership_factory(user=actor, tenant=tenant, role=TenantUserRole.OWNER)
    if access in {'owner', 'member', 'pending', 'no_permission'}:
        tenant_membership_factory(
            user=requester,
            tenant=tenant,
            role=TenantUserRole.OWNER if access == 'owner' else TenantUserRole.MEMBER,
            is_accepted=access != 'pending',
        )
    if access == 'no_permission':
        for role in OrganizationRole.objects.filter(tenant=tenant):
            role.permissions.remove(*role.permissions.filter(code='security.view'))
    # Being the recorded actor does not grant permission to tenant security metadata.
    obj = SSOAuditLogFactory(
        user=requester, tenant=None if access == 'personal' else tenant, metadata={'private': 'synthetic'}
    )
    result = execute(
        None if access == 'anonymous' else requester,
        'query($id: ID!) { node(id: $id) { ... on SSOAuditLogType { metadata userEmail } } }',
        {'id': to_global_id('SSOAuditLogType', str(obj.pk))},
    )
    if access in {'owner', 'member'}:
        assert not result.get('errors'), result
        assert json.loads(result['data']['node']['metadata']) == {'private': 'synthetic'}
    else:
        assert result.get('data', {}).get('node') is None, result


def test_unprotected_sso_relationship_cannot_bypass_authorization(user, user_factory):
    foreign = UserPasskeyFactory(user=user_factory())

    class UnprotectedPasskeyType(DjangoObjectType):
        class Meta:
            model = UserPasskey
            fields = ('name',)

    class Query(graphene.ObjectType):
        passkey = graphene.Field(UnprotectedPasskeyType, resolver=lambda root, info: foreign)

    result = graphene.Schema(query=Query).execute(
        '{ passkey { name } }',
        context_value=SimpleNamespace(user=user),
        middleware=[ObjectAuthorizationMiddleware()],
    )
    assert result.errors
    assert result.errors[0].message == 'permission_denied'
    assert result.data in [{'passkey': None}, {'passkey': {'name': None}}]
