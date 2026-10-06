from unittest.mock import patch

import pytest
from graphql_relay import to_global_id

from apps.multitenancy.constants import TenantType
from apps.users.models import UserProfile

pytestmark = pytest.mark.django_db

MUTATION = '''mutation($organizationId: ID) {
    setDefaultOrganization(input: {organizationId: $organizationId}) { defaultOrganizationId }
}'''
QUERY = '{ currentUser { defaultOrganizationId tenants { id } } }'


def set_default(client, organization_id):
    return client.mutate(MUTATION, variable_values={'organizationId': organization_id})


def test_set_change_and_remove_default(graphene_client, user_factory, tenant_factory, tenant_membership_factory):
    user = user_factory()
    companies = [tenant_factory(type=TenantType.ORGANIZATION) for _ in range(2)]
    for company in companies:
        tenant_membership_factory(user=user, tenant=company, is_accepted=True)
    graphene_client.force_authenticate(user)
    for company in companies:
        response = set_default(graphene_client, to_global_id('TenantType', str(company.pk)))
        assert 'errors' not in response
        assert response['data']['setDefaultOrganization']['defaultOrganizationId'] == to_global_id(
            'TenantType', str(company.pk)
        )
        current_user = graphene_client.query(QUERY)['data']['currentUser']
        assert current_user['defaultOrganizationId'] == to_global_id('TenantType', str(company.pk))
        assert current_user['defaultOrganizationId'] in [tenant['id'] for tenant in current_user['tenants']]
    assert set_default(graphene_client, None)['data']['setDefaultOrganization']['defaultOrganizationId'] is None
    assert UserProfile.objects.get(user=user).default_organization_id is None


@pytest.mark.parametrize('invalid_kind', ['personal', 'invited', 'foreign', 'invalid', 'wrong_node'])
def test_reject_unavailable_organization_without_changing_preference(
    graphene_client, user_factory, tenant_factory, tenant_membership_factory, invalid_kind
):
    user = user_factory()
    allowed = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=allowed, is_accepted=True)
    user.profile.default_organization = allowed
    user.profile.save()
    other = tenant_factory(type=TenantType.DEFAULT if invalid_kind == 'personal' else TenantType.ORGANIZATION)
    if invalid_kind in ['personal', 'invited']:
        tenant_membership_factory(user=user, tenant=other, is_accepted=invalid_kind == 'personal')
    identifier = 'not-an-id' if invalid_kind == 'invalid' else str(other.pk)
    if invalid_kind == 'wrong_node':
        identifier = to_global_id('UserType', str(allowed.pk))
    graphene_client.force_authenticate(user)
    assert set_default(graphene_client, identifier).get('errors')
    assert UserProfile.objects.get(user=user).default_organization_id == allowed.pk


def test_preference_is_personal(graphene_client, user_factory, tenant_factory, tenant_membership_factory):
    first, second = user_factory(), user_factory()
    company = tenant_factory(type=TenantType.ORGANIZATION)
    for user in [first, second]:
        tenant_membership_factory(user=user, tenant=company, is_accepted=True)
    graphene_client.force_authenticate(first)
    assert 'errors' not in set_default(graphene_client, str(company.pk))
    graphene_client.force_authenticate(second)
    assert graphene_client.query(QUERY)['data']['currentUser']['defaultOrganizationId'] is None
    assert UserProfile.objects.get(user=second).default_organization_id is None


@pytest.mark.parametrize('change', ['delete_company', 'delete_membership', 'revoke_membership'])
def test_default_stops_resolving_after_access_loss(
    graphene_client, user_factory, tenant_factory, tenant_membership_factory, change
):
    user = user_factory()
    company = tenant_factory(type=TenantType.ORGANIZATION)
    membership = tenant_membership_factory(user=user, tenant=company, is_accepted=True)
    graphene_client.force_authenticate(user)
    assert 'errors' not in set_default(graphene_client, str(company.pk))
    if change == 'delete_company':
        company.delete()
        assert UserProfile.objects.get(user=user).default_organization_id is None
    elif change == 'delete_membership':
        membership.delete()
    else:
        membership.is_accepted = False
        membership.save()
    assert graphene_client.query(QUERY)['data']['currentUser']['defaultOrganizationId'] is None


def test_superuser_can_choose_visible_company_without_membership(graphene_client, user_factory, tenant_factory):
    user = user_factory(is_superuser=True)
    company = tenant_factory(type=TenantType.ORGANIZATION)
    graphene_client.force_authenticate(user)
    assert 'errors' not in set_default(graphene_client, str(company.pk))
    assert graphene_client.query(QUERY)['data']['currentUser']['defaultOrganizationId'] == to_global_id(
        'TenantType', str(company.pk)
    )


def test_requires_authentication(graphene_client, tenant_factory):
    company = tenant_factory(type=TenantType.ORGANIZATION)
    assert set_default(graphene_client, str(company.pk)).get('errors')


def test_sso_session_filter_applies_to_mutation_and_read(
    graphene_client, user_factory, tenant_factory, tenant_membership_factory
):
    user = user_factory()
    company = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=company, is_accepted=True)
    user.profile.default_organization = company
    user.profile.save()
    graphene_client.force_authenticate(user)
    with patch(
        'apps.users.services.default_organization.filter_tenants_for_password_session',
        side_effect=lambda request, qs: qs.none(),
    ):
        assert set_default(graphene_client, str(company.pk)).get('errors')
        assert graphene_client.query(QUERY)['data']['currentUser']['defaultOrganizationId'] is None


def test_default_relation_is_not_exposed_on_generic_profile_type(graphene_client):
    result = graphene_client.query('{ __type(name: "UserProfileType") { fields { name } } }')
    assert 'defaultOrganization' not in [field['name'] for field in result['data']['__type']['fields']]
