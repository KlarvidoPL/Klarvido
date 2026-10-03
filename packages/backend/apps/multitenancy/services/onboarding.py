"""Validation and storage for the organization onboarding profile."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..constants import TenantType
from ..models import OrganizationOnboardingProfile


RESPONDENT_ROLES = ('OWNER_MANAGEMENT', 'ACCOUNTING', 'ADVISOR', 'EMPLOYEE')
CUSTOMER_TYPES = ('B2B', 'B2C', 'MIXED', 'PUBLIC')
REVENUE_MODELS = ('SUBSCRIPTION', 'PROJECT', 'PRODUCT', 'TIME', 'SERVICE', 'COMMISSION')
COST_DRIVERS = ('MATERIALS', 'EMPLOYEES', 'SUBCONTRACTORS', 'TRANSPORT', 'MARKETING', 'TECHNOLOGY')
PRICING_MODELS = ('FIXED', 'INDIVIDUAL', 'COST_PLUS', 'TIME_UNIT', 'SUBSCRIPTION')
MAIN_GOALS = ('CASH', 'COSTS', 'PRICING', 'HIRING', 'CLIENT_LOSS', 'EARLY_WARNING')
SUMMARY_STEP = 6


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
    if step == 2:
        _valid_choice(answers.get('respondent_role'), RESPONDENT_ROLES, 'respondent_role')
        _valid_choice(answers.get('customer_type'), CUSTOMER_TYPES, 'customer_type')
        profile.respondent_role = answers['respondent_role']
        profile.customer_type = answers['customer_type']
    elif step == 3:
        _valid_choices(answers.get('revenue_models'), REVENUE_MODELS, 2, 'revenue_models')
        profile.revenue_models = answers['revenue_models']
    elif step == 4:
        _valid_choices(answers.get('cost_drivers'), COST_DRIVERS, 3, 'cost_drivers')
        profile.cost_drivers = answers['cost_drivers']
    elif step == 5:
        _valid_choice(answers.get('pricing'), PRICING_MODELS, 'pricing')
        _valid_choice(answers.get('main_goal'), MAIN_GOALS, 'main_goal')
        profile.pricing = answers['pricing']
        profile.main_goal = answers['main_goal']
    elif step == SUMMARY_STEP:
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
        profile.current_step = min(step + 1, SUMMARY_STEP)
    profile.save()
    return profile
