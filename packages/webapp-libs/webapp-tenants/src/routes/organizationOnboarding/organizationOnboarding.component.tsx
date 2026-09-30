import { useMutation, useQuery } from '@apollo/client/react';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { cn } from '@sb/webapp-core/lib/utils';
import { useToast } from '@sb/webapp-core/toast';
import { ArrowLeft, ArrowRight, Building2, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router';

import { RoutesConfig as TenantRoutesConfig } from '../../config/routes';
import { useGenerateTenantPath } from '../../hooks';
import { useCurrentTenant } from '../../providers';
import {
  organizationOnboardingProfileQuery,
  saveOrganizationOnboardingStepMutation,
} from './organizationOnboarding.graphql';

type Option = { value: string; label: string; hint?: string };
type Answers = {
  respondentRole: string;
  customerType: string;
  revenueModels: string[];
  costDrivers: string[];
  pricing: string;
  mainGoal: string;
  ksefToken: string;
  ksefDemoConnected: boolean;
};

const initialAnswers: Answers = {
  respondentRole: '',
  customerType: '',
  revenueModels: [],
  costDrivers: [],
  pricing: '',
  mainGoal: '',
  ksefToken: '',
  ksefDemoConnected: false,
};

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
}) => (
  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {options.map((option) => {
      const active = selected.includes(option.value);
      return (
        <button
          key={option.value}
          type="button"
          aria-pressed={active}
          className={cn(
            'min-h-24 rounded-lg border bg-card p-4 text-left transition-colors hover:border-primary',
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
          <span className="block font-medium">{option.label}</span>
          {option.hint && <span className="mt-1 block text-sm text-muted-foreground">{option.hint}</span>}
        </button>
      );
    })}
  </div>
);

export const OrganizationOnboarding = () => {
  const { data: tenant } = useCurrentTenant();
  const tenantId = tenant?.id ?? '';
  const navigate = useNavigate();
  const tenantPath = useGenerateTenantPath();
  const intl = useIntl();
  const { toast } = useToast();
  const [step, setStep] = useState(2);
  const [answers, setAnswers] = useState<Answers>(initialAnswers);
  const [loaded, setLoaded] = useState(false);
  const { data, loading, error, refetch } = useQuery(organizationOnboardingProfileQuery, {
    variables: { tenantId },
    skip: !tenantId,
    fetchPolicy: 'network-only',
  });
  const [saveStep, { loading: saving }] = useMutation(saveOrganizationOnboardingStepMutation);
  const profile = data?.organizationOnboardingProfile;
  const steps = [
    intl.formatMessage({ defaultMessage: 'Company', id: 'Onboarding / Step company' }),
    intl.formatMessage({ defaultMessage: 'Customers', id: 'Onboarding / Step customers' }),
    intl.formatMessage({ defaultMessage: 'Revenue', id: 'Onboarding / Step revenue' }),
    intl.formatMessage({ defaultMessage: 'Costs', id: 'Onboarding / Step costs' }),
    intl.formatMessage({ defaultMessage: 'Pricing & goal', id: 'Onboarding / Step pricing goal' }),
    intl.formatMessage({ defaultMessage: 'Data', id: 'Onboarding / Step data' }),
    intl.formatMessage({ defaultMessage: 'Summary', id: 'Onboarding / Step summary' }),
  ];

  useEffect(() => {
    if (!data || loaded) return;
    let customerDraft: Pick<Answers, 'respondentRole' | 'customerType'> | null = null;
    try {
      const savedDraft = sessionStorage.getItem(`organization-onboarding-customers:${tenantId}`);
      if (savedDraft) {
        const parsed = JSON.parse(savedDraft);
        if (typeof parsed.respondentRole === 'string' && typeof parsed.customerType === 'string') {
          customerDraft = parsed;
        }
      }
    } catch {
      // Browsers may disable session storage; the saved profile remains available.
    }
    setAnswers({
      respondentRole: customerDraft?.respondentRole ?? profile?.respondentRole ?? '',
      customerType: customerDraft?.customerType ?? profile?.customerType ?? '',
      revenueModels: (profile?.revenueModels ?? []).filter((value): value is string => value !== null),
      costDrivers: (profile?.costDrivers ?? []).filter((value): value is string => value !== null),
      pricing: profile?.pricing ?? '',
      mainGoal: profile?.mainGoal ?? '',
      ksefToken: '',
      ksefDemoConnected: profile?.ksefStatus === 'demo',
    });
    setStep(profile?.completedAt ? 7 : Math.max(2, Math.min(profile?.currentStep ?? 2, 7)));
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
  const tokenLength = Array.from(answers.ksefToken).length;
  const canContinue =
    step === 2
      ? !!answers.respondentRole && !!answers.customerType
      : step === 3
        ? answers.revenueModels.length > 0
        : step === 4
          ? answers.costDrivers.length > 0
          : step === 5
            ? !!answers.pricing && !!answers.mainGoal
            : step === 6
              ? (answers.ksefDemoConnected && tokenLength === 0) || tokenLength === 40
              : true;

  const onNext = async () => {
    if (!tenantId || !canContinue) return;
    if (step === 6 && answers.ksefDemoConnected && tokenLength === 0) {
      setStep(7);
      return;
    }
    try {
      await saveStep({
        variables: {
          tenantId,
          step,
          ...(step === 2 ? { respondentRole: answers.respondentRole, customerType: answers.customerType } : {}),
          ...(step === 3 ? { revenueModels: answers.revenueModels } : {}),
          ...(step === 4 ? { costDrivers: answers.costDrivers } : {}),
          ...(step === 5 ? { pricing: answers.pricing, mainGoal: answers.mainGoal } : {}),
          ...(step === 6 ? { ksefToken: answers.ksefToken } : {}),
        },
      });
      if (step === 6) update({ ksefToken: '', ksefDemoConnected: true });
      await refetch();
      if (step === 2) {
        try {
          sessionStorage.removeItem(`organization-onboarding-customers:${tenantId}`);
        } catch {
          // The profile has already been saved on the server.
        }
      }
      if (step === 7) {
        toast({
          description: intl.formatMessage({ defaultMessage: 'Onboarding completed', id: 'Onboarding / Completed' }),
          variant: 'success',
        });
        navigate(tenantPath(RoutesConfig.home));
      } else setStep(step + 1);
    } catch {
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
    if (step === 2) {
      try {
        sessionStorage.setItem(
          `organization-onboarding-customers:${tenantId}`,
          JSON.stringify({ respondentRole: answers.respondentRole, customerType: answers.customerType })
        );
      } catch {
        // Navigation still works if session storage is unavailable.
      }
      navigate(tenantPath(TenantRoutesConfig.tenant.settings.general));
    } else {
      setStep(step - 1);
    }
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
      <Card className="mx-auto w-full max-w-5xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            <FormattedMessage defaultMessage="Set up your organization" id="Onboarding / Title" />
          </CardTitle>
          <CardDescription>
            <FormattedMessage
              defaultMessage="Tell us how your business works. You can return to earlier steps."
              id="Onboarding / Description"
            />
          </CardDescription>
          <div
            className="flex flex-wrap gap-2 pt-4"
            aria-label={intl.formatMessage({ defaultMessage: 'Onboarding steps', id: 'Onboarding / Steps label' })}
          >
            {steps.map((label, index) => (
              <span
                key={label}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs',
                  index + 1 === step ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
                )}
              >
                {index + 1}. {label}
              </span>
            ))}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {step === 2 && (
            <>
              <div>
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="Your role in the company" id="Onboarding / Respondent role label" />
                </h2>
                <p className="text-sm text-muted-foreground">
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
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="Who usually pays you?" id="Onboarding / Customers title" />
                </h2>
                <p className="text-sm text-muted-foreground">
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
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="What do customers pay you for?" id="Onboarding / Revenue title" />
                </h2>
                <p className="text-sm text-muted-foreground">
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
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="Which costs grow with your sales?" id="Onboarding / Costs title" />
                </h2>
                <p className="text-sm text-muted-foreground">
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
              <div>
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="How do you make key decisions?" id="Onboarding / Pricing title" />
                </h2>
              </div>
              <div className="space-y-3">
                <h3 className="font-medium">
                  <FormattedMessage
                    defaultMessage="How do you usually set prices?"
                    id="Onboarding / Pricing question"
                  />
                </h3>
                <ChoiceGroup
                  options={pricingOptions}
                  selected={[answers.pricing]}
                  onChange={([pricing]) => update({ pricing })}
                />
              </div>
              <div className="space-y-3">
                <h3 className="font-medium">
                  <FormattedMessage
                    defaultMessage="What do you most want to keep under control?"
                    id="Onboarding / Goal question"
                  />
                </h3>
                <ChoiceGroup
                  options={goalOptions}
                  selected={[answers.mainGoal]}
                  onChange={([mainGoal]) => update({ mainGoal })}
                />
              </div>
            </>
          )}
          {step === 6 && (
            <>
              <div>
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="KSeF demo" id="Onboarding / KSeF title" />
                </h2>
                <p className="text-sm text-muted-foreground">
                  <FormattedMessage
                    defaultMessage="This is a demonstration only. No connection to KSeF or invoice synchronization will occur."
                    id="Onboarding / KSeF disclaimer"
                  />
                </p>
              </div>
              <div className="max-w-lg space-y-2">
                <label htmlFor="ksef-demo-token" className="text-sm font-medium">
                  <FormattedMessage
                    defaultMessage="Demo token (exactly 40 characters)"
                    id="Onboarding / KSeF token label"
                  />
                </label>
                <input
                  id="ksef-demo-token"
                  type="password"
                  autoComplete="off"
                  value={answers.ksefToken}
                  onChange={(event) => update({ ksefToken: event.target.value })}
                  className="h-10 w-full rounded-md border border-input bg-background px-3"
                />
                <p className="text-sm text-muted-foreground">{tokenLength}/40</p>
                {answers.ksefDemoConnected && (
                  <p className="text-sm text-emerald-700">
                    <FormattedMessage
                      defaultMessage="Demo token saved. Enter a new 40-character value to replace it."
                      id="Onboarding / KSeF saved"
                    />
                  </p>
                )}
              </div>
            </>
          )}
          {step === 7 && (
            <>
              <div>
                <h2 className="text-xl font-semibold">
                  <FormattedMessage defaultMessage="Your business profile" id="Onboarding / Summary title" />
                </h2>
                <p className="text-sm text-muted-foreground">
                  <FormattedMessage
                    defaultMessage="This is a starting point for future analysis."
                    id="Onboarding / Summary hint"
                  />
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  [steps[1], customerOptions.find((option) => option.value === answers.customerType)?.label],
                  [
                    steps[2],
                    answers.revenueModels
                      .map((value) => revenueOptions.find((option) => option.value === value)?.label)
                      .join(', '),
                  ],
                  [
                    steps[3],
                    answers.costDrivers
                      .map((value) => costOptions.find((option) => option.value === value)?.label)
                      .join(', '),
                  ],
                  [
                    intl.formatMessage({ defaultMessage: 'Pricing', id: 'Onboarding / Summary pricing' }),
                    pricingOptions.find((option) => option.value === answers.pricing)?.label,
                  ],
                  [
                    intl.formatMessage({ defaultMessage: 'Main goal', id: 'Onboarding / Summary goal' }),
                    goalOptions.find((option) => option.value === answers.mainGoal)?.label,
                  ],
                  [
                    'KSeF',
                    answers.ksefDemoConnected
                      ? intl.formatMessage({
                          defaultMessage: 'Demo token saved',
                          id: 'Onboarding / Summary KSeF saved',
                        })
                      : intl.formatMessage({ defaultMessage: 'Not set', id: 'Onboarding / Summary not set' }),
                  ],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border p-4">
                    <div className="text-sm text-muted-foreground">{label}</div>
                    <div className="font-medium">{value}</div>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="flex flex-col gap-3 pt-4 sm:flex-row">
            <Button
              type="button"
              variant={ButtonVariant.SECONDARY}
              onClick={onBack}
              disabled={saving}
              icon={<ArrowLeft className="h-4 w-4" />}
            >
              <FormattedMessage defaultMessage="Back" id="Onboarding / Back" />
            </Button>
            <Button
              type="button"
              onClick={onNext}
              disabled={saving || !canContinue}
              className="w-full sm:w-fit"
              icon={saving ? <Loader2 className="h-4 w-4 animate-spin" /> : undefined}
            >
              {step === 7 ? (
                <FormattedMessage defaultMessage="Confirm profile" id="Onboarding / Confirm" />
              ) : (
                <>
                  <FormattedMessage defaultMessage="Next" id="Onboarding / Next" />
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </PageLayout>
  );
};
