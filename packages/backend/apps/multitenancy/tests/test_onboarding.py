import pytest
from graphql_relay import to_global_id
from rest_framework.exceptions import ValidationError

from ..constants import TenantType, TenantUserRole
from ..models import OrganizationOnboardingProfile, Tenant, TenantMembership
from ..services.onboarding import decrypt_demo_token, save_onboarding_step


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def onboarding_encryption_key(settings):
    settings.ONBOARDING_KSEF_ENCRYPTION_KEY = 'HLKgz3EuGIF4jOIAHFGl5atkYZxugw3trZu00Uex0QI='


def test_step_answers_persist_and_completion_requires_every_step(tenant_factory):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    with pytest.raises(ValidationError):
        save_onboarding_step(tenant, 7)

    save_onboarding_step(tenant, 2, respondent_role='OWNER_MANAGEMENT', customer_type='B2B')
    save_onboarding_step(tenant, 3, revenue_models=['PROJECT', 'PRODUCT'])
    save_onboarding_step(tenant, 4, cost_drivers=['MATERIALS'])
    save_onboarding_step(tenant, 5, pricing='FIXED', main_goal='PRICING')
    profile = save_onboarding_step(tenant, 6, ksef_token='a' * 40)
    assert profile.ksef_status == 'demo'
    assert 'a' * 40 not in profile.ksef_demo_token_encrypted
    assert decrypt_demo_token(profile.ksef_demo_token_encrypted) == 'a' * 40
    assert profile.current_step == 7

    completed = save_onboarding_step(tenant, 7)
    assert completed.completed_at is not None
    assert completed.revenue_models == ['PROJECT', 'PRODUCT']
    first_completed_at = completed.completed_at
    assert save_onboarding_step(tenant, 7).completed_at == first_completed_at


@pytest.mark.parametrize(
    'step,answer',
    [
        (3, {'revenue_models': ['PROJECT', 'PRODUCT', 'TIME']}),
        (4, {'cost_drivers': ['MATERIALS', 'EMPLOYEES', 'TRANSPORT', 'MARKETING']}),
        (6, {'ksef_token': 'a' * 39}),
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
    customerType currentStep ksefStatus completedAt
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


def test_owner_can_save_and_read_without_token_in_schema(
    graphene_client, user, tenant_factory, tenant_membership_factory
):
    tenant = tenant_factory(type=TenantType.ORGANIZATION)
    tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER)
    tenant_id = to_global_id('TenantType', tenant.pk)
    graphene_client.force_authenticate(user)

    saved = graphene_client.query(
        MUTATION,
        variable_values={'tenantId': tenant_id, 'step': 2, 'respondentRole': 'OWNER_MANAGEMENT', 'customerType': 'B2B'},
    )
    assert 'errors' not in saved, saved.get('errors')
    assert saved['data']['saveOrganizationOnboardingStep']['profile']['customerType'] == 'B2B'
    read = graphene_client.query(QUERY, variable_values={'tenantId': tenant_id})
    assert 'errors' not in read, read
    assert read['data']['organizationOnboardingProfile'] is not None, read
    assert read['data']['organizationOnboardingProfile']['currentStep'] == 3, read
    assert 'ksefDemoTokenEncrypted' not in read['data']['organizationOnboardingProfile']
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


def test_token_is_not_a_graphql_field(graphene_client, user):
    graphene_client.force_authenticate(user)
    result = graphene_client.query('''{ __type(name: "OrganizationOnboardingProfileType") { fields { name } } }''')
    fields = {field['name'] for field in result['data']['__type']['fields']}
    assert 'ksefStatus' in fields
    assert 'ksefDemoTokenEncrypted' not in fields


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
          $revenueModels: [String], $costDrivers: [String], $pricing: String, $mainGoal: String, $ksefToken: String) {
  saveOrganizationOnboardingDraft(step: $step, company: $company, respondentRole: $respondentRole,
    customerType: $customerType, revenueModels: $revenueModels, costDrivers: $costDrivers,
    pricing: $pricing, mainGoal: $mainGoal, ksefToken: $ksefToken) {
    tenant { id } profile { currentStep ksefStatus completedAt }
  }
}
'''
DRAFT_QUERY = '''{ organizationOnboardingDraft {
  companyData { name nip companyName } respondentRole customerType currentStep ksefStatus
} }'''


def complete_draft_answers(client):
    for step, answers in [
        (2, {'respondentRole': 'ACCOUNTING', 'customerType': 'B2B'}),
        (3, {'revenueModels': ['PROJECT']}),
        (4, {'costDrivers': ['MATERIALS']}),
        (5, {'pricing': 'FIXED', 'mainGoal': 'COSTS'}),
        (6, {'ksefToken': 'x' * 40}),
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
    assert decrypt_demo_token(draft.ksef_demo_token_encrypted) == 'x' * 40
    assert Tenant.objects.count() == initial_count
    completed = graphene_client.query(
        DRAFT_MUTATION,
        variable_values={
            'step': 7,
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
    repeated = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 7})
    assert repeated.get('errors')
    assert Tenant.objects.count() == initial_count + 1


def test_draft_is_account_scoped_and_cannot_skip(graphene_client, user, user_factory):
    graphene_client.force_authenticate(user)
    assert graphene_client.query(DRAFT_MUTATION, variable_values={'step': 7}).get('errors')
    started = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in started, started
    assert graphene_client.query(DRAFT_MUTATION, variable_values={'step': 6, 'ksefToken': 'x' * 40}).get('errors')
    graphene_client.force_authenticate(user_factory())
    assert graphene_client.query(DRAFT_QUERY)['data']['organizationOnboardingDraft'] is None


def test_duplicate_nip_is_account_scoped_and_rechecked_at_finish(
    graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
):
    graphene_client.force_authenticate(user)
    started = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in started, started
    complete_draft_answers(graphene_client)
    existing = tenant_factory(
        type=TenantType.ORGANIZATION, nip=DRAFT_COMPANY['nip'], country='PL', creator=user_factory()
    )
    tenant_membership_factory(tenant=existing, user=user, role=TenantUserRole.MEMBER)
    duplicate = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 7})
    assert duplicate.get('errors'), duplicate
    draft = OrganizationOnboardingProfile.objects.get(draft_owner=user)
    assert draft.completed_at is None  # transaction rollback, draft retained for correction
    nip_query = '''query ($nip: String!, $country: String!) { organizationNipExists(nip: $nip, country: $country) }'''
    values = {'nip': 'PL 972-138-23-73', 'country': 'PL'}
    assert graphene_client.query(nip_query, variable_values=values)['data']['organizationNipExists'] is True
    graphene_client.force_authenticate(user_factory())
    assert graphene_client.query(nip_query, variable_values=values)['data']['organizationNipExists'] is False
    unrelated = graphene_client.query(DRAFT_MUTATION, variable_values={'step': 1, 'company': DRAFT_COMPANY})
    assert 'errors' not in unrelated, unrelated
