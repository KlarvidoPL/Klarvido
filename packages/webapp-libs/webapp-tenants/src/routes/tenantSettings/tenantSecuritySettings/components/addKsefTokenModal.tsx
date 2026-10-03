import { useApiForm } from '@sb/webapp-api-client/hooks';
import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { Input } from '@sb/webapp-core/components/forms';
import { Small } from '@sb/webapp-core/components/typography';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { ExternalLink, KeyRound, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

import { useTenantKsef } from '../../../../hooks/useTenantKsef';
import { getKsefErrorMessage } from './ksefErrors';

export type AddKsefTokenModalProps = {
  tenantId: string;
  closeModal: () => void;
  onSaved: () => void;
};

type KsefTokenFormFields = {
  token: string;
};

// Public KSeF web application (Aplikacja Podatnika), where the token is generated.
const KSEF_WEB_APP_URL = 'https://ksef.mf.gov.pl';

export const AddKsefTokenModal = ({ tenantId, closeModal, onSaved }: AddKsefTokenModalProps) => {
  const intl = useIntl();
  const { toast } = useToast();
  const { setToken } = useTenantKsef(tenantId, false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const form = useApiForm<KsefTokenFormFields>();
  const {
    handleSubmit,
    form: {
      register,
      formState: { errors, isSubmitting },
    },
  } = form;

  const submitHandler = async (values: KsefTokenFormFields) => {
    setErrorMessage(null);
    let result;
    try {
      const { data } = await setToken({ variables: { tenantId, token: values.token } });
      result = data?.setKsefToken;
    } catch {
      setErrorMessage(getKsefErrorMessage(intl, null));
      return;
    }

    if (!result?.ok) {
      // The token itself is never echoed back; only the error code is shown.
      setErrorMessage(getKsefErrorMessage(intl, result?.errorCode));
      return;
    }

    if (result.ksefCredential?.status === 'UNVERIFIED') {
      toast({
        description: intl.formatMessage({
          id: 'KSeF / Saved unverified toast',
          defaultMessage:
            'Token saved. KSeF could not be reached, so it is not verified yet. Test the connection later.',
        }),
        variant: 'warning',
      });
    } else {
      toast({
        description: intl.formatMessage({
          id: 'KSeF / Saved toast',
          defaultMessage: 'KSeF token verified and saved.',
        }),
        variant: 'success',
      });
    }
    onSaved();
    closeModal();
  };

  const steps = [
    {
      title: intl.formatMessage({ id: 'KSeF / Step 1 title', defaultMessage: 'Open the KSeF web application' }),
      description: intl.formatMessage({
        id: 'KSeF / Step 1 description',
        defaultMessage: 'Log in to KSeF with an account that is authorized for your company.',
      }),
    },
    {
      title: intl.formatMessage({ id: 'KSeF / Step 2 title', defaultMessage: 'Generate a new token' }),
      description: intl.formatMessage({
        id: 'KSeF / Step 2 description',
        defaultMessage:
          'Open the Tokens section and generate a new token. Grant only the invoice read permission (InvoiceRead). Do not grant write permissions.',
      }),
    },
    {
      title: intl.formatMessage({ id: 'KSeF / Step 3 title', defaultMessage: 'Copy the token' }),
      description: intl.formatMessage({
        id: 'KSeF / Step 3 description',
        defaultMessage: 'KSeF shows the token only once. Copy it right away, before closing that window.',
      }),
    },
    {
      title: intl.formatMessage({ id: 'KSeF / Step 4 title', defaultMessage: 'Paste it below' }),
      description: intl.formatMessage({
        id: 'KSeF / Step 4 description',
        defaultMessage:
          'We check the token with KSeF before saving it. Stored tokens are encrypted and never shown again.',
      }),
    },
  ];

  return (
    <form
      onSubmit={handleSubmit(submitHandler)}
      className="-m-6 flex h-[85vh] max-h-[700px] flex-col overflow-hidden sm:rounded-lg"
    >
      {/* Fixed Header */}
      <div className="flex shrink-0 items-center gap-3 border-b bg-background px-6 py-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <KeyRound className="h-5 w-5 text-primary" />
        </div>
        <div className="mr-8">
          <h2 className="text-lg font-semibold">
            <FormattedMessage id="KSeF / Modal title" defaultMessage="Connect KSeF" />
          </h2>
          <p className="text-sm text-muted-foreground">
            <FormattedMessage
              id="KSeF / Modal subtitle"
              defaultMessage="Connect a KSeF token so invoices can be read from KSeF"
            />
          </p>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5">
        <ol className="space-y-5">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">
                {index + 1}
              </div>
              <div className="flex-1 space-y-1">
                <h3 className="text-sm font-medium">{step.title}</h3>
                <p className="text-sm text-muted-foreground">{step.description}</p>
                {index === 0 && (
                  <a
                    href={KSEF_WEB_APP_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
                  >
                    {KSEF_WEB_APP_URL}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </li>
          ))}
        </ol>

        <div className="flex-1 space-y-3 rounded-lg border p-4">
          <h3 className="text-sm font-medium">
            <FormattedMessage id="KSeF / Token input label" defaultMessage="KSeF token" />
          </h3>
          <Input
            {...register('token', {
              required: {
                value: true,
                message: intl.formatMessage({ id: 'KSeF / Token required', defaultMessage: 'Paste the KSeF token' }),
              },
            })}
            type="password"
            autoComplete="off"
            spellCheck={false}
            autoFocus
            error={errors.token?.message}
            className="w-full font-mono"
          />
          {errorMessage && (
            <div className="text-sm text-destructive dark:text-red-400" role="alert">
              <Small>{errorMessage}</Small>
            </div>
          )}
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 shrink-0" />
            <FormattedMessage
              id="KSeF / Token security note"
              defaultMessage="The token is encrypted before it is stored and cannot be viewed again after saving."
            />
          </p>
        </div>
      </div>

      {/* Fixed Footer */}
      <div className="flex shrink-0 gap-3 border-t bg-background px-6 py-4">
        <Button type="button" variant={ButtonVariant.SECONDARY} onClick={closeModal} className="flex-1">
          <FormattedMessage id="KSeF / Cancel button" defaultMessage="Cancel" />
        </Button>
        <Button type="submit" className="flex-1" disabled={isSubmitting}>
          <FormattedMessage id="KSeF / Verify and save button" defaultMessage="Verify and save" />
        </Button>
      </div>
    </form>
  );
};
