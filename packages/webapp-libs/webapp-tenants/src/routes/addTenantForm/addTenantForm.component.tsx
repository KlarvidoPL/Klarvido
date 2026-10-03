import { useLazyQuery, useMutation, useQuery } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { Form } from '@sb/webapp-core/components/forms';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { cn } from '@sb/webapp-core/lib/utils';
import { AlertTriangle, ArrowLeft, ArrowRight, Building2, CheckCircle2, Info, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

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
import {
  CompanyDetails,
  getMissingCompanyFields,
  useCompanyLookup,
  useFormatCompanyFields,
} from '../../hooks/useCompanyLookup';
import { DEFAULT_COMPANY_COUNTRY, normalizeTaxId } from '../../utils/companyCountries';
import { normalizeDigits } from '../../utils/nip';
import { OrganizationOnboarding } from '../organizationOnboarding/organizationOnboarding.component';
import {
  organizationNipExistsQuery,
  organizationOnboardingDraftQuery,
  saveOrganizationOnboardingDraftMutation,
} from '../organizationOnboarding/organizationOnboarding.graphql';

enum Step {
  BASICS = 1,
  COMPANY_DETAILS = 2,
}

const STEP_1_FIELDS = ['name', 'country', 'nip'] as const;

export const AddTenantForm = () => {
  const errorMessages = useCompanyFormErrorMessages();
  const intl = useIntl();
  const {
    data: draft,
    loading: draftLoading,
    error: draftError,
    refetch: refetchDraft,
  } = useQuery(organizationOnboardingDraftQuery, { fetchPolicy: 'network-only' });
  const [checkNip, { loading: checkingNip }] = useLazyQuery(organizationNipExistsQuery, {
    fetchPolicy: 'network-only',
  });
  const { lookup, loading: lookupLoading } = useCompanyLookup();

  const [step, setStep] = useState<Step>(Step.BASICS);
  // null = not looked up yet; true/false = whether MF returned a company for the NIP in the form
  const [companyFound, setCompanyFound] = useState<boolean | null>(null);
  const [lookedUpNip, setLookedUpNip] = useState<string>();
  // Fields the register returned empty for a found company, e.g. no REGON
  const [missingFields, setMissingFields] = useState<Array<keyof CompanyDetails>>([]);

  const { form, handleSubmit, setApolloGraphQLResponseErrors, hasGenericErrorOnly, genericError } =
    useApiForm<TenantFormFields>({
      errorMessages,
      mode: 'onChange',
      defaultValues: {
        name: '',
        country: DEFAULT_COMPANY_COUNTRY,
        nip: '',
        companyName: '',
        regon: '',
        address: '',
        vatStatus: '',
      },
    });
  const {
    formState: { errors },
    trigger,
    getValues,
    setValue,
    watch,
  } = form;

  // Every company field is required: as soon as step 2 opens, flag the ones the register didn't fill (red error on
  // each), and keep "Next" disabled until all of them are filled in and valid
  useEffect(() => {
    if (step === Step.COMPANY_DETAILS) {
      trigger([...COMPANY_DETAILS_FIELDS]);
    }
  }, [step, trigger]);
  const companyValues = watch([...COMPANY_DETAILS_FIELDS]);
  const companyDetailsIncomplete = COMPANY_DETAILS_FIELDS.some(
    (field, index) => !companyValues[index] || !!errors[field]
  );

  const [commitTenantFormMutation, { loading: loadingMutation }] = useMutation(
    saveOrganizationOnboardingDraftMutation,
    {
      onCompleted: async () => {
        await refetchDraft();
      },
      onError: (error) => {
        const graphQLErrors = extractGraphQLErrors(error);
        if (!graphQLErrors) return;
        setApolloGraphQLResponseErrors(graphQLErrors);

        // Name/NIP errors can only be fixed on the first step
        const validationError = graphQLErrors.find(({ message }) => message === 'GraphQlValidationError');
        const fieldsWithErrors = Object.keys(validationError?.extensions ?? {});
        if (STEP_1_FIELDS.some((field) => fieldsWithErrors.includes(field))) {
          setStep(Step.BASICS);
        }
      },
    }
  );

  const handleNext = async () => {
    if (!(await trigger([...STEP_1_FIELDS]))) return;

    const country = getValues('country');
    const nip = normalizeTaxId(getValues('nip'), country);
    try {
      const result = await checkNip({ variables: { nip, country } });
      if (result.data?.organizationNipExists) {
        form.setError('nip', {
          message: intl.formatMessage({
            defaultMessage: 'An organization with this NIP already exists in your account.',
            id: 'Onboarding / Duplicate NIP',
          }),
        });
        return;
      }
    } catch {
      form.setError('nip', {
        message: intl.formatMessage({
          defaultMessage: 'Could not verify this NIP. Please try again.',
          id: 'Onboarding / NIP check failed',
        }),
      });
      return;
    }
    const lookupKey = `${country}:${nip}`;
    // Only (re)query the registry when the country/NIP changed, so going Back/Next doesn't wipe the user's manual edits
    if (lookupKey !== lookedUpNip) {
      const company = await lookup(nip, country);
      setValue('companyName', company?.companyName ?? '');
      setValue('regon', company?.regon ?? '');
      setValue('address', company?.address ?? '');
      setValue('vatStatus', company?.vatStatus ?? '');
      setCompanyFound(!!company);
      setMissingFields(company ? getMissingCompanyFields(company) : []);
      setLookedUpNip(lookupKey);
    }
    setStep(Step.COMPANY_DETAILS);
  };

  const onSubmit = handleSubmit((formData: TenantFormFields) => {
    commitTenantFormMutation({
      variables: {
        step: 1,
        company: {
          name: formData.name,
          country: formData.country,
          nip: normalizeTaxId(formData.nip, formData.country),
          companyName: formData.companyName,
          regon: normalizeDigits(formData.regon),
          address: formData.address,
          vatStatus: formData.vatStatus,
        },
      },
    });
  });

  if (draftLoading)
    return (
      <PageLayout>
        <Loader2 className="mx-auto my-8 animate-spin" />
      </PageLayout>
    );
  if (draftError)
    return (
      <PageLayout>
        <p className="p-8 text-destructive">
          <FormattedMessage defaultMessage="Could not load the business profile." id="Onboarding / Load failed" />
        </p>
      </PageLayout>
    );
  if (draft?.organizationOnboardingDraft) return <OrganizationOnboarding draftMode />;

  return (
    <PageLayout>
      <Card className="mx-auto w-full max-w-screen-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            <FormattedMessage defaultMessage="Add Organization" id="Tenant form / AddTenant / Card title" />
          </CardTitle>
          <CardDescription>
            <FormattedMessage
              defaultMessage="Enter the details for your new organization"
              id="Tenant form / AddTenant / Card description"
            />
          </CardDescription>
          <OnboardingProgress step={step} />
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              className="flex flex-col gap-4"
              noValidate
              onSubmit={(event) => {
                if (step === Step.BASICS) {
                  event.preventDefault();
                  handleNext();
                  return;
                }
                onSubmit(event);
              }}
            >
              {step === Step.BASICS && (
                <>
                  <DisplayNameField />
                  <CountryField />
                  <NipField />
                </>
              )}

              {step === Step.COMPANY_DETAILS && (
                <>
                  <LookupResultNote found={!!companyFound} missingFields={missingFields} />
                  <CompanyDetailsFields />
                </>
              )}

              {hasGenericErrorOnly && (
                <div className="text-sm text-destructive dark:text-red-400">
                  <span>{genericError}</span>
                </div>
              )}

              <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                {/* Distinct keys: without them React reuses the same <button> across steps, so clicking Back flips
                    it to type="submit" mid-click and the browser submits the form (= Next) right back to step 2 */}
                {step === Step.BASICS ? (
                  <Button
                    key="next"
                    type="submit"
                    disabled={lookupLoading || checkingNip}
                    className="w-full sm:w-fit"
                    icon={lookupLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : undefined}
                  >
                    <FormattedMessage defaultMessage="Next" id="Tenant form / AddTenant / Next button" />
                    {!lookupLoading && <ArrowRight className="ml-2 h-4 w-4" />}
                  </Button>
                ) : (
                  <>
                    <Button
                      key="back"
                      type="button"
                      variant={ButtonVariant.SECONDARY}
                      onClick={() => setStep(Step.BASICS)}
                      disabled={loadingMutation}
                      className="w-full sm:w-fit"
                      icon={<ArrowLeft className="h-4 w-4" />}
                    >
                      <FormattedMessage defaultMessage="Back" id="Tenant form / AddTenant / Back button" />
                    </Button>
                    <Button
                      key="create"
                      type="submit"
                      disabled={loadingMutation || companyDetailsIncomplete}
                      className="w-full sm:w-fit"
                    >
                      <FormattedMessage defaultMessage="Next" id="Tenant form / AddTenant / Next button" />
                    </Button>
                  </>
                )}
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </PageLayout>
  );
};

const LookupResultNote = ({ found, missingFields }: { found: boolean; missingFields: Array<keyof CompanyDetails> }) => {
  const formatCompanyFields = useFormatCompanyFields();

  if (found && missingFields.length > 0) {
    return (
      <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        {/* One text node: FormattedMessage with rich values renders several siblings, which the flex row would split */}
        <span>
          <FormattedMessage
            defaultMessage="We found your company in the Ministry of Finance register, but it has no {fields} for it. Please check the details below and fill in what's missing."
            id="Tenant form / AddTenant / Lookup found partial"
            values={{ fields: <strong key="missing-fields">{formatCompanyFields(missingFields)}</strong> }}
          />
        </span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex items-start gap-2 rounded-md border px-3 py-2 text-sm',
        found ? 'border-green-500/30 bg-green-500/5' : 'border-border bg-muted/50'
      )}
    >
      {found ? (
        <>
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
          <FormattedMessage
            defaultMessage="We found your company in the Ministry of Finance register and filled in the details below. Please check them before continuing."
            id="Tenant form / AddTenant / Lookup found"
          />
        </>
      ) : (
        <>
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <FormattedMessage
            defaultMessage="We couldn't find this NIP in the Ministry of Finance register. Please fill in the company details yourself."
            id="Tenant form / AddTenant / Lookup not found"
          />
        </>
      )}
    </div>
  );
};
