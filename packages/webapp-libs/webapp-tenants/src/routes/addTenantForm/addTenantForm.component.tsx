import { useMutation } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { Form } from '@sb/webapp-core/components/forms';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { cn } from '@sb/webapp-core/lib/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { AlertTriangle, ArrowLeft, ArrowRight, Building2, CheckCircle2, Info, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router';

import {
  COMPANY_DETAILS_FIELDS,
  CompanyDetailsFields,
  CountryField,
  DisplayNameField,
  NipField,
} from '../../components/companyDetailsFields';
import { TenantFormFields } from '../../components/tenantForm/tenantForm.component';
import { useGenerateTenantPath } from '../../hooks';
import {
  CompanyDetails,
  getMissingCompanyFields,
  useCompanyLookup,
  useFormatCompanyFields,
} from '../../hooks/useCompanyLookup';
import { DEFAULT_COMPANY_COUNTRY, normalizeTaxId } from '../../utils/companyCountries';
import { normalizeDigits } from '../../utils/nip';
import { addTenantMutation } from './addTenantForm.graphql';

enum Step {
  BASICS = 1,
  COMPANY_DETAILS = 2,
}

const STEP_1_FIELDS = ['name', 'country', 'nip'] as const;

export const AddTenantForm = () => {
  const generateTenantPath = useGenerateTenantPath();
  const { toast } = useToast();
  const intl = useIntl();
  const navigate = useNavigate();
  const { reload: reloadCommonQuery } = useCommonQuery();
  const { lookup, loading: lookupLoading } = useCompanyLookup();

  const [step, setStep] = useState<Step>(Step.BASICS);
  // null = not looked up yet; true/false = whether MF returned a company for the NIP in the form
  const [companyFound, setCompanyFound] = useState<boolean | null>(null);
  const [lookedUpNip, setLookedUpNip] = useState<string>();
  // Fields the register returned empty for a found company, e.g. no REGON
  const [missingFields, setMissingFields] = useState<Array<keyof CompanyDetails>>([]);

  const { form, handleSubmit, setApolloGraphQLResponseErrors, hasGenericErrorOnly, genericError } =
    useApiForm<TenantFormFields>({
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
  // each), and keep "Create organization" disabled until all of them are filled in and valid
  useEffect(() => {
    if (step === Step.COMPANY_DETAILS) {
      trigger([...COMPANY_DETAILS_FIELDS]);
    }
  }, [step, trigger]);
  const companyValues = watch([...COMPANY_DETAILS_FIELDS]);
  const companyDetailsIncomplete = COMPANY_DETAILS_FIELDS.some(
    (field, index) => !companyValues[index] || !!errors[field]
  );

  const successMessage = intl.formatMessage({
    id: 'Tenant form / AddTenant / Success message',
    defaultMessage: 'Organization added successfully!',
  });

  const [commitTenantFormMutation, { loading: loadingMutation }] = useMutation(addTenantMutation, {
    onCompleted: (data) => {
      const id = data?.createTenant?.tenantEdge?.node?.id;
      reloadCommonQuery();

      trackEvent('tenant', 'add', id);

      toast({ description: successMessage, variant: 'success' });

      navigate(generateTenantPath(RoutesConfig.home, { tenantId: id! }));
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
  });

  const handleNext = async () => {
    if (!(await trigger([...STEP_1_FIELDS]))) return;

    const country = getValues('country');
    const nip = normalizeTaxId(getValues('nip'), country);
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
        input: {
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

  return (
    <PageLayout>
      <Card>
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
          <StepIndicator step={step} />
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
                    disabled={lookupLoading}
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
                      <FormattedMessage
                        defaultMessage="Create organization"
                        id="Tenant form / AddTenant / Submit button"
                      />
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

const StepIndicator = ({ step }: { step: Step }) => (
  <div className="flex items-center gap-3 pt-4 text-sm">
    {[Step.BASICS, Step.COMPANY_DETAILS].map((current, index) => (
      <div key={current} className="flex items-center gap-3">
        {index > 0 && <div className="h-px w-6 bg-border sm:w-10" />}
        <div className={cn('flex items-center gap-2', current === step ? 'text-foreground' : 'text-muted-foreground')}>
          <span
            className={cn(
              'flex h-6 w-6 items-center justify-center rounded-full border text-xs font-medium',
              current === step ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
            )}
          >
            {current}
          </span>
          {current === Step.BASICS ? (
            <FormattedMessage defaultMessage="Organization" id="Tenant form / AddTenant / Step basics" />
          ) : (
            <FormattedMessage defaultMessage="Company details" id="Tenant form / AddTenant / Step company details" />
          )}
        </div>
      </div>
    ))}
  </div>
);

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
            values={{ fields: <strong>{formatCompanyFields(missingFields)}</strong> }}
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
