import { useQuery } from '@apollo/client/react';
import { useMemo } from 'react';
import type { MessageDescriptor } from 'react-intl';
import { useIntl } from 'react-intl';

import { organizationOnboardingChoicesQuery } from './organizationOnboarding.graphql';

export type Option = { value: string; label: string };

export type OnboardingOptions = {
  roles: Option[];
  customers: Option[];
  revenue: Option[];
  costs: Option[];
  pricing: Option[];
  goals: Option[];
};

// The values come from the API (`organizationOnboardingChoices`), so the backend stays the source of truth.
// These maps only supply the translated labels; a value without a label falls back to the raw value.
const ROLE_LABELS: Record<string, MessageDescriptor> = {
  OWNER_MANAGEMENT: { defaultMessage: 'Owner / management', id: 'Onboarding / Role owner management' },
  ACCOUNTING: { defaultMessage: 'Accounting', id: 'Onboarding / Role accounting' },
  ADVISOR: { defaultMessage: 'Advisor', id: 'Onboarding / Role advisor' },
  EMPLOYEE: { defaultMessage: 'Employee', id: 'Onboarding / Role employee' },
};

const CUSTOMER_LABELS: Record<string, MessageDescriptor> = {
  B2B: { defaultMessage: 'Mostly businesses (B2B)', id: 'Onboarding / Customer B2B' },
  B2C: { defaultMessage: 'Mostly consumers (B2C)', id: 'Onboarding / Customer B2C' },
  MIXED: { defaultMessage: 'Both businesses and consumers', id: 'Onboarding / Customer mixed' },
  PUBLIC: { defaultMessage: 'Public institutions', id: 'Onboarding / Customer public' },
};

const REVENUE_LABELS: Record<string, MessageDescriptor> = {
  SUBSCRIPTION: { defaultMessage: 'Subscription / recurring service', id: 'Onboarding / Revenue subscription' },
  PROJECT: { defaultMessage: 'Project / assignment', id: 'Onboarding / Revenue project' },
  PRODUCT: { defaultMessage: 'Product / order', id: 'Onboarding / Revenue product' },
  TIME: { defaultMessage: 'Time worked', id: 'Onboarding / Revenue time' },
  SERVICE: { defaultMessage: 'Number of services', id: 'Onboarding / Revenue service' },
  COMMISSION: { defaultMessage: 'Commission / result', id: 'Onboarding / Revenue commission' },
};

const COST_LABELS: Record<string, MessageDescriptor> = {
  MATERIALS: { defaultMessage: 'Materials / goods', id: 'Onboarding / Cost materials' },
  EMPLOYEES: { defaultMessage: 'Employee time', id: 'Onboarding / Cost employees' },
  SUBCONTRACTORS: { defaultMessage: 'Subcontractors', id: 'Onboarding / Cost subcontractors' },
  TRANSPORT: { defaultMessage: 'Transport / logistics', id: 'Onboarding / Cost transport' },
  MARKETING: { defaultMessage: 'Marketing / commissions', id: 'Onboarding / Cost marketing' },
  TECHNOLOGY: { defaultMessage: 'Technology / infrastructure', id: 'Onboarding / Cost technology' },
};

const PRICING_LABELS: Record<string, MessageDescriptor> = {
  FIXED: { defaultMessage: 'Fixed price / quote', id: 'Onboarding / Pricing fixed' },
  INDIVIDUAL: { defaultMessage: 'Individual client price', id: 'Onboarding / Pricing individual' },
  COST_PLUS: { defaultMessage: 'Cost plus margin', id: 'Onboarding / Pricing cost plus' },
  TIME_UNIT: { defaultMessage: 'Time / unit', id: 'Onboarding / Pricing time unit' },
  SUBSCRIPTION: { defaultMessage: 'Subscription / package', id: 'Onboarding / Pricing subscription' },
};

const GOAL_LABELS: Record<string, MessageDescriptor> = {
  CASH: { defaultMessage: 'I work hard, but the cash is not there', id: 'Onboarding / Goal cash' },
  COSTS: { defaultMessage: 'Costs keep rising', id: 'Onboarding / Goal costs' },
  PRICING: { defaultMessage: 'I am unsure about my pricing', id: 'Onboarding / Goal pricing' },
  HIRING: { defaultMessage: 'Can I afford to grow the team?', id: 'Onboarding / Goal hiring' },
  CLIENT_LOSS: { defaultMessage: 'I worry about losing a major client', id: 'Onboarding / Goal client loss' },
  EARLY_WARNING: { defaultMessage: 'I want to spot problems early', id: 'Onboarding / Goal early warning' },
};

export const useOnboardingOptions = () => {
  const intl = useIntl();
  const { data, loading, error } = useQuery(organizationOnboardingChoicesQuery);
  const choices = data?.organizationOnboardingChoices;

  const options = useMemo<OnboardingOptions | undefined>(() => {
    if (!choices) return undefined;
    const toOptions = (
      values: ReadonlyArray<string | null> | null | undefined,
      labels: Record<string, MessageDescriptor>
    ) =>
      (values ?? [])
        .filter((value): value is string => value !== null)
        .map((value) => ({ value, label: labels[value] ? intl.formatMessage(labels[value]) : value }));
    return {
      roles: toOptions(choices.respondentRoles, ROLE_LABELS),
      customers: toOptions(choices.customerTypes, CUSTOMER_LABELS),
      revenue: toOptions(choices.revenueModels, REVENUE_LABELS),
      costs: toOptions(choices.costDrivers, COST_LABELS),
      pricing: toOptions(choices.pricingModels, PRICING_LABELS),
      goals: toOptions(choices.mainGoals, GOAL_LABELS),
    };
  }, [choices, intl]);

  return { options, loading, error };
};
