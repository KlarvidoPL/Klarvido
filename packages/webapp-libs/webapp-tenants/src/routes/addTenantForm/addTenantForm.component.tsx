import { useMutation } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { Form, Input } from '@sb/webapp-core/components/forms';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { cn } from '@sb/webapp-core/lib/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { ArrowLeft, ArrowRight, Building2, CheckCircle2, Info, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router';

import { CompanyDetailsFields, NipField } from '../../components/companyDetailsFields';
import { TenantFormFields } from '../../components/tenantForm/tenantForm.component';
import { useGenerateTenantPath } from '../../hooks';
import { useCompanyLookup } from '../../hooks/useCompanyLookup';
import { normalizeDigits } from '../../utils/nip';
import { addTenantMutation } from './addTenantForm.graphql';

const MAX_NAME_LENGTH = 255;

enum Step {
  BASICS = 1,
  COMPANY_DETAILS = 2,
}

const STEP_1_FIELDS = ['name', 'nip'] as const;

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

  const { form, handleSubmit, setApolloGraphQLResponseErrors, hasGenericErrorOnly, genericError } =
    useApiForm<TenantFormFields>({
      defaultValues: { name: '', nip: '', companyName: '', regon: '', address: '', vatStatus: '' },
    });
  const {
    register,
    formState: { errors },
    trigger,
    getValues,
    setValue,
  } = form;

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

    const nip = normalizeDigits(getValues('nip'));
    // Only (re)query MF when the NIP changed, so going Back/Next doesn't wipe the user's manual edits
    if (nip !== lookedUpNip) {
      const company = await lookup(nip);
      setValue('companyName', company?.companyName ?? '');
      setValue('regon', company?.regon ?? '');
      setValue('address', company?.address ?? '');
      setValue('vatStatus', company?.vatStatus ?? '');
      setCompanyFound(!!company);
      setLookedUpNip(nip);
    }
    setStep(Step.COMPANY_DETAILS);
  };

  const onSubmit = handleSubmit((formData: TenantFormFields) => {
    commitTenantFormMutation({
      variables: {
        input: {
          name: formData.name,
          nip: normalizeDigits(formData.nip),
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
      <Card className="mx-auto w-full max-w-3xl">
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
                  <Input
                    {...register('name', {
                      maxLength: {
                        value: MAX_NAME_LENGTH,
                        message: intl.formatMessage({
                          defaultMessage: 'Name is too long',
                          id: 'Tenant form / Name max length error',
                        }),
                      },
                      required: {
                        value: true,
                        message: intl.formatMessage({
                          defaultMessage: 'Name is required',
                          id: 'Tenant form / Name required',
                        }),
                      },
                    })}
                    label={intl.formatMessage({ defaultMessage: 'Name:', id: 'Tenant Form / Name label' })}
                    placeholder={intl.formatMessage({ defaultMessage: 'Name', id: 'Tenant form / Name placeholder' })}
                    error={errors.name?.message}
                  />
                  <NipField />
                </>
              )}

              {step === Step.COMPANY_DETAILS && (
                <>
                  <LookupResultNote found={!!companyFound} />
                  <CompanyDetailsFields />
                </>
              )}

              {hasGenericErrorOnly && (
                <div className="text-sm text-destructive dark:text-red-400">
                  <span>{genericError}</span>
                </div>
              )}

              <div className="mt-2 flex flex-col gap-3 sm:flex-row">
                {step === Step.BASICS ? (
                  <Button
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
                      type="button"
                      variant={ButtonVariant.SECONDARY}
                      onClick={() => setStep(Step.BASICS)}
                      disabled={loadingMutation}
                      className="w-full sm:w-fit"
                      icon={<ArrowLeft className="h-4 w-4" />}
                    >
                      <FormattedMessage defaultMessage="Back" id="Tenant form / AddTenant / Back button" />
                    </Button>
                    <Button type="submit" disabled={loadingMutation} className="w-full sm:w-fit">
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

const LookupResultNote = ({ found }: { found: boolean }) => (
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
