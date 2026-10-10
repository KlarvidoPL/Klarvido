import { useApolloClient, useMutation, useQuery } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Label } from '@sb/webapp-core/components/ui/label';
import { OtpInput } from '@sb/webapp-core/components/ui/otpInput';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { getPasskeyAuthorizationErrorMessage, useWebAuthn } from '@sb/webapp-sso/hooks';
import { useGenerateTenantPath } from '@sb/webapp-tenants/hooks';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { Link } from 'react-router';

import { RoutesConfig } from '../../app/config/routes';
import { useAuth } from '../../shared/hooks';
import { accountDeletionEligibilityQuery, deleteAccountMutation } from './accountDeletion.graphql';

export const AccountDeletion = () => {
  const intl = useIntl();
  const { currentUser } = useAuth();
  const client = useApolloClient();
  const generateLocalePath = useGenerateLocalePath();
  const generateTenantPath = useGenerateTenantPath();
  const { authorizePasskeyChange } = useWebAuthn();
  const { data, loading, error: eligibilityError, refetch } = useQuery(accountDeletionEligibilityQuery);
  const [commit] = useMutation(deleteAccountMutation);
  const [confirmation, setConfirmation] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const apiForm = useApiForm<{ confirmation: string; otpToken: string }>({
    errorMessages: {
      otpToken: {
        otp_verification_failure: intl.formatMessage({
          id: 'Auth / OTP / Invalid code',
          defaultMessage: 'The verification code is invalid.',
        }),
        otp_attempt_limit_exceeded: intl.formatMessage({
          id: 'Auth / OTP / Attempt limit',
          defaultMessage: 'Too many incorrect codes. Try again in 15 minutes.',
        }),
      },
    },
  });
  const hasPasskey = data?.myPasskeys?.edges?.some((edge) => edge?.node?.isActive);
  const requiresOtp = currentUser?.otpEnabled && currentUser?.otpVerified;
  const canAuthenticate = currentUser?.hasUsablePassword || hasPasskey;
  const blockers = data?.accountDeletionBlockers ?? [];

  const remove = async (withPasskey = false) => {
    if (busy) return;
    setBusy(true);
    setError('');
    apiForm.form.clearErrors();
    try {
      const authorization = await authorizePasskeyChange(
        'account_delete',
        undefined,
        withPasskey ? undefined : password
      );
      const result = await commit({
        variables: { input: { confirmation, otpToken: requiresOtp ? otp : undefined } },
        context: { headers: { 'X-Passkey-Authorization': authorization } },
      });
      if (!result.data?.deleteAccount?.ok) throw new Error('Deletion failed');
      await client.clearStore();
      window.location.replace(generateLocalePath('/'));
    } catch (failure) {
      const errors = extractGraphQLErrors(failure);
      if (errors) apiForm.setApolloGraphQLResponseErrors(errors);
      else setError(intl.formatMessage(getPasskeyAuthorizationErrorMessage(failure)));
      setOtp('');
      void refetch();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-destructive/50 dark:border-red-400/50">
      <CardHeader>
        <CardTitle>
          <FormattedMessage id="Account deletion / Title" defaultMessage="Delete account" />
        </CardTitle>
        <CardDescription>
          <FormattedMessage
            id="Account deletion / Description"
            defaultMessage="Permanently delete your account and personal files. Shared organization content and historical attribution remain. Historical backups expire according to the backup retention policy."
          />
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {blockers.length > 0 && (
          <div>
            <p>
              <FormattedMessage
                id="Account deletion / Ownership blocker"
                defaultMessage="Transfer ownership to another accepted member or delete these organizations first:"
              />
            </p>
            <ul>
              {blockers.map(
                (tenant) =>
                  tenant && (
                    <li key={tenant.id}>
                      <Link
                        className="underline"
                        to={generateTenantPath(RoutesConfig.tenant.settings.members, { tenantId: tenant.id })}
                      >
                        {tenant.name}
                      </Link>
                    </li>
                  )
              )}
            </ul>
          </div>
        )}
        {!loading && !canAuthenticate && (
          <p>
            <FormattedMessage
              id="Account deletion / Set password"
              defaultMessage="Set a password using the verified password setup flow above before deleting your account."
            />
          </p>
        )}
        {eligibilityError && (
          <p role="alert">
            <FormattedMessage
              id="Account deletion / Eligibility error"
              defaultMessage="Could not check account deletion eligibility. Please reload and try again."
            />
          </p>
        )}
        <ConfirmDialog
          variant="destructive"
          closeOnContinue={false}
          onContinue={() => remove()}
          onOpenChange={() => {
            setConfirmation('');
            setPassword('');
            setOtp('');
            setError('');
            apiForm.form.reset();
            void refetch();
          }}
          continueDisabled={
            busy || confirmation !== currentUser?.email || !password || (!!requiresOtp && otp.length !== 6)
          }
          title={
            <FormattedMessage id="Account deletion / Confirm title" defaultMessage="Permanently delete your account?" />
          }
          description={
            <FormattedMessage
              id="Account deletion / Confirm description"
              defaultMessage="This cannot be undone. You will lose access on all devices. Enter your email and confirm your identity to continue."
            />
          }
          content={
            <div className="space-y-4">
              <div>
                <Label htmlFor="delete-account-email">
                  <FormattedMessage id="Account deletion / Email" defaultMessage="Your email address" />
                </Label>
                <Input
                  id="delete-account-email"
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                  disabled={busy}
                  autoComplete="off"
                />
              </div>
              {currentUser?.hasUsablePassword && (
                <div>
                  <Label htmlFor="delete-account-password">
                    <FormattedMessage id="Account deletion / Password" defaultMessage="Current password" />
                  </Label>
                  <Input
                    id="delete-account-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={busy}
                  />
                </div>
              )}
              {requiresOtp && (
                <OtpInput
                  label={intl.formatMessage({
                    id: 'Auth / Change password / OTP label',
                    defaultMessage: 'Authentication code',
                  })}
                  value={otp}
                  onValueChange={setOtp}
                  disabled={busy}
                />
              )}
              {hasPasskey && (
                <Button
                  variant="destructive"
                  disabled={busy || confirmation !== currentUser?.email || (!!requiresOtp && otp.length !== 6)}
                  onClick={() => remove(true)}
                >
                  <FormattedMessage id="Account deletion / Passkey" defaultMessage="Confirm deletion with a passkey" />
                </Button>
              )}
              {error && (
                <p role="alert" className="text-sm text-destructive dark:text-red-400">
                  {error}
                </p>
              )}
              {(apiForm.form.formState.errors.otpToken?.message ||
                apiForm.form.formState.errors.confirmation?.message ||
                apiForm.genericError) && (
                <p role="alert" className="text-sm text-destructive dark:text-red-400">
                  {apiForm.form.formState.errors.otpToken?.message ||
                    apiForm.form.formState.errors.confirmation?.message ||
                    apiForm.genericError}
                </p>
              )}
            </div>
          }
        >
          <Button
            variant="destructive"
            disabled={loading || !!eligibilityError || blockers.length > 0 || !canAuthenticate || busy}
          >
            <FormattedMessage id="Account deletion / Title" defaultMessage="Delete account" />
          </Button>
        </ConfirmDialog>
      </CardContent>
    </Card>
  );
};
