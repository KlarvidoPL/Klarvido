import { useMutation, useQuery } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Form } from '@sb/webapp-core/components/forms';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { cn } from '@sb/webapp-core/lib/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast';
import { ArrowLeft, ArrowRight, Building2, Loader2, Trash2 } from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router';

import {
  COMPANY_DETAILS_FIELDS,
  CompanyDetailsFields,
  CountryField,
  DisplayNameField,
  NipField,
} from '../../components/companyDetailsFields';
import { useCompanyFormErrorMessages } from '../../components/companyDetailsFields/companyFormErrors.hook';
import { OnboardingProgress } from '../../components/onboardingProgress/onboardingProgress.component';
import { TenantFormFields } from '../../components/tenantForm/tenantForm.component';
import { useGenerateTenantPath } from '../../hooks';
import { useCompanyLookup } from '../../hooks/useCompanyLookup';
import { useCurrentTenant } from '../../providers';
import { normalizeTaxId } from '../../utils/companyCountries';
import { normalizeDigits } from '../../utils/nip';
import {
  organizationOnboardingDraftQuery,
  organizationOnboardingProfileQuery,
  saveOrganizationOnboardingDraftMutation,
  saveOrganizationOnboardingStepMutation,
  updateOnboardingTenantMutation,
} from './organizationOnboarding.graphql';

type Option = { value: string; label: string; hint?: string };
type Answers = {
  respondentRole: string;
  customerType: string;
  revenueModels: string[];
  costDrivers: string[];
  pricing: string;
  mainGoal: string;
};

const initialAnswers: Answers = {
  respondentRole: '',
  customerType: '',
  revenueModels: [],
  costDrivers: [],
  pricing: '',
  mainGoal: '',
};

// Matches the backend SUMMARY_STEP (apps/multitenancy/services/onboarding.py).
const SUMMARY_STEP = 6;

const ChoiceGroup = ({
  options,
  selected,
  onChange,
  max = 1,
}: {
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
  max?: number;
}) => {
  const [optionWidth, setOptionWidth] = useState(144);
  const measurementRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const labelsKey = options.map(({ label, hint }) => `${label}:${hint ?? ''}`).join('|');

  useLayoutEffect(() => {
    const measure = () => {
      const widestLabel = Math.max(...measurementRefs.current.map((element) => element?.offsetWidth ?? 0));
      setOptionWidth(Math.max(144, widestLabel + 28));
    };
    measure();
    const observer = new ResizeObserver(measure);
    measurementRefs.current.forEach((element) => element && observer.observe(element));
    return () => observer.disconnect();
  }, [labelsKey]);

  return (
    <div className="relative flex flex-wrap gap-3">
      <div className="pointer-events-none absolute invisible" aria-hidden="true">
        {options.map((option, index) => (
          <span
            key={option.value}
            ref={(element) => {
              measurementRefs.current[index] = element;
            }}
            className="block w-max whitespace-nowrap text-sm font-normal"
          >
            {option.label}
          </span>
        ))}
      </div>
      {options.map((option) => {
        const active = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            aria-disabled={max > 1 && !active && selected.length >= max}
            disabled={max > 1 && !active && selected.length >= max}
            style={{ width: optionWidth }}
            className={cn(
              'flex min-h-10 max-w-full flex-none flex-col items-center justify-center rounded-lg border bg-card px-3 py-2 text-center text-sm transition-colors hover:border-primary disabled:cursor-not-allowed disabled:opacity-50',
              active && 'border-primary bg-primary/5 ring-1 ring-primary'
            )}
            onClick={() =>
              onChange(
                max === 1
                  ? [option.value]
                  : active
                    ? selected.filter((value) => value !== option.value)
                    : selected.length < max
                      ? [...selected, option.value]
                      : selected
              )
            }
          >
            <span className="block font-normal">{option.label}</span>
            {option.hint && <span className="mt-1 block text-sm text-muted-foreground">{option.hint}</span>}
          </button>
        );
      })}
    </div>
  );
};

export const OrganizationOnboarding = ({
  draftMode = false,
  onClearDraft,
  clearingDraft = false,
}: {
  draftMode?: boolean;
  onClearDraft?: () => Promise<void>;
  clearingDraft?: boolean;
}) => {
  const errorMessages = useCompanyFormErrorMessages();
  const { data: currentTenant } = useCurrentTenant();
  const draftQuery = useQuery(organizationOnboardingDraftQuery, { skip: !draftMode, fetchPolicy: 'network-only' });
  const tenant = draftMode ? draftQuery.data?.organizationOnboardingDraft?.companyData : currentTenant;
  const { lookup, loading: lookupLoading } = useCompanyLookup();
  const [saveDraft, { loading: savingDraft }] = useMutation(saveOrganizationOnboardingDraftMutation);
  const tenantId = draftMode ? '' : (currentTenant?.id ?? '');
  const navigate = useNavigate();
  const tenantPath = useGenerateTenantPath();
  const intl = useIntl();
  const { toast } = useToast();
  const { reload: reloadCommonQuery } = useCommonQuery();
  const [step, setStep] = useState(2);
  const [answers, setAnswers] = useState<Answers>(initialAnswers);
  const [loaded, setLoaded] = useState(false);
  const tenantQuery = useQuery(organizationOnboardingProfileQuery, {
    variables: { tenantId },
    skip: draftMode || !tenantId,
    fetchPolicy: 'network-only',
  });
  const { loading, error, refetch } = draftMode ? draftQuery : tenantQuery;
  const data = draftMode ? draftQuery.data : tenantQuery.data;
  const [saveStep, { loading: saving }] = useMutation(saveOrganizationOnboardingStepMutation);
  const [updateTenant, { loading: updatingTenant }] = useMutation(updateOnboardingTenantMutation);
  const {
    form: tenantForm,
    setApolloGraphQLResponseErrors,
    hasGenericErrorOnly: hasTenantError,
    genericError: tenantError,
  } = useApiForm<TenantFormFields>({
    errorMessages,
    mode: 'onChange',
    defaultValues: {
      name: tenant?.name ?? '',
      country: tenant?.country ?? '',
      nip: tenant?.nip ?? '',
      companyName: tenant?.companyName ?? '',
      regon: tenant?.regon ?? '',
      address: tenant?.address ?? '',
      vatStatus: tenant?.vatStatus ?? '',
    },
  });
  const profile = draftMode
    ? draftQuery.data?.organizationOnboardingDraft
    : tenantQuery.data?.organizationOnboardingProfile;
  const initializedTenantId = useRef<string | undefined>(undefined);
  const sourceId = draftMode ? 'draft' : tenantId;
  useEffect(() => {
    if (!tenant || initializedTenantId.current === sourceId) return;
    tenantForm.reset({
      name: tenant.name ?? '',
      country: tenant.country ?? '',
      nip: tenant.nip ?? '',
      companyName: tenant.companyName ?? '',
      regon: tenant.regon ?? '',
      address: tenant.address ?? '',
      vatStatus: tenant.vatStatus ?? '',
    });
    initializedTenantId.current = sourceId;
  }, [tenant, tenantForm, sourceId]);
  useEffect(() => {
    if (!data || loaded) return;
    setAnswers({
      respondentRole: profile?.respondentRole ?? '',
      customerType: profile?.customerType ?? '',
      revenueModels: (profile?.revenueModels ?? []).filter((value): value is string => value !== null),
      costDrivers: (profile?.costDrivers ?? []).filter((value): value is string => value !== null),
      pricing: profile?.pricing ?? '',
      mainGoal: profile?.mainGoal ?? '',
    });
    setStep(profile?.completedAt ? SUMMARY_STEP : Math.max(2, Math.min(profile?.currentStep ?? 2, SUMMARY_STEP)));
    setLoaded(true);
  }, [data, profile, loaded]);

  const customerOptions: Option[] = [
    {
      value: 'B2B',
      label: intl.formatMessage({ defaultMessage: 'Mostly businesses (B2B)', id: 'Onboarding / Customer B2B' }),
    },
    {
      value: 'B2C',
      label: intl.formatMessage({ defaultMessage: 'Mostly consumers (B2C)', id: 'Onboarding / Customer B2C' }),
    },
    {
      value: 'MIXED',
      label: intl.formatMessage({ defaultMessage: 'Both businesses and consumers', id: 'Onboarding / Customer mixed' }),
    },
    {
      value: 'PUBLIC',
      label: intl.formatMessage({ defaultMessage: 'Public institutions', id: 'Onboarding / Customer public' }),
    },
  ];
  const roleOptions: Option[] = [
    {
      value: 'OWNER_MANAGEMENT',
      label: intl.formatMessage({ defaultMessage: 'Owner / management', id: 'Onboarding / Role owner management' }),
    },
    {
      value: 'ACCOUNTING',
      label: intl.formatMessage({ defaultMessage: 'Accounting', id: 'Onboarding / Role accounting' }),
    },
    { value: 'ADVISOR', label: intl.formatMessage({ defaultMessage: 'Advisor', id: 'Onboarding / Role advisor' }) },
    { value: 'EMPLOYEE', label: intl.formatMessage({ defaultMessage: 'Employee', id: 'Onboarding / Role employee' }) },
  ];
  const revenueOptions: Option[] = [
    {
      value: 'SUBSCRIPTION',
      label: intl.formatMessage({
        defaultMessage: 'Subscription / recurring service',
        id: 'Onboarding / Revenue subscription',
      }),
    },
    {
      value: 'PROJECT',
      label: intl.formatMessage({ defaultMessage: 'Project / assignment', id: 'Onboarding / Revenue project' }),
    },
    {
      value: 'PRODUCT',
      label: intl.formatMessage({ defaultMessage: 'Product / order', id: 'Onboarding / Revenue product' }),
    },
    { value: 'TIME', label: intl.formatMessage({ defaultMessage: 'Time worked', id: 'Onboarding / Revenue time' }) },
    {
      value: 'SERVICE',
      label: intl.formatMessage({ defaultMessage: 'Number of services', id: 'Onboarding / Revenue service' }),
    },
    {
      value: 'COMMISSION',
      label: intl.formatMessage({ defaultMessage: 'Commission / result', id: 'Onboarding / Revenue commission' }),
    },
  ];
  const costOptions: Option[] = [
    {
      value: 'MATERIALS',
      label: intl.formatMessage({ defaultMessage: 'Materials / goods', id: 'Onboarding / Cost materials' }),
    },
    {
      value: 'EMPLOYEES',
      label: intl.formatMessage({ defaultMessage: 'Employee time', id: 'Onboarding / Cost employees' }),
    },
    {
      value: 'SUBCONTRACTORS',
      label: intl.formatMessage({ defaultMessage: 'Subcontractors', id: 'Onboarding / Cost subcontractors' }),
    },
    {
      value: 'TRANSPORT',
      label: intl.formatMessage({ defaultMessage: 'Transport / logistics', id: 'Onboarding / Cost transport' }),
    },
    {
      value: 'MARKETING',
      label: intl.formatMessage({ defaultMessage: 'Marketing / commissions', id: 'Onboarding / Cost marketing' }),
    },
    {
      value: 'TECHNOLOGY',
      label: intl.formatMessage({ defaultMessage: 'Technology / infrastructure', id: 'Onboarding / Cost technology' }),
    },
  ];
  const pricingOptions: Option[] = [
    {
      value: 'FIXED',
      label: intl.formatMessage({ defaultMessage: 'Fixed price / quote', id: 'Onboarding / Pricing fixed' }),
    },
    {
      value: 'INDIVIDUAL',
      label: intl.formatMessage({ defaultMessage: 'Individual client price', id: 'Onboarding / Pricing individual' }),
    },
    {
      value: 'COST_PLUS',
      label: intl.formatMessage({ defaultMessage: 'Cost plus margin', id: 'Onboarding / Pricing cost plus' }),
    },
    {
      value: 'TIME_UNIT',
      label: intl.formatMessage({ defaultMessage: 'Time / unit', id: 'Onboarding / Pricing time unit' }),
    },
    {
      value: 'SUBSCRIPTION',
      label: intl.formatMessage({ defaultMessage: 'Subscription / package', id: 'Onboarding / Pricing subscription' }),
    },
  ];
  const goalOptions: Option[] = [
    {
      value: 'CASH',
      label: intl.formatMessage({
        defaultMessage: 'I work hard, but the cash is not there',
        id: 'Onboarding / Goal cash',
      }),
    },
    {
      value: 'COSTS',
      label: intl.formatMessage({ defaultMessage: 'Costs keep rising', id: 'Onboarding / Goal costs' }),
    },
    {
      value: 'PRICING',
      label: intl.formatMessage({ defaultMessage: 'I am unsure about my pricing', id: 'Onboarding / Goal pricing' }),
    },
    {
      value: 'HIRING',
      label: intl.formatMessage({ defaultMessage: 'Can I afford to grow the team?', id: 'Onboarding / Goal hiring' }),
    },
    {
      value: 'CLIENT_LOSS',
      label: intl.formatMessage({
        defaultMessage: 'I worry about losing a major client',
        id: 'Onboarding / Goal client loss',
      }),
    },
    {
      value: 'EARLY_WARNING',
      label: intl.formatMessage({
        defaultMessage: 'I want to spot problems early',
        id: 'Onboarding / Goal early warning',
      }),
    },
  ];

  const update = (patch: Partial<Answers>) => setAnswers((current) => ({ ...current, ...patch }));
  const canContinue =
    step < 2
      ? true
      : step === 2
        ? !!answers.respondentRole && !!answers.customerType
        : step === 3
          ? answers.revenueModels.length > 0
          : step === 4
            ? answers.costDrivers.length > 0
            : step === 5
              ? !!answers.pricing && !!answers.mainGoal
              : true;

  const onNext = async () => {
    if ((!tenantId && !draftMode) || !canContinue) return;
    if (step < 2) {
      const fields = step === 0 ? (['name', 'country', 'nip'] as const) : COMPANY_DETAILS_FIELDS;
      if (!(await tenantForm.trigger([...fields]))) return;
      const values = tenantForm.getValues();
      try {
        if (draftMode) {
          if (step === 0) {
            const nip = normalizeTaxId(values.nip, values.country);
            if (nip !== tenant?.nip || values.country !== tenant?.country) {
              const company = await lookup(nip, values.country);
              tenantForm.setValue('companyName', company?.companyName ?? '');
              tenantForm.setValue('regon', company?.regon ?? '');
              tenantForm.setValue('address', company?.address ?? '');
              tenantForm.setValue('vatStatus', company?.vatStatus ?? '');
            }
          } else {
            await saveDraft({
              variables: {
                step: 1,
                company: {
                  ...values,
                  nip: normalizeTaxId(values.nip, values.country),
                  regon: normalizeDigits(values.regon),
                },
              },
            });
            await refetch();
          }
          setStep(step + 1);
          return;
        }
        await updateTenant({
          variables: {
            input: {
              id: tenantId,
              tenantId,
              name: values.name,
              ...(step === 0
                ? {
                    country: values.country,
                    nip: normalizeTaxId(values.nip, values.country),
                  }
                : {
                    companyName: values.companyName,
                    regon: normalizeDigits(values.regon),
                    address: values.address,
                    vatStatus: values.vatStatus,
                  }),
            },
          },
        });
        await reloadCommonQuery();
        setStep(step + 1);
      } catch (mutationError) {
        const graphQLErrors = extractGraphQLErrors(mutationError);
        if (graphQLErrors) setApolloGraphQLResponseErrors(graphQLErrors);
        toast({
          description: intl.formatMessage({
            defaultMessage: 'Could not update the organization. Please check the fields and try again.',
            id: 'Onboarding / Organization save failed',
          }),
          variant: 'destructive',
        });
      }
      return;
    }
    try {
      const variables = {
        step,
        ...(draftMode && step === SUMMARY_STEP
          ? {
              company: {
                ...tenantForm.getValues(),
                nip: normalizeTaxId(tenantForm.getValues('nip'), tenantForm.getValues('country')),
                regon: normalizeDigits(tenantForm.getValues('regon')),
              },
              respondentRole: answers.respondentRole,
              customerType: answers.customerType,
              revenueModels: answers.revenueModels,
              costDrivers: answers.costDrivers,
              pricing: answers.pricing,
              mainGoal: answers.mainGoal,
            }
          : {}),
        ...(step === 2 ? { respondentRole: answers.respondentRole, customerType: answers.customerType } : {}),
        ...(step === 3 ? { revenueModels: answers.revenueModels } : {}),
        ...(step === 4 ? { costDrivers: answers.costDrivers } : {}),
        ...(step === 5 ? { pricing: answers.pricing, mainGoal: answers.mainGoal } : {}),
      };
      const created = draftMode
        ? (await saveDraft({ variables })).data?.saveOrganizationOnboardingDraft?.tenant
        : (await saveStep({ variables: { ...variables, tenantId } }), null);
      if (step !== SUMMARY_STEP || !draftMode) await refetch();
      if (step === SUMMARY_STEP) {
        await reloadCommonQuery();
        toast({
          description: profile?.isRequired
            ? intl.formatMessage({
                defaultMessage: 'Organization added successfully!',
                id: 'Tenant form / AddTenant / Success message',
              })
            : intl.formatMessage({ defaultMessage: 'Onboarding completed', id: 'Onboarding / Completed' }),
          variant: 'success',
        });
        if (created) trackEvent('tenant', 'add', created.id);
        navigate(tenantPath(RoutesConfig.home, created ? { tenantId: created.id } : undefined));
      } else setStep(step + 1);
    } catch (mutationError) {
      const graphQLErrors = extractGraphQLErrors(mutationError);
      if (graphQLErrors) {
        setApolloGraphQLResponseErrors(graphQLErrors);
        const validationError = graphQLErrors.find(({ message }) => message === 'GraphQlValidationError');
        const fieldsWithErrors = Object.keys(validationError?.extensions ?? {});
        if (['name', 'country', 'nip'].some((field) => fieldsWithErrors.includes(field))) setStep(0);
        else if (
          ['companyName', 'company_name', 'regon', 'address', 'vatStatus', 'vat_status'].some((field) =>
            fieldsWithErrors.includes(field)
          )
        )
          setStep(1);
      }
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Could not save this step. Please try again.',
          id: 'Onboarding / Save failed',
        }),
        variant: 'destructive',
      });
    }
  };

  const onBack = () => {
    if (step > 0) setStep(step - 1);
  };

  if (error)
    return (
      <PageLayout>
        <p className="p-8 text-destructive">
          <FormattedMessage defaultMessage="Could not load the business profile." id="Onboarding / Load failed" />
        </p>
      </PageLayout>
    );
  if (loading || !loaded)
    return (
      <PageLayout>
        <div className="flex justify-center p-8">
          <Loader2 className="animate-spin" />
        </div>
      </PageLayout>
    );

  return (
    <PageLayout>
      <Card className="mx-auto w-full max-w-screen-2xl">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              {draftMode ? (
                <FormattedMessage defaultMessage="Add Organization" id="Tenant form / AddTenant / Card title" />
              ) : (
                <FormattedMessage defaultMessage="Set up your organization" id="Onboarding / Title" />
              )}
            </CardTitle>
            {draftMode && onClearDraft && (
              <ConfirmDialog
                title={<FormattedMessage defaultMessage="Clear this draft?" id="Onboarding / Clear draft title" />}
                description={
                  <FormattedMessage
                    defaultMessage="All answers for this new organization will be deleted. This cannot be undone."
                    id="Onboarding / Clear draft description"
                  />
                }
                continueLabel={<FormattedMessage defaultMessage="Clear draft" id="Onboarding / Clear draft confirm" />}
                variant="destructive"
                onContinue={() => void onClearDraft()}
              >
                <button
                  type="button"
                  disabled={clearingDraft}
                  aria-label={intl.formatMessage({ defaultMessage: 'Clear draft', id: 'Onboarding / Clear draft' })}
                  title={intl.formatMessage({ defaultMessage: 'Clear draft', id: 'Onboarding / Clear draft' })}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </ConfirmDialog>
            )}
          </div>
          <CardDescription>
            {draftMode ? (
              <FormattedMessage
                defaultMessage="Enter the details for your new organization"
                id="Tenant form / AddTenant / Card description"
              />
            ) : (
              <FormattedMessage
                defaultMessage="Tell us how your business works. You can return to earlier steps."
                id="Onboarding / Description"
              />
            )}
          </CardDescription>
          <OnboardingProgress
            step={step + 1}
            maxStep={profile?.completedAt ? SUMMARY_STEP + 1 : Math.max(3, (profile?.currentStep ?? 2) + 1)}
            onStepChange={(nextStep) => setStep(nextStep - 1)}
          />
        </CardHeader>
        <CardContent>
          <Form {...tenantForm}>
            <form
              className="space-y-6"
              noValidate
              onSubmit={(event) => {
                event.preventDefault();
                onNext();
              }}
            >
              {step === 0 && (
                <>
                  <DisplayNameField />
                  <CountryField locked={!draftMode && !!tenant?.country} />
                  <NipField locked={!draftMode && !!tenant?.nip} />
                </>
              )}
              {step === 1 && (
                <CompanyDetailsFields
                  regonLocked={!draftMode && !!tenant?.regon}
                  showLockHint={!draftMode && (!!tenant?.country || !!tenant?.nip || !!tenant?.regon)}
                />
              )}
              {step === 2 && (
                <>
                  <div>
                    <h2 className="text-base font-semibold">
                      <FormattedMessage
                        defaultMessage="Your role in the company"
                        id="Onboarding / Respondent role label"
                      />
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="This answer is descriptive and does not change your organization permissions."
                        id="Onboarding / Respondent role profile hint"
                      />
                    </p>
                  </div>
                  <ChoiceGroup
                    options={roleOptions}
                    selected={[answers.respondentRole]}
                    onChange={([respondentRole]) => update({ respondentRole })}
                  />
                  <div>
                    <h2 className="text-base font-semibold">
                      <FormattedMessage defaultMessage="Who usually pays you?" id="Onboarding / Customers title" />
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="This helps estimate how much sales data future integrations can cover."
                        id="Onboarding / Customers hint"
                      />
                    </p>
                  </div>
                  <ChoiceGroup
                    options={customerOptions}
                    selected={[answers.customerType]}
                    onChange={([customerType]) => update({ customerType })}
                  />
                </>
              )}
              {step === 3 && (
                <>
                  <div>
                    <h2 className="text-base font-semibold">
                      <FormattedMessage
                        defaultMessage="What do customers pay you for?"
                        id="Onboarding / Revenue title"
                      />
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      <FormattedMessage defaultMessage="Choose up to two." id="Onboarding / Revenue hint" />
                    </p>
                  </div>
                  <ChoiceGroup
                    options={revenueOptions}
                    selected={answers.revenueModels}
                    onChange={(revenueModels) => update({ revenueModels })}
                    max={2}
                  />
                </>
              )}
              {step === 4 && (
                <>
                  <div>
                    <h2 className="text-base font-semibold">
                      <FormattedMessage
                        defaultMessage="Which costs grow with your sales?"
                        id="Onboarding / Costs title"
                      />
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      <FormattedMessage defaultMessage="Choose up to three." id="Onboarding / Costs hint" />
                    </p>
                  </div>
                  <ChoiceGroup
                    options={costOptions}
                    selected={answers.costDrivers}
                    onChange={(costDrivers) => update({ costDrivers })}
                    max={3}
                  />
                </>
              )}
              {step === 5 && (
                <>
                  <div className="space-y-3">
                    <h2 className="text-base font-semibold">
                      <FormattedMessage
                        defaultMessage="How do you usually set prices?"
                        id="Onboarding / Pricing question"
                      />
                    </h2>
                    <ChoiceGroup
                      options={pricingOptions}
                      selected={[answers.pricing]}
                      onChange={([pricing]) => update({ pricing })}
                    />
                  </div>
                  <div className="space-y-3">
                    <h2 className="text-base font-semibold">
                      <FormattedMessage
                        defaultMessage="What do you most want to keep under control?"
                        id="Onboarding / Goal question"
                      />
                    </h2>
                    <ChoiceGroup
                      options={goalOptions}
                      selected={[answers.mainGoal]}
                      onChange={([mainGoal]) => update({ mainGoal })}
                    />
                  </div>
                </>
              )}
              {step === SUMMARY_STEP && (
                <>
                  <div>
                    <h2 className="text-base font-semibold">
                      <FormattedMessage defaultMessage="Your business profile" id="Onboarding / Summary title" />
                    </h2>
                    <p className="text-xs text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="This is a starting point for future analysis."
                        id="Onboarding / Summary hint"
                      />
                    </p>
                  </div>
                  <dl className="divide-y rounded-lg border">
                    {[
                      [
                        intl.formatMessage({
                          defaultMessage: 'Organization',
                          id: 'Tenant form / AddTenant / Step basics',
                        }),
                        tenantForm.getValues('name'),
                        0,
                      ],
                      [
                        intl.formatMessage({
                          defaultMessage: 'Company details',
                          id: 'Tenant form / AddTenant / Step company details',
                        }),
                        [
                          tenantForm.getValues('companyName'),
                          tenantForm.getValues('nip'),
                          tenantForm.getValues('regon'),
                          tenantForm.getValues('address'),
                          tenantForm.getValues('vatStatus'),
                        ]
                          .filter(Boolean)
                          .join(' · '),
                        1,
                      ],
                      [
                        intl.formatMessage({ defaultMessage: 'Your role', id: 'Onboarding / Summary role' }),
                        roleOptions.find((option) => option.value === answers.respondentRole)?.label,
                        2,
                      ],
                      [
                        intl.formatMessage({ defaultMessage: 'Customers', id: 'Onboarding / Step customers' }),
                        customerOptions.find((option) => option.value === answers.customerType)?.label,
                        2,
                      ],
                      [
                        intl.formatMessage({ defaultMessage: 'Revenue', id: 'Onboarding / Step revenue' }),
                        answers.revenueModels
                          .map((value) => revenueOptions.find((option) => option.value === value)?.label)
                          .join(', '),
                        3,
                      ],
                      [
                        intl.formatMessage({ defaultMessage: 'Costs', id: 'Onboarding / Step costs' }),
                        answers.costDrivers
                          .map((value) => costOptions.find((option) => option.value === value)?.label)
                          .join(', '),
                        4,
                      ],
                      [
                        intl.formatMessage({ defaultMessage: 'Pricing', id: 'Onboarding / Summary pricing' }),
                        pricingOptions.find((option) => option.value === answers.pricing)?.label,
                        5,
                      ],
                      [
                        intl.formatMessage({ defaultMessage: 'Main goal', id: 'Onboarding / Summary goal' }),
                        goalOptions.find((option) => option.value === answers.mainGoal)?.label,
                        5,
                      ],
                    ].map(([label, value, editStep]) => (
                      <div key={label} className="grid grid-cols-[7rem_1fr_auto] items-start gap-4 px-4 py-3 text-sm">
                        <dt className="text-muted-foreground">{label}</dt>
                        <dd className="min-w-0 break-words">{value}</dd>
                        <button
                          type="button"
                          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                          onClick={() => setStep(Number(editStep))}
                        >
                          <FormattedMessage defaultMessage="Edit" id="Onboarding / Edit" />
                        </button>
                      </div>
                    ))}
                  </dl>
                </>
              )}
              {hasTenantError && <div className="text-sm text-destructive">{tenantError}</div>}
              <div className="flex flex-col gap-3 pt-4 sm:flex-row">
                {step > 0 && (
                  <Button
                    type="button"
                    variant={ButtonVariant.SECONDARY}
                    onClick={onBack}
                    disabled={saving || savingDraft || updatingTenant || lookupLoading}
                    icon={<ArrowLeft className="h-4 w-4" />}
                    className="w-full sm:w-fit"
                  >
                    <FormattedMessage defaultMessage="Back" id="Onboarding / Back" />
                  </Button>
                )}
                <Button
                  type="submit"
                  disabled={saving || savingDraft || updatingTenant || lookupLoading || !canContinue}
                  className="w-full sm:w-fit"
                  icon={
                    saving || savingDraft || updatingTenant || lookupLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : undefined
                  }
                >
                  {step === SUMMARY_STEP ? (
                    draftMode ? (
                      <FormattedMessage
                        defaultMessage="Create organization"
                        id="Tenant form / AddTenant / Submit button"
                      />
                    ) : (
                      <FormattedMessage defaultMessage="Confirm profile" id="Onboarding / Confirm" />
                    )
                  ) : (
                    <>
                      <FormattedMessage defaultMessage="Next" id="Onboarding / Next" />
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </PageLayout>
  );
};
