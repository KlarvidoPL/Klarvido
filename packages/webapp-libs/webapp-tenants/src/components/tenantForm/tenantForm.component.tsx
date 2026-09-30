import { Button, ButtonVariant, Link } from '@sb/webapp-core/components/buttons';
import { Form, FormControl, FormField, FormItem, Input } from '@sb/webapp-core/components/forms';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast';
import { Loader2, RefreshCw } from 'lucide-react';
import { ReactNode } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

import { useCompanyLookup } from '../../hooks/useCompanyLookup';
import { isValidNip } from '../../utils/nip';
import { CompanyDetailsFields, CompanyDetailsFormFields, NipField } from '../companyDetailsFields';
import { useTenantForm } from './tenantForm.hook';

const MAX_NAME_LENGTH = 255;

export type TenantFormFields = CompanyDetailsFormFields & {
  name: string;
};

export type TenantFormProps = {
  initialData?: Partial<TenantFormFields> | null;
  onSubmit: (formData: TenantFormFields) => void;
  loading: boolean;
  error?: Error;
  /** Custom submit button label, defaults to "Save changes" */
  submitLabel?: ReactNode;
  /** Custom cancel URL, defaults to home route */
  cancelUrl?: string;
  /** Hide cancel button */
  hideCancel?: boolean;
  /** Disable the form (read-only mode) */
  disabled?: boolean;
  /** Show NIP + company details (organizations only; the personal default tenant has none) */
  showCompanyDetails?: boolean;
};

export const TenantForm = ({
  initialData,
  onSubmit,
  error,
  loading,
  submitLabel,
  cancelUrl,
  hideCancel,
  disabled,
  showCompanyDetails,
}: TenantFormProps) => {
  const intl = useIntl();
  const { toast } = useToast();
  const generateLocalePath = useGenerateLocalePath();
  const { lookup, loading: lookupLoading } = useCompanyLookup();

  const {
    form: {
      register,
      formState: { errors },
      control,
      getValues,
      setValue,
      trigger,
    },
    form,
    genericError,
    hasGenericErrorOnly,
    handleFormSubmit,
  } = useTenantForm({ initialData, onSubmit, error });

  const defaultCancelUrl = generateLocalePath(RoutesConfig.home);

  const handleRefreshFromMF = async () => {
    if (!(await trigger('nip')) || !isValidNip(getValues('nip'))) return;

    const company = await lookup(getValues('nip'));
    if (!company) {
      toast({
        description: intl.formatMessage({
          defaultMessage: 'No company found for this NIP in the Ministry of Finance register.',
          id: 'Tenant form / Refresh from MF / Not found',
        }),
        variant: 'warning',
      });
      return;
    }

    (Object.keys(company) as Array<keyof typeof company>).forEach((field) =>
      setValue(field, company[field], { shouldDirty: true, shouldValidate: true })
    );
    toast({
      description: intl.formatMessage({
        defaultMessage: 'Company details refreshed. Save changes to keep them.',
        id: 'Tenant form / Refresh from MF / Success',
      }),
      variant: 'info',
    });
  };

  return (
    <Form {...form}>
      <form className="flex flex-col gap-4" onSubmit={handleFormSubmit} noValidate>
        <FormField
          control={control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormControl>
                <Input
                  {...field}
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
                  label={intl.formatMessage({
                    defaultMessage: 'Name:',
                    id: 'Tenant Form / Name label',
                  })}
                  placeholder={intl.formatMessage({
                    defaultMessage: 'Name',
                    id: 'Tenant form / Name placeholder',
                  })}
                  error={errors.name?.message}
                  disabled={disabled}
                />
              </FormControl>
            </FormItem>
          )}
        />

        {showCompanyDetails && (
          <>
            <NipField
              disabled={disabled}
              action={
                !disabled && (
                  <Button
                    type="button"
                    variant={ButtonVariant.SECONDARY}
                    onClick={handleRefreshFromMF}
                    disabled={lookupLoading}
                    className="w-full sm:w-fit"
                    icon={
                      lookupLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />
                    }
                  >
                    <FormattedMessage defaultMessage="Refresh from MF" id="Tenant form / Refresh from MF button" />
                  </Button>
                )
              }
            />
            <CompanyDetailsFields disabled={disabled} />
          </>
        )}

        {hasGenericErrorOnly && (
          <div className="text-sm text-destructive dark:text-red-400">
            <span>{genericError}</span>
          </div>
        )}

        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          {!hideCancel && (
            <Link to={cancelUrl ?? defaultCancelUrl} variant={ButtonVariant.SECONDARY} className="w-full sm:w-fit">
              <FormattedMessage defaultMessage="Cancel" id="Tenant form / Cancel button" />
            </Link>
          )}

          <Button type="submit" disabled={loading || disabled} className="w-full sm:w-fit">
            {submitLabel ?? <FormattedMessage defaultMessage="Save changes" id="Tenant form / Submit button" />}
          </Button>
        </div>
      </form>
    </Form>
  );
};
