import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';

import { organizationOnboardingChoicesQuery } from '../organizationOnboarding.graphql';

// Mirrors the choices returned by the backend (`OnboardingChoices` in apps/multitenancy/services/onboarding.py).
export const onboardingChoicesMock = composeMockedQueryResult(organizationOnboardingChoicesQuery, {
  data: {
    organizationOnboardingChoices: {
      __typename: 'OrganizationOnboardingChoicesType' as const,
      respondentRoles: ['OWNER_MANAGEMENT', 'ACCOUNTING', 'ADVISOR', 'EMPLOYEE'],
      customerTypes: ['B2B', 'B2C', 'MIXED', 'PUBLIC'],
      revenueModels: ['SUBSCRIPTION', 'PROJECT', 'PRODUCT', 'TIME', 'SERVICE', 'COMMISSION'],
      costDrivers: ['MATERIALS', 'EMPLOYEES', 'SUBCONTRACTORS', 'TRANSPORT', 'MARKETING', 'TECHNOLOGY'],
      pricingModels: ['FIXED', 'INDIVIDUAL', 'COST_PLUS', 'TIME_UNIT', 'SUBSCRIPTION'],
      mainGoals: ['CASH', 'COSTS', 'PRICING', 'HIRING', 'CLIENT_LOSS', 'EARLY_WARNING'],
    },
  },
});
