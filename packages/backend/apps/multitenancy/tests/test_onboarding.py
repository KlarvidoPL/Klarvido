import pytest
from graphql_relay import to_global_id
from rest_framework.exceptions import ValidationError

from ..constants import TenantType, TenantUserRole
from ..models import OrganizationOnboardingProfile
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
