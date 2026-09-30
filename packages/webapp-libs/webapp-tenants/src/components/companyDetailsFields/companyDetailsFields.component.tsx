import { FormControl, FormField, FormItem, FormLabel, Input } from '@sb/webapp-core/components/forms';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@sb/webapp-core/components/ui/select';
import { ReactNode } from 'react';
import { useFormContext } from 'react-hook-form';
import { useIntl } from 'react-intl';

import { isValidNip, isValidRegon, normalizeDigits } from '../../utils/nip';

export enum VatStatus {
  ACTIVE = 'ACTIVE',
  EXEMPT = 'EXEMPT',
  NOT_REGISTERED = 'NOT_REGISTERED',
}

export type CompanyDetailsFormFields = {
  nip: string;
  companyName: string;
  regon: string;
  address: string;
  vatStatus: string;
};

const MAX_COMPANY_NAME_LENGTH = 255;
const MAX_ADDRESS_LENGTH = 500;

export type NipFieldProps = {
  disabled?: boolean;
  /** Rendered next to the input, e.g. a "Refresh from MF" button */
  action?: ReactNode;
};

/** NIP input with checksum validation. Must be rendered inside a `<Form>` whose fields include `nip`. */
export const NipField = ({ disabled, action }: NipFieldProps) => {
  const intl = useIntl();
  const {
    register,
    formState: { errors },
  } = useFormContext<CompanyDetailsFormFields>();

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
      <Input
        {...register('nip', {
          required: {
            value: true,
            message: intl.formatMessage({
              defaultMessage: 'NIP is required',
              id: 'Tenant form / NIP required',
            }),
          },
          validate: (value) =>
            isValidNip(value) ||
            intl.formatMessage({
              defaultMessage: 'Invalid NIP number',
              id: 'Tenant form / NIP invalid',
            }),
        })}
        label={intl.formatMessage({ defaultMessage: 'NIP:', id: 'Tenant form / NIP label' })}
        placeholder={intl.formatMessage({ defaultMessage: '10-digit tax ID', id: 'Tenant form / NIP placeholder' })}
        inputMode="numeric"
        autoComplete="off"
        error={errors.nip?.message}
        disabled={disabled}
      />
      {action && <div className="shrink-0 sm:mt-6">{action}</div>}
    </div>
  );
};

export type CompanyDetailsFieldsProps = {
  disabled?: boolean;
};

/**
 * Company name, REGON, address and VAT status inputs, shared by the Add Organization wizard and the General
 * settings form. Must be rendered inside a `<Form>` whose fields include `CompanyDetailsFormFields`.
 */
export const CompanyDetailsFields = ({ disabled }: CompanyDetailsFieldsProps) => {
  const intl = useIntl();
  const {
    register,
    control,
    formState: { errors },
  } = useFormContext<CompanyDetailsFormFields>();

  const vatStatusLabels: Record<VatStatus, string> = {
    [VatStatus.ACTIVE]: intl.formatMessage({
      defaultMessage: 'Active VAT payer',
      id: 'Tenant form / VAT status active',
    }),
    [VatStatus.EXEMPT]: intl.formatMessage({
      defaultMessage: 'Exempt from VAT',
      id: 'Tenant form / VAT status exempt',
    }),
    [VatStatus.NOT_REGISTERED]: intl.formatMessage({
      defaultMessage: 'Not registered for VAT',
      id: 'Tenant form / VAT status not registered',
    }),
  };

  return (
    <div className="flex flex-col gap-4">
      <Input
        {...register('companyName', {
          maxLength: {
            value: MAX_COMPANY_NAME_LENGTH,
            message: intl.formatMessage({
              defaultMessage: 'Company name is too long',
              id: 'Tenant form / Company name max length error',
            }),
          },
        })}
        label={intl.formatMessage({ defaultMessage: 'Company name:', id: 'Tenant form / Company name label' })}
        placeholder={intl.formatMessage({
          defaultMessage: 'Registered company name',
          id: 'Tenant form / Company name placeholder',
        })}
        error={errors.companyName?.message}
        disabled={disabled}
      />

      <Input
        {...register('regon', {
          validate: (value) =>
            !normalizeDigits(value) ||
            isValidRegon(value) ||
            intl.formatMessage({ defaultMessage: 'Invalid REGON number', id: 'Tenant form / REGON invalid' }),
        })}
        label={intl.formatMessage({ defaultMessage: 'REGON:', id: 'Tenant form / REGON label' })}
        placeholder={intl.formatMessage({ defaultMessage: '9 or 14 digits', id: 'Tenant form / REGON placeholder' })}
        inputMode="numeric"
        autoComplete="off"
        error={errors.regon?.message}
        disabled={disabled}
      />

      <Input
        {...register('address', {
          maxLength: {
            value: MAX_ADDRESS_LENGTH,
            message: intl.formatMessage({
              defaultMessage: 'Address is too long',
              id: 'Tenant form / Address max length error',
            }),
          },
        })}
        label={intl.formatMessage({ defaultMessage: 'Address:', id: 'Tenant form / Address label' })}
        placeholder={intl.formatMessage({
          defaultMessage: 'Street, postal code, city',
          id: 'Tenant form / Address placeholder',
        })}
        error={errors.address?.message}
        disabled={disabled}
      />

      <FormField
        control={control}
        name="vatStatus"
        render={({ field }) => (
          <FormItem>
            <FormLabel>
              {intl.formatMessage({ defaultMessage: 'VAT status:', id: 'Tenant form / VAT status label' })}
            </FormLabel>
            <Select onValueChange={field.onChange} value={field.value || undefined} disabled={disabled}>
              <FormControl>
                <SelectTrigger>
                  <SelectValue
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Select VAT status',
                      id: 'Tenant form / VAT status placeholder',
                    })}
                  />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                {Object.values(VatStatus).map((status) => (
                  <SelectItem value={status} key={status}>
                    {vatStatusLabels[status]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormItem>
        )}
      />
    </div>
  );
};
