import { FormControl, FormField, FormItem, FormLabel, FormMessage, Input } from '@sb/webapp-core/components/forms';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@sb/webapp-core/components/ui/select';
import { cn } from '@sb/webapp-core/lib/utils';
import { Lock } from 'lucide-react';
import { ReactNode } from 'react';
import { useFormContext } from 'react-hook-form';
import { FormattedMessage, useIntl } from 'react-intl';

import { isValidNip, isValidRegon } from '../../utils/nip';

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

/** Company fields other than NIP - rendered by `CompanyDetailsFields`, all required. */
export const COMPANY_DETAILS_FIELDS = ['companyName', 'regon', 'address', 'vatStatus'] as const;

const MAX_DISPLAY_NAME_LENGTH = 255;
const MAX_COMPANY_NAME_LENGTH = 255;
const MAX_ADDRESS_LENGTH = 500;

// NIP/REGON never change for a company, so once saved they're read-only (the backend rejects a change too).
// readOnly rather than disabled: the value must still be submitted with the rest of the form.
const LOCKED_INPUT_CLASS = '[&_input]:cursor-not-allowed [&_input]:bg-muted [&_input]:text-muted-foreground';

export type DisplayNameFieldProps = {
  disabled?: boolean;
};

/**
 * The organization's name as shown inside the app (organization switcher, sidebar...) - distinct from the registered
 * company name. Must be rendered inside a `<Form>` whose fields include `name`.
 */
export const DisplayNameField = ({ disabled }: DisplayNameFieldProps) => {
  const intl = useIntl();
  const {
    register,
    formState: { errors },
  } = useFormContext<{ name: string }>();

  return (
    <div className="flex flex-col gap-1.5">
      <Input
        {...register('name', {
          required: {
            value: true,
            message: intl.formatMessage({
              defaultMessage: 'Display name is required',
              id: 'Tenant form / Display name required',
            }),
          },
          maxLength: {
            value: MAX_DISPLAY_NAME_LENGTH,
            message: intl.formatMessage({
              defaultMessage: 'Display name is too long',
              id: 'Tenant form / Display name max length error',
            }),
          },
        })}
        label={intl.formatMessage({ defaultMessage: 'Display name:', id: 'Tenant form / Display name label' })}
        placeholder={intl.formatMessage({
          defaultMessage: 'Display name',
          id: 'Tenant form / Display name placeholder',
        })}
        error={errors.name?.message}
        disabled={disabled}
      />
      <p className="text-sm text-muted-foreground">
        <FormattedMessage
          defaultMessage="Shown in the app, e.g. in the organization switcher. It doesn't have to match the registered company name."
          id="Tenant form / Display name hint"
        />
      </p>
    </div>
  );
};

export type NipFieldProps = {
  disabled?: boolean;
  /** Read-only: the organization's NIP is already saved */
  locked?: boolean;
  /** Rendered next to the input, e.g. a "Refresh from MF" button */
  action?: ReactNode;
};

/** NIP input with checksum validation. Must be rendered inside a `<Form>` whose fields include `nip`. */
export const NipField = ({ disabled, locked, action }: NipFieldProps) => {
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
        readOnly={locked}
        className={cn(locked && LOCKED_INPUT_CLASS)}
      />
      {action && <div className="shrink-0 sm:mt-6">{action}</div>}
    </div>
  );
};

export type CompanyDetailsFieldsProps = {
  disabled?: boolean;
  /** Read-only REGON: the organization's REGON is already saved */
  regonLocked?: boolean;
  /** Show the "NIP and REGON can't be changed" hint under REGON (the NIP field sits right above it) */
  showLockHint?: boolean;
};

/**
 * REGON, company name, address and VAT status inputs (all required), shared by the Add Organization wizard and the
 * General settings form. Must be rendered inside a `<Form>` whose fields include `CompanyDetailsFormFields`.
 */
export const CompanyDetailsFields = ({ disabled, regonLocked, showLockHint }: CompanyDetailsFieldsProps) => {
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
        {...register('regon', {
          required: {
            value: true,
            message: intl.formatMessage({
              defaultMessage: 'REGON is required',
              id: 'Tenant form / REGON required',
            }),
          },
          validate: (value) =>
            isValidRegon(value) ||
            intl.formatMessage({ defaultMessage: 'Invalid REGON number', id: 'Tenant form / REGON invalid' }),
        })}
        label={intl.formatMessage({ defaultMessage: 'REGON:', id: 'Tenant form / REGON label' })}
        placeholder={intl.formatMessage({ defaultMessage: '9 or 14 digits', id: 'Tenant form / REGON placeholder' })}
        inputMode="numeric"
        autoComplete="off"
        error={errors.regon?.message}
        disabled={disabled}
        readOnly={regonLocked}
        className={cn(regonLocked && LOCKED_INPUT_CLASS)}
      />
      {showLockHint && (
        <p className="-mt-2.5 flex items-center gap-1.5 text-sm text-muted-foreground">
          <Lock className="h-3.5 w-3.5 shrink-0" />
          <FormattedMessage
            defaultMessage="NIP and REGON can't be changed once saved."
            id="Tenant form / NIP and REGON locked hint"
          />
        </p>
      )}

      <Input
        {...register('companyName', {
          required: {
            value: true,
            message: intl.formatMessage({
              defaultMessage: 'Company name is required',
              id: 'Tenant form / Company name required',
            }),
          },
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
        {...register('address', {
          required: {
            value: true,
            message: intl.formatMessage({
              defaultMessage: 'Address is required',
              id: 'Tenant form / Address required',
            }),
          },
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
        rules={{
          required: {
            value: true,
            message: intl.formatMessage({
              defaultMessage: 'VAT status is required',
              id: 'Tenant form / VAT status required',
            }),
          },
        }}
        render={({ field }) => (
          <FormItem>
            <FormLabel>
              {intl.formatMessage({ defaultMessage: 'VAT status:', id: 'Tenant form / VAT status label' })}
            </FormLabel>
            <Select onValueChange={field.onChange} value={field.value || undefined} disabled={disabled}>
              <FormControl>
                <SelectTrigger onBlur={field.onBlur}>
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
            <FormMessage className="font-normal leading-tight" />
          </FormItem>
        )}
      />
    </div>
  );
};
