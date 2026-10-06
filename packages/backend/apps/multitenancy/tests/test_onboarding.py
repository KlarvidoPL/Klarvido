import pytest
from types import SimpleNamespace
from graphql_relay import to_global_id
from rest_framework.exceptions import ValidationError

from ..constants import TenantType, TenantUserRole
from ..models import OrganizationOnboardingProfile, Tenant, TenantMembership
from ..services.onboarding import (
    CHOICES,
    COST_DRIVERS,
    CUSTOMER_TYPES,
    MAIN_GOALS,
    PRICING_MODELS,
    RESPONDENT_ROLES,
    REVENUE_MODELS,
    save_draft_step,
    save_onboarding_step,
)


pytestmark = pytest.mark.django_db


def test_step_answers_persist_and_completion_requires_every_step(tenant_factory):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    with pytest.raises(ValidationError):
        save_onboarding_step(tenant, 6)

    save_onboarding_step(tenant, 2, respondent_role='OWNER_MANAGEMENT', customer_type='B2B')
    save_onboarding_step(tenant, 3, revenue_models=['PROJECT', 'PRODUCT'])
    save_onboarding_step(tenant, 4, cost_drivers=['MATERIALS'])
    profile = save_onboarding_step(tenant, 5, pricing='FIXED', main_goal='PRICING')
    assert profile.current_step == 6

    completed = save_onboarding_step(tenant, 6)
    assert completed.completed_at is not None
    assert completed.revenue_models == ['PROJECT', 'PRODUCT']
    first_completed_at = completed.completed_at
    assert save_onboarding_step(tenant, 6).completed_at == first_completed_at


@pytest.mark.parametrize(
    'step,answer',
    [
        (3, {'revenue_models': ['PROJECT', 'PRODUCT', 'TIME']}),
        (4, {'cost_drivers': ['MATERIALS', 'EMPLOYEES', 'TRANSPORT', 'MARKETING']}),
    ],
)
def test_invalid_answers_are_rejected(tenant_factory, step, answer):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    OrganizationOnboardingProfile.objects.create(tenant=tenant, current_step=step)
    with pytest.raises(ValidationError):
        save_onboarding_step(tenant, step, **answer)


def test_cannot_skip_steps_or_onboard_personal_tenant(tenant_factory):
    organization = tenant_factory(type=TenantType.ORGANIZATION)
    with pytest.raises(ValidationError):
        save_onboarding_step(organization, 3, revenue_models=['PROJECT'])

    personal = tenant_factory(type=TenantType.DEFAULT)
    with pytest.raises(ValidationError):
        save_onboarding_step(personal, 2, respondent_role='OWNER_MANAGEMENT', customer_type='B2B')


QUERY = '''
query ($tenantId: ID!) {
  organizationOnboardingProfile(tenantId: $tenantId) {
    customerType currentStep completedAt
  }
}
'''

MUTATION = '''
mutation ($tenantId: ID!, $step: Int!, $respondentRole: String, $customerType: String) {
  saveOrganizationOnboardingStep(
    tenantId: $tenantId, step: $step,
    respondentRole: $respondentRole, customerType: $customerType
  ) {
    profile { customerType currentStep }
  }
}
'''


def test_owner_can_save_and_read_onboarding_profile(graphene_client, user, tenant_factory, tenant_membership_factory):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    tenant_id = to_global_id('TenantType', tenant.pk)
    graphene_client.force_authenticate(user)
    graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)

    saved = graphene_client.mutate(
        MUTATION,
        variable_values={'tenantId': tenant_id, 'step': 2, 'respondentRole': 'OWNER_MANAGEMENT', 'customerType': 'B2B'},
    )
    assert 'errors' not in saved, saved.get('errors')
    assert saved['data']['saveOrganizationOnboardingStep']['profile']['customerType'] == 'B2B'
    read = graphene_client.query(QUERY, variable_values={'tenantId': tenant_id})
    assert 'errors' not in read, read
    assert read['data']['organizationOnboardingProfile'] is not None, read
    assert read['data']['organizationOnboardingProfile']['currentStep'] == 3, read
    assert OrganizationOnboardingProfile.objects.get(tenant=tenant).customer_type == 'B2B'


def test_other_tenant_cannot_read_or_write(graphene_client, user, tenant_factory):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_id = to_global_id('TenantType', tenant.pk)
    graphene_client.force_authenticate(user)
    for query, values in [
        (QUERY, {'tenantId': tenant_id}),
        (MUTATION, {'tenantId': tenant_id, 'step': 2, 'respondentRole': 'OWNER_MANAGEMENT', 'customerType': 'B2B'}),
    ]:
        result = graphene_client.query(query, variable_values=values)
        assert result.get('errors'), result


@pytest.mark.parametrize('is_owner', [True, False])
def test_onboarding_http_authorizes_the_explicit_organization(
    api_client, user, tenant_factory, tenant_membership_factory, is_owner
):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    if is_owner:
        tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    api_client.force_authenticate(user)
    response = api_client.post(
        '/api/graphql/',
        {
            'query': MUTATION,
            'variables': {
                'tenantId': to_global_id('TenantType', tenant.pk),
                'step': 2,
                'respondentRole': 'OWNER_MANAGEMENT',
                'customerType': 'B2B',
            },
        },
        format='json',
    )
    result = response.json()
    if is_owner:
        assert not result.get('errors'), result
        assert result['data']['saveOrganizationOnboardingStep']['profile']['customerType'] == 'B2B'
    else:
        assert result.get('errors'), result
        assert not OrganizationOnboardingProfile.objects.filter(tenant=tenant).exists()


DRAFT_COMPANY = {
    'name': 'Draft organization',
    'country': 'PL',
    'nip': '9721382373',
    'companyName': 'Draft company',
    'regon': '123456785',
    'address': 'Warsaw',
    'vatStatus': 'ACTIVE',
}
DRAFT_MUTATION = '''
mutation ($step: Int!, $company: OnboardingCompanyInput, $respondentRole: String, $customerType: String,
          $revenueModels: [String], $costDrivers: [String], $pricing: String, $mainGoal: String) {
  saveOrganizationOnboardingDraft(step: $step, company: $company, respondentRole: $respondentRole,
    customerType: $customerType, revenueModels: $revenueModels, costDrivers: $costDrivers,
    pricing: $pricing, mainGoal: $mainGoal) {
    tenant { id } profile { currentStep completedAt }
  }
}
'''
DRAFT_QUERY = '''{ organizationOnboardingDraft {
  companyData { name nip companyName } respondentRole customerType currentStep
} }'''


def complete_draft_answers(client):
    for step, answers in [
        (2, {'respondentRole': 'ACCOUNTING', 'customerType': 'B2B'}),
        (3, {'revenueModels': ['PROJECT']}),
        (4, {'costDrivers': ['MATERIALS']}),
        (5, {'pricing': 'FIXED', 'mainGoal': 'COSTS'}),
    ]:
        result = client.query(DRAFT_MUTATION, variable_values={'step': step, **answers})
        assert 'errors' not in result, result
        assert result['data']['saveOrganizationOnboardingDraft']['tenant'] is None


def test_draft_creates_organization_only_after_summary(graphene_client, user):
    graphene_client.force_authenticate(user)
    initial_count = Tenant.objects.count()
    started = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in started, started
    assert Tenant.objects.count() == initial_count
    assert started['data']['saveOrganizationOnboardingDraft']['tenant'] is None
    read = graphene_client.query(DRAFT_QUERY)
    assert read['data']['organizationOnboardingDraft']['companyData']['nip'] == DRAFT_COMPANY['nip']
    complete_draft_answers(graphene_client)
    draft = OrganizationOnboardingProfile.objects.get(draft_owner=user)
    assert Tenant.objects.count() == initial_count
    completed = graphene_client.query(
        DRAFT_MUTATION,
        variable_values={
            'step': 6,
            'company': {**DRAFT_COMPANY, 'name': 'Final corrected name'},
            'respondentRole': 'ACCOUNTING',
            'customerType': 'B2C',
            'revenueModels': ['PROJECT'],
            'costDrivers': ['MATERIALS'],
            'pricing': 'FIXED',
            'mainGoal': 'COSTS',
        },
    )
    assert 'errors' not in completed, completed
    assert Tenant.objects.count() == initial_count + 1
    draft.refresh_from_db()
    assert draft.tenant is not None and draft.draft_owner is None
    assert draft.completed_at is not None
    assert draft.respondent_role == 'ACCOUNTING'
    assert draft.customer_type == 'B2C'
    assert draft.tenant.name == 'Final corrected name'
    assert TenantMembership.objects.get(tenant=draft.tenant, user=user).role == TenantUserRole.OWNER
    assert graphene_client.query(DRAFT_QUERY)['data']['organizationOnboardingDraft'] is None
    repeated = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 6})
    assert repeated.get('errors')
    assert Tenant.objects.count() == initial_count + 1


def test_draft_is_account_scoped_and_cannot_skip(graphene_client, user, user_factory):
    graphene_client.force_authenticate(user)
    assert graphene_client.query(DRAFT_MUTATION, variable_values={'step': 6}).get('errors')
    started = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in started, started
    assert graphene_client.query(DRAFT_MUTATION, variable_values={'step': 3, 'revenueModels': ['PROJECT']}).get(
        'errors'
    )
    graphene_client.force_authenticate(user_factory())
    assert graphene_client.query(DRAFT_QUERY)['data']['organizationOnboardingDraft'] is None


CLEAR_MUTATION = """
mutation {
  clearOrganizationOnboardingDraft { ok }
}
"""


def test_clear_draft_removes_only_the_callers_draft(graphene_client, user, user_factory):
    graphene_client.force_authenticate(user)
    started = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in started, started
    other = user_factory()
    OrganizationOnboardingProfile.objects.create(draft_owner=other)

    result = graphene_client.query(CLEAR_MUTATION)
    assert 'errors' not in result, result
    assert result['data']['clearOrganizationOnboardingDraft']['ok'] is True
    assert graphene_client.query(DRAFT_QUERY)['data']['organizationOnboardingDraft'] is None
    assert OrganizationOnboardingProfile.objects.filter(draft_owner=other).exists()


def test_same_nip_can_be_used_for_another_organization(
    graphene_client, user, tenant_factory, tenant_membership_factory
):
    existing = tenant_factory(type=TenantType.ORGANIZATION, nip=DRAFT_COMPANY['nip'], country='PL', creator=user)
    tenant_membership_factory(tenant=existing, user=user, role=TenantUserRole.OWNER)
    graphene_client.force_authenticate(user)

    started = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in started, started
    complete_draft_answers(graphene_client)
    completed = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 6})
    assert 'errors' not in completed, completed
    assert Tenant.objects.filter(nip=DRAFT_COMPANY['nip'], creator=user).count() == 2


def test_failed_finish_rolls_back_organization_and_keeps_draft(mocker, user):
    context = {'request': SimpleNamespace(user=user)}
    company = {
        'name': 'Draft organization',
        'country': 'PL',
        'nip': DRAFT_COMPANY['nip'],
        'company_name': 'Draft company',
        'regon': '123456785',
        'address': 'Warsaw',
        'vat_status': 'ACTIVE',
    }
    save_draft_step(user, 1, company=company, context=context)
    for step, answers in [
        (2, {'respondent_role': 'ACCOUNTING', 'customer_type': 'B2B'}),
        (3, {'revenue_models': ['PROJECT']}),
        (4, {'cost_drivers': ['MATERIALS']}),
        (5, {'pricing': 'FIXED', 'main_goal': 'COSTS'}),
    ]:
        save_draft_step(user, step, context=context, **answers)

    # The summary's first save succeeds; the save after the organization is created fails.
    mocker.patch.object(OrganizationOnboardingProfile, 'save', side_effect=[None, RuntimeError('boom')])
    with pytest.raises(RuntimeError):
        save_draft_step(user, 6, context=context)

    assert not Tenant.objects.filter(nip=DRAFT_COMPANY['nip'], creator=user).exists()
    assert OrganizationOnboardingProfile.objects.filter(draft_owner=user, tenant__isnull=True).exists()


def test_unauthenticated_clear_is_rejected(graphene_client):
    result = graphene_client.query(CLEAR_MUTATION)
    assert result.get('errors'), result


def test_choices_query_exposes_the_service_lists(graphene_client, user):
    graphene_client.force_authenticate(user)
    result = graphene_client.query(
        """
        {
          organizationOnboardingChoices {
            respondentRoles customerTypes revenueModels costDrivers pricingModels mainGoals
          }
        }
        """
    )
    assert 'errors' not in result, result
    choices = result['data']['organizationOnboardingChoices']
    assert choices['respondentRoles'] == list(RESPONDENT_ROLES)
    assert choices['customerTypes'] == list(CUSTOMER_TYPES)
    assert choices['revenueModels'] == list(REVENUE_MODELS)
    assert choices['costDrivers'] == list(COST_DRIVERS)
    assert choices['pricingModels'] == list(PRICING_MODELS)
    assert choices['mainGoals'] == list(MAIN_GOALS)
    assert CHOICES['respondent_roles'] == RESPONDENT_ROLES
