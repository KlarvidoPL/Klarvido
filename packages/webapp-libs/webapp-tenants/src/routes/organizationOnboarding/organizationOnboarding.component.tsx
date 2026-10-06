import { useMutation, useQuery } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Form } from '@sb/webapp-core/components/forms';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardHeader } from '@sb/webapp-core/components/ui/card';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast';
import { ArrowLeft, ArrowRight, Building2, Loader2, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useLocation, useNavigate } from 'react-router';

import {
  COMPANY_DETAILS_FIELDS,
  CompanyDetailsFields,
  CountryField,
  DisplayNameField,
  NipField,
} from '../../components/companyDetailsFields';
import { VatStatus, useVatStatusLabels } from '../../components/companyDetailsFields/companyDetailsFields.component';
import { useCompanyFormErrorMessages } from '../../components/companyDetailsFields/companyFormErrors.hook';
import { OnboardingProgress } from '../../components/onboardingProgress/onboardingProgress.component';
import { TenantFormFields } from '../../components/tenantForm/tenantForm.component';
import { useGenerateTenantPath } from '../../hooks';
import { useCompanyLookup } from '../../hooks/useCompanyLookup';
import { useCurrentTenant } from '../../providers';
import { normalizeTaxId } from '../../utils/companyCountries';
import { normalizeDigits } from '../../utils/nip';
import { ChoiceQuestion } from './choiceGroup.component';
import type { OnboardingOptions, Option } from './onboardingOptions.hook';
import { useOnboardingOptions } from './onboardingOptions.hook';
import { LAST_ONBOARDING_STEP, OnboardingStep } from './onboardingSteps';
import {
  organizationOnboardingDraftQuery,
  organizationOnboardingProfileQuery,
  saveOrganizationOnboardingDraftMutation,
  saveOrganizationOnboardingStepMutation,
  updateOnboardingTenantMutation,
} from './organizationOnboarding.graphql';
import { SummaryRow, SummaryStep } from './summaryStep.component';

// Company values as stored on the tenant or in the account's draft.
type CompanyValues = Partial<Record<keyof TenantFormFields, string | null | undefined>>;

// The answers saved on the profile or draft, as returned by the API.
type ProfileValues = {
  respondentRole?: string | null;
  customerType?: string | null;
  revenueModels?: ReadonlyArray<string | null> | null;
  costDrivers?: ReadonlyArray<string | null> | null;
  pricing?: string | null;
  mainGoal?: string | null;
  currentStep?: number | null;
  completedAt?: string | null;
  isRequired?: boolean | null;
};

type Answers = {
  respondentRole: string;
  customerType: string;
  revenueModels: string[];
  costDrivers: string[];
  pricing: string;
  mainGoal: string;
};

const nonNull = (values: ReadonlyArray<string | null> | null | undefined) =>
  (values ?? []).filter((value): value is string => value !== null);

const companyDefaults = (tenant: CompanyValues | undefined) => ({
  name: tenant?.name ?? '',
  country: tenant?.country ?? '',
  nip: tenant?.nip ?? '',
  companyName: tenant?.companyName ?? '',
  regon: tenant?.regon ?? '',
  address: tenant?.address ?? '',
  vatStatus: tenant?.vatStatus ?? '',
});

const companyVariables = (values: TenantFormFields) => ({
  ...values,
  nip: normalizeTaxId(values.nip, values.country),
  regon: normalizeDigits(values.regon),
});

const isAnswerComplete = (step: number, answers: Answers) => {
  switch (step) {
    case OnboardingStep.CUSTOMERS:
      return !!answers.respondentRole && !!answers.customerType;
    case OnboardingStep.REVENUE:
      return answers.revenueModels.length > 0;
    case OnboardingStep.COSTS:
      return answers.costDrivers.length > 0;
    case OnboardingStep.PRICING:
      return !!answers.pricing && !!answers.mainGoal;
    default:
      return true;
  }
};

// Only the answers that belong to one step, as sent when that step is saved.
const answersForStep = (step: number, answers: Answers) => {
  switch (step) {
    case OnboardingStep.CUSTOMERS:
      return { respondentRole: answers.respondentRole, customerType: answers.customerType };
    case OnboardingStep.REVENUE:
      return { revenueModels: answers.revenueModels };
    case OnboardingStep.COSTS:
      return { costDrivers: answers.costDrivers };
    case OnboardingStep.PRICING:
      return { pricing: answers.pricing, mainGoal: answers.mainGoal };
    default:
      return {};
  }
};

const optionLabel = (options: Option[], value: string) => options.find((option) => option.value === value)?.label;

const optionLabels = (options: Option[], values: string[]) =>
  values.map((value) => optionLabel(options, value)).join(', ');

type OnboardingFormProps = {
  draftMode: boolean;
  tenantId: string;
  tenant: CompanyValues | undefined;
  profile: ProfileValues | null | undefined;
  options: OnboardingOptions;
  refetchProfile: () => Promise<unknown>;
  onClearDraft?: () => Promise<void>;
  clearingDraft: boolean;
};

// Mounted only once the saved data has loaded, so its state starts from that data and is not re-synced from it.
const OnboardingForm = ({
  draftMode,
  tenantId,
  tenant,
  profile,
  options,
  refetchProfile,
  onClearDraft,
  clearingDraft,
}: OnboardingFormProps) => {
  const errorMessages = useCompanyFormErrorMessages();
  const intl = useIntl();
  const navigate = useNavigate();
  const location = useLocation();
  const tenantPath = useGenerateTenantPath();
  const { toast } = useToast();
  const { reload: reloadCommonQuery } = useCommonQuery();
  const { lookup, loading: lookupLoading } = useCompanyLookup();
  const [saveDraft, { loading: savingDraft }] = useMutation(saveOrganizationOnboardingDraftMutation);
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
    defaultValues: companyDefaults(tenant),
  });

  const [step, setStep] = useState(() =>
    profile?.completedAt
      ? LAST_ONBOARDING_STEP
      : Math.max(
          OnboardingStep.CUSTOMERS,
          Math.min(profile?.currentStep ?? OnboardingStep.CUSTOMERS, LAST_ONBOARDING_STEP)
        )
  );
  const [answers, setAnswers] = useState<Answers>(() => ({
    respondentRole: profile?.respondentRole ?? '',
    customerType: profile?.customerType ?? '',
    revenueModels: nonNull(profile?.revenueModels),
    costDrivers: nonNull(profile?.costDrivers),
    pricing: profile?.pricing ?? '',
    mainGoal: profile?.mainGoal ?? '',
  }));

  const update = (patch: Partial<Answers>) => setAnswers((current) => ({ ...current, ...patch }));
  const vatStatusLabels = useVatStatusLabels();
  const canContinue = isAnswerComplete(step, answers);
  const busy = saving || savingDraft || updatingTenant || lookupLoading;

  const showCompanyError = (mutationError: unknown) => {
    const graphQLErrors = extractGraphQLErrors(mutationError);
    if (graphQLErrors) setApolloGraphQLResponseErrors(graphQLErrors);
    toast({
      description: intl.formatMessage({
        defaultMessage: 'Could not update the organization. Please check the fields and try again.',
        id: 'Onboarding / Organization save failed',
      }),
      variant: 'destructive',
    });
  };

  const showAnswerError = (mutationError: unknown) => {
    const graphQLErrors = extractGraphQLErrors(mutationError);
    if (graphQLErrors) {
      setApolloGraphQLResponseErrors(graphQLErrors);
      // Send the user back to the step that owns the field that failed validation.
      const validationError = graphQLErrors.find(({ message }) => message === 'GraphQlValidationError');
      const fieldsWithErrors = Object.keys(validationError?.extensions ?? {});
      if (['name', 'country', 'nip'].some((field) => fieldsWithErrors.includes(field))) {
        setStep(OnboardingStep.ORGANIZATION);
      } else if (
        ['companyName', 'company_name', 'regon', 'address', 'vatStatus', 'vat_status'].some((field) =>
          fieldsWithErrors.includes(field)
        )
      ) {
        setStep(OnboardingStep.COMPANY_DETAILS);
      }
    }
    toast({
      description: intl.formatMessage({
        defaultMessage: 'Could not save this step. Please try again.',
        id: 'Onboarding / Save failed',
      }),
      variant: 'destructive',
    });
  };

  const finishOnboarding = async (createdTenantId: string | undefined) => {
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
    if (createdTenantId) trackEvent('tenant', 'add', createdTenantId);
    // Set by the settings page when it opens this form, so editing returns there instead of the home page.
    const returnTo = (location.state as { returnTo?: string } | null)?.returnTo;
    navigate(returnTo ?? tenantPath(RoutesConfig.home, createdTenantId ? { tenantId: createdTenantId } : undefined));
  };

  // Steps 0 and 1: organization name and company details.
  const saveCompanyStep = async () => {
    const fields =
      step === OnboardingStep.ORGANIZATION ? (['name', 'country', 'nip'] as const) : COMPANY_DETAILS_FIELDS;
    if (!(await tenantForm.trigger([...fields]))) return;
    const values = tenantForm.getValues();
    try {
      if (!draftMode) {
        await updateTenant({
          variables: {
            input: {
              id: tenantId,
              tenantId,
              name: values.name,
              ...(step === OnboardingStep.ORGANIZATION
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
      } else if (step === OnboardingStep.ORGANIZATION) {
        // Looking up the registry only when the NIP or country changed keeps manual corrections intact.
        const nip = normalizeTaxId(values.nip, values.country);
        if (nip !== tenant?.nip || values.country !== tenant?.country) {
          const company = await lookup(nip, values.country);
          tenantForm.setValue('companyName', company?.companyName ?? '');
          tenantForm.setValue('regon', company?.regon ?? '');
          tenantForm.setValue('address', company?.address ?? '');
          tenantForm.setValue('vatStatus', company?.vatStatus ?? '');
        }
      } else {
        await saveDraft({ variables: { step: OnboardingStep.COMPANY_DETAILS, company: companyVariables(values) } });
        await refetchProfile();
      }
      setStep(step + 1);
    } catch (mutationError) {
      showCompanyError(mutationError);
    }
  };

  // Steps 2-6: the answers. The summary creates the organization (draft mode) or confirms the profile (tenant mode).
  const saveAnswersStep = async () => {
    try {
      let createdTenantId: string | undefined;
      if (draftMode) {
        const variables =
          step === OnboardingStep.SUMMARY
            ? {
                step,
                company: companyVariables(tenantForm.getValues()),
                respondentRole: answers.respondentRole,
                customerType: answers.customerType,
                revenueModels: answers.revenueModels,
                costDrivers: answers.costDrivers,
                pricing: answers.pricing,
                mainGoal: answers.mainGoal,
              }
            : { step, ...answersForStep(step, answers) };
        const result = await saveDraft({ variables });
        createdTenantId = result.data?.saveOrganizationOnboardingDraft?.tenant?.id;
      } else {
        await saveStep({ variables: { step, tenantId, ...answersForStep(step, answers) } });
      }

      if (step === OnboardingStep.SUMMARY) {
        await finishOnboarding(createdTenantId);
        return;
      }
      await refetchProfile();
      setStep(step + 1);
    } catch (mutationError) {
      showAnswerError(mutationError);
    }
  };

  const onNext = async () => {
    if ((!tenantId && !draftMode) || !canContinue) return;
    if (step < OnboardingStep.CUSTOMERS) await saveCompanyStep();
    else await saveAnswersStep();
  };

  const onBack = () => {
    if (step > OnboardingStep.ORGANIZATION) setStep(step - 1);
  };

  const summaryRows: SummaryRow[] = [
    {
      label: intl.formatMessage({ defaultMessage: 'Organization', id: 'Tenant form / AddTenant / Step basics' }),
      value: tenantForm.getValues('name'),
      editStep: OnboardingStep.ORGANIZATION,
    },
    {
      label: intl.formatMessage({
        defaultMessage: 'Company details',
        id: 'Tenant form / AddTenant / Step company details',
      }),
      value: [
        tenantForm.getValues('companyName'),
        tenantForm.getValues('nip'),
        tenantForm.getValues('regon'),
        tenantForm.getValues('address'),
        vatStatusLabels[tenantForm.getValues('vatStatus') as VatStatus] ?? tenantForm.getValues('vatStatus'),
      ]
        .filter(Boolean)
        .join(' · '),
      editStep: OnboardingStep.COMPANY_DETAILS,
    },
    {
      label: intl.formatMessage({ defaultMessage: 'Your role', id: 'Onboarding / Summary role' }),
      value: optionLabel(options.roles, answers.respondentRole),
      editStep: OnboardingStep.CUSTOMERS,
    },
    {
      label: intl.formatMessage({ defaultMessage: 'Customers', id: 'Onboarding / Step customers' }),
      value: optionLabel(options.customers, answers.customerType),
      editStep: OnboardingStep.CUSTOMERS,
    },
    {
      label: intl.formatMessage({ defaultMessage: 'Revenue', id: 'Onboarding / Step revenue' }),
      value: optionLabels(options.revenue, answers.revenueModels),
      editStep: OnboardingStep.REVENUE,
    },
    {
      label: intl.formatMessage({ defaultMessage: 'Costs', id: 'Onboarding / Step costs' }),
      value: optionLabels(options.costs, answers.costDrivers),
      editStep: OnboardingStep.COSTS,
    },
    {
      label: intl.formatMessage({ defaultMessage: 'Pricing', id: 'Onboarding / Summary pricing' }),
      value: optionLabel(options.pricing, answers.pricing),
      editStep: OnboardingStep.PRICING,
    },
    {
      label: intl.formatMessage({ defaultMessage: 'Main goal', id: 'Onboarding / Summary goal' }),
      value: optionLabel(options.goals, answers.mainGoal),
      editStep: OnboardingStep.PRICING,
    },
  ];

  return (
    <PageLayout>
      <div className="mx-auto w-full max-w-5xl space-y-8">
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-2">
            <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
              <Building2 className="h-6 w-6 shrink-0 text-primary" />
              {draftMode ? (
                <FormattedMessage defaultMessage="Add Organization" id="Tenant form / AddTenant / Card title" />
              ) : (
                <FormattedMessage defaultMessage="Set up your organization" id="Onboarding / Title" />
              )}
            </h1>
          </div>
          <p className="text-lg text-muted-foreground">
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
          </p>
        </div>
        <Card>
          <CardHeader>
            <OnboardingProgress
              step={step + 1}
              maxStep={profile?.completedAt ? LAST_ONBOARDING_STEP + 1 : Math.max(3, (profile?.currentStep ?? 2) + 1)}
              onStepChange={(nextStep) => setStep(nextStep - 1)}
            />
          </CardHeader>
          <CardContent>
            <Form {...tenantForm}>
              <form
                className="space-y-8"
                noValidate
                onSubmit={(event) => {
                  event.preventDefault();
                  onNext();
                }}
              >
                {step === OnboardingStep.ORGANIZATION && (
                  <>
                    <DisplayNameField />
                    <CountryField locked={!draftMode && !!tenant?.country} />
                    <NipField locked={!draftMode && !!tenant?.nip} />
                  </>
                )}
                {step === OnboardingStep.COMPANY_DETAILS && (
                  <CompanyDetailsFields
                    regonLocked={!draftMode && !!tenant?.regon}
                    showLockHint={!draftMode && (!!tenant?.country || !!tenant?.nip || !!tenant?.regon)}
                  />
                )}
                {step === OnboardingStep.CUSTOMERS && (
                  <>
                    <ChoiceQuestion
                      title={
                        <FormattedMessage
                          defaultMessage="Your role in the company"
                          id="Onboarding / Respondent role label"
                        />
                      }
                      hint={
                        <FormattedMessage
                          defaultMessage="This answer is descriptive and does not change your organization permissions."
                          id="Onboarding / Respondent role profile hint"
                        />
                      }
                      options={options.roles}
                      selected={[answers.respondentRole]}
                      onChange={([respondentRole]) => update({ respondentRole })}
                    />
                    <ChoiceQuestion
                      title={
                        <FormattedMessage defaultMessage="Who usually pays you?" id="Onboarding / Customers title" />
                      }
                      hint={
                        <FormattedMessage
                          defaultMessage="This helps estimate how much sales data future integrations can cover."
                          id="Onboarding / Customers hint"
                        />
                      }
                      options={options.customers}
                      selected={[answers.customerType]}
                      onChange={([customerType]) => update({ customerType })}
                    />
                  </>
                )}
                {step === OnboardingStep.REVENUE && (
                  <ChoiceQuestion
                    title={
                      <FormattedMessage
                        defaultMessage="What do customers pay you for?"
                        id="Onboarding / Revenue title"
                      />
                    }
                    hint={<FormattedMessage defaultMessage="Choose up to two." id="Onboarding / Revenue hint" />}
                    options={options.revenue}
                    selected={answers.revenueModels}
                    onChange={(revenueModels) => update({ revenueModels })}
                    max={2}
                  />
                )}
                {step === OnboardingStep.COSTS && (
                  <ChoiceQuestion
                    title={
                      <FormattedMessage
                        defaultMessage="Which costs grow with your sales?"
                        id="Onboarding / Costs title"
                      />
                    }
                    hint={<FormattedMessage defaultMessage="Choose up to three." id="Onboarding / Costs hint" />}
                    options={options.costs}
                    selected={answers.costDrivers}
                    onChange={(costDrivers) => update({ costDrivers })}
                    max={3}
                  />
                )}
                {step === OnboardingStep.PRICING && (
                  <>
                    <div className="space-y-3">
                      <ChoiceQuestion
                        title={
                          <FormattedMessage
                            defaultMessage="How do you usually set prices?"
                            id="Onboarding / Pricing question"
                          />
                        }
                        options={options.pricing}
                        selected={[answers.pricing]}
                        onChange={([pricing]) => update({ pricing })}
                      />
                    </div>
                    <div className="space-y-3">
                      <ChoiceQuestion
                        title={
                          <FormattedMessage
                            defaultMessage="What do you most want to keep under control?"
                            id="Onboarding / Goal question"
                          />
                        }
                        options={options.goals}
                        selected={[answers.mainGoal]}
                        onChange={([mainGoal]) => update({ mainGoal })}
                      />
                    </div>
                  </>
                )}
                {step === OnboardingStep.SUMMARY && <SummaryStep rows={summaryRows} onEdit={setStep} />}
                {hasTenantError && <div className="text-sm text-destructive">{tenantError}</div>}
                <div className="flex flex-col gap-3 pt-4 sm:flex-row sm:items-center">
                  {step > OnboardingStep.ORGANIZATION && (
                    <Button
                      type="button"
                      variant={ButtonVariant.SECONDARY}
                      onClick={onBack}
                      disabled={busy}
                      icon={<ArrowLeft className="h-4 w-4" />}
                      className="w-full sm:w-fit"
                    >
                      <FormattedMessage defaultMessage="Back" id="Onboarding / Back" />
                    </Button>
                  )}
                  <Button
                    type="submit"
                    disabled={busy || !canContinue}
                    className="w-full sm:w-fit"
                    icon={busy ? <Loader2 className="h-4 w-4 animate-spin" /> : undefined}
                  >
                    {step === OnboardingStep.SUMMARY ? (
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
                  {draftMode && onClearDraft && (
                    <ConfirmDialog
                      title={
                        <FormattedMessage defaultMessage="Clear this draft?" id="Onboarding / Clear draft title" />
                      }
                      description={
                        <FormattedMessage
                          defaultMessage="All answers for this new organization will be deleted. This cannot be undone."
                          id="Onboarding / Clear draft description"
                        />
                      }
                      continueLabel={
                        <FormattedMessage defaultMessage="Clear draft" id="Onboarding / Clear draft confirm" />
                      }
                      variant="destructive"
                      onContinue={() => void onClearDraft()}
                    >
                      <button
                        type="button"
                        disabled={clearingDraft}
                        aria-label={intl.formatMessage({
                          defaultMessage: 'Clear draft',
                          id: 'Onboarding / Clear draft',
                        })}
                        title={intl.formatMessage({ defaultMessage: 'Clear draft', id: 'Onboarding / Clear draft' })}
                        className="mt-3 flex h-10 w-full shrink-0 cursor-pointer items-center justify-center gap-2 rounded-md border text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 sm:ml-auto sm:mt-0 sm:w-auto sm:border-0 sm:px-3"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                        <span>
                          <FormattedMessage defaultMessage="Clear draft" id="Onboarding / Clear draft" />
                        </span>
                      </button>
                    </ConfirmDialog>
                  )}
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
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
  const { data: currentTenant } = useCurrentTenant();
  const tenantId = draftMode ? '' : (currentTenant?.id ?? '');
  const draftQuery = useQuery(organizationOnboardingDraftQuery, { skip: !draftMode, fetchPolicy: 'network-only' });
  const profileQuery = useQuery(organizationOnboardingProfileQuery, {
    variables: { tenantId },
    skip: draftMode || !tenantId,
    fetchPolicy: 'network-only',
  });
  const { options, error: optionsError } = useOnboardingOptions();

  const source = draftMode ? draftQuery : profileQuery;
  if (source.error || optionsError)
    return (
      <PageLayout>
        <p className="p-8 text-destructive">
          <FormattedMessage defaultMessage="Could not load the business profile." id="Onboarding / Load failed" />
        </p>
      </PageLayout>
    );
  // Keep local step and answer state when refreshing an already loaded profile.
  if (!options || !source.data)
    return (
      <PageLayout>
        <div className="flex justify-center p-8">
          <Loader2 className="animate-spin" />
        </div>
      </PageLayout>
    );

  const profile = draftMode
    ? draftQuery.data?.organizationOnboardingDraft
    : profileQuery.data?.organizationOnboardingProfile;
  const tenant = draftMode
    ? (draftQuery.data?.organizationOnboardingDraft?.companyData ?? undefined)
    : (currentTenant ?? undefined);
  const refetchProfile = () => (draftMode ? draftQuery.refetch() : profileQuery.refetch());

  return (
    <OnboardingForm
      key={draftMode ? 'draft' : tenantId}
      draftMode={draftMode}
      tenantId={tenantId}
      tenant={tenant}
      profile={profile}
      options={options}
      refetchProfile={refetchProfile}
      onClearDraft={onClearDraft}
      clearingDraft={clearingDraft}
    />
  );
};
