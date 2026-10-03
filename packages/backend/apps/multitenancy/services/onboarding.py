"""Validation and storage for the organization onboarding profile.

The step numbers and answer choices defined here are the source of truth for the webapp, which reads them from the
`organizationOnboardingChoices` query and mirrors the step numbers in `OnboardingStep`.
"""

from enum import IntEnum

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..constants import TenantType
from ..models import OrganizationOnboardingProfile
from ..serializers import TenantSerializer


class OnboardingStep(IntEnum):
    COMPANY_DETAILS = 1
    CUSTOMERS = 2
    REVENUE = 3
    COSTS = 4
    PRICING = 5
    SUMMARY = 6


RESPONDENT_ROLES = ('OWNER_MANAGEMENT', 'ACCOUNTING', 'ADVISOR', 'EMPLOYEE')
CUSTOMER_TYPES = ('B2B', 'B2C', 'MIXED', 'PUBLIC')
REVENUE_MODELS = ('SUBSCRIPTION', 'PROJECT', 'PRODUCT', 'TIME', 'SERVICE', 'COMMISSION')
COST_DRIVERS = ('MATERIALS', 'EMPLOYEES', 'SUBCONTRACTORS', 'TRANSPORT', 'MARKETING', 'TECHNOLOGY')
PRICING_MODELS = ('FIXED', 'INDIVIDUAL', 'COST_PLUS', 'TIME_UNIT', 'SUBSCRIPTION')
MAIN_GOALS = ('CASH', 'COSTS', 'PRICING', 'HIRING', 'CLIENT_LOSS', 'EARLY_WARNING')

# Steps whose answers are re-validated when the draft is finished, in the order they appear in the flow.
ANSWER_STEPS = (OnboardingStep.CUSTOMERS, OnboardingStep.REVENUE, OnboardingStep.COSTS, OnboardingStep.PRICING)


def _valid_choice(value, choices, field):
    if value not in choices:
        raise ValidationError({field: 'Select a valid answer.'})


def _valid_choices(values, choices, maximum, field):
    if not isinstance(values, list) or not 1 <= len(values) <= maximum or len(values) != len(set(values)):
        raise ValidationError({field: f'Select between 1 and {maximum} distinct answers.'})
    if any(value not in choices for value in values):
        raise ValidationError({field: 'Select valid answers.'})


def save_onboarding_step(tenant, step, **answers):
    if tenant.type != TenantType.ORGANIZATION:
        raise ValidationError({'tenant': 'Onboarding is available only for organizations.'})

    profile, _ = OrganizationOnboardingProfile.objects.get_or_create(tenant=tenant)
    return save_profile_step(profile, step, **answers)


def save_profile_step(profile, step, **answers):
    if step > profile.current_step:
        raise ValidationError({'step': 'Complete the previous onboarding steps first.'})
    if step == OnboardingStep.CUSTOMERS:
        _valid_choice(answers.get('respondent_role'), RESPONDENT_ROLES, 'respondent_role')
        _valid_choice(answers.get('customer_type'), CUSTOMER_TYPES, 'customer_type')
        profile.respondent_role = answers['respondent_role']
        profile.customer_type = answers['customer_type']
    elif step == OnboardingStep.REVENUE:
        _valid_choices(answers.get('revenue_models'), REVENUE_MODELS, 2, 'revenue_models')
        profile.revenue_models = answers['revenue_models']
    elif step == OnboardingStep.COSTS:
        _valid_choices(answers.get('cost_drivers'), COST_DRIVERS, 3, 'cost_drivers')
        profile.cost_drivers = answers['cost_drivers']
    elif step == OnboardingStep.PRICING:
        _valid_choice(answers.get('pricing'), PRICING_MODELS, 'pricing')
        _valid_choice(answers.get('main_goal'), MAIN_GOALS, 'main_goal')
        profile.pricing = answers['pricing']
        profile.main_goal = answers['main_goal']
    elif step == OnboardingStep.SUMMARY:
        if not all(
            (
                profile.respondent_role,
                profile.customer_type,
                profile.revenue_models,
                profile.cost_drivers,
                profile.pricing,
                profile.main_goal,
            )
        ):
            raise ValidationError({'step': 'Complete all onboarding steps first.'})
        if profile.completed_at is None:
            profile.completed_at = timezone.now()
    else:
        raise ValidationError({'step': 'Invalid onboarding step.'})

    if step == profile.current_step:
        profile.current_step = min(step + 1, OnboardingStep.SUMMARY)
    profile.save()
    return profile


def _validated_company(company, context):
    serializer = TenantSerializer(data=dict(company), context=context)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def _create_organization_from_draft(profile, context):
    """Create the organization from the completed draft and attach the profile to it."""
    serializer = TenantSerializer(data=profile.company_data, context=context)
    serializer.is_valid(raise_exception=True)
    tenant = serializer.save()
    OrganizationOnboardingProfile.objects.filter(tenant=tenant).delete()
    profile.tenant = tenant
    profile.draft_owner = None
    profile.company_data = {}
    profile.save()
    return tenant


@transaction.atomic
def save_draft_step(user, step, company=None, context=None, **answers):
    """Save one step of the account-owned draft. Finishing the summary creates the organization.

    Returns the profile and the created tenant (None until the summary is finished).
    """
    # Serialise draft writes for one account so concurrent submissions cannot interleave.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    profile = OrganizationOnboardingProfile.objects.filter(draft_owner=user).first()

    if step == OnboardingStep.COMPANY_DETAILS:
        if profile is None:
            profile = OrganizationOnboardingProfile(draft_owner=user, is_required=True)
        profile.company_data = _validated_company(company or {}, context)
        profile.save()
        return profile, None

    if profile is None:
        raise ValidationError({'step': 'Complete the company details first.'})
    if step == OnboardingStep.SUMMARY and company is not None:
        profile.company_data = _validated_company(company, context)
        for answer_step in ANSWER_STEPS:
            save_profile_step(profile, answer_step, **answers)
    save_profile_step(profile, step, **answers)

    if step == OnboardingStep.SUMMARY:
        return profile, _create_organization_from_draft(profile, context)
    return profile, None


@transaction.atomic
def clear_draft(user):
    """Delete the caller's own draft. Organization profiles are never touched here."""
    OrganizationOnboardingProfile.objects.filter(draft_owner=user).delete()


CHOICES = {
    'respondent_roles': RESPONDENT_ROLES,
    'customer_types': CUSTOMER_TYPES,
    'revenue_models': REVENUE_MODELS,
    'cost_drivers': COST_DRIVERS,
    'pricing_models': PRICING_MODELS,
    'main_goals': MAIN_GOALS,
}
