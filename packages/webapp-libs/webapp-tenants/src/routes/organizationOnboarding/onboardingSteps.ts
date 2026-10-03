// Step numbers used by the onboarding screens. Steps 2-6 match `OnboardingStep` in
// apps/multitenancy/services/onboarding.py; steps 0 and 1 are the organization name and company details.
export const OnboardingStep = {
  ORGANIZATION: 0,
  COMPANY_DETAILS: 1,
  CUSTOMERS: 2,
  REVENUE: 3,
  COSTS: 4,
  PRICING: 5,
  SUMMARY: 6,
} as const;

export const LAST_ONBOARDING_STEP = OnboardingStep.SUMMARY;
