import { useApolloClient, useMutation, useQuery } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent } from '@sb/webapp-core/components/ui/card';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Label } from '@sb/webapp-core/components/ui/label';
import { OtpInput } from '@sb/webapp-core/components/ui/otpInput';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { getPasskeyAuthorizationErrorMessage, useWebAuthn } from '@sb/webapp-sso/hooks';
import { useGenerateTenantPath } from '@sb/webapp-tenants/hooks';
import { AlertTriangle, ArrowRight, Building2, Fingerprint, LockKeyhole } from 'lucide-react';
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
      confirmation: {
        last_owner: intl.formatMessage({
          id: 'Account deletion / Ownership blocker',
          defaultMessage: 'Transfer ownership to another accepted member or delete these organizations first:',
        }),
        last_administrator: intl.formatMessage({
          id: 'Account deletion / Last administrator',
          defaultMessage: 'The last active administrator cannot delete their account.',
        }),
        personal_organization_review: intl.formatMessage({
          id: 'Account deletion / Personal organization review',
          defaultMessage: 'Your personal organization requires administrator review before account deletion.',
        }),
        confirmation_mismatch: intl.formatMessage({
          id: 'Account deletion / Confirmation mismatch',
          defaultMessage: 'Enter your exact account email address to confirm deletion.',
        }),
      },
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
    <Card>
      <CardContent className="pt-6">
        <div className="space-y-6">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-destructive dark:text-red-400" aria-hidden="true" />
            <h3 className="text-lg font-semibold text-destructive dark:text-red-400">
              <FormattedMessage defaultMessage="Danger Zone" id="Tenant General Settings / Danger Zone / Header" />
            </h3>
          </div>
          <div className="rounded-lg border-2 border-destructive/50 bg-destructive/5 p-6 dark:border-red-400/50">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 space-y-2">
                <div className="font-semibold text-foreground">
                  <FormattedMessage id="Account deletion / Title" defaultMessage="Delete account" />
                </div>
                <p className="text-sm text-muted-foreground">
                  <FormattedMessage
                    id="Account deletion / Description"
                    defaultMessage="Permanently delete your account and personal files. Shared organization content and historical attribution remain. Historical backups expire according to the backup retention policy."
                  />
                </p>
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
              </div>
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
                hideContinue={!currentUser?.hasUsablePassword}
                additionalActionSeparator={
                  currentUser?.hasUsablePassword && <FormattedMessage defaultMessage="or" id="Passkeys / Or" />
                }
                additionalAction={
                  hasPasskey && (
                    <Button
                      variant={currentUser?.hasUsablePassword ? 'outline' : 'destructive'}
                      className="h-auto min-h-10 w-full gap-2 whitespace-normal py-3 text-center"
                      disabled={busy || confirmation !== currentUser?.email || (!!requiresOtp && otp.length !== 6)}
                      onClick={() => remove(true)}
                    >
                      <Fingerprint className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <FormattedMessage
                        id="Account deletion / Passkey"
                        defaultMessage="Confirm deletion with a passkey"
                      />
                    </Button>
                  )
                }
                title={
                  <FormattedMessage
                    id="Account deletion / Confirm title"
                    defaultMessage="Permanently delete your account?"
                  />
                }
                description={
                  <FormattedMessage
                    id="Account deletion / Confirm description"
                    defaultMessage="This cannot be undone. You will lose access on all devices. Enter your email and confirm your identity to continue."
                  />
                }
                feedback={
                  (error ||
                    apiForm.form.formState.errors.otpToken?.message ||
                    apiForm.form.formState.errors.confirmation?.message ||
                    apiForm.genericError) && (
                    <div className="space-y-2" aria-live="polite">
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
                  )
                }
                content={
                  <div className="space-y-4">
                    <div className="space-y-2">
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
                      <div className="space-y-2">
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
                  </div>
                }
              >
                <Button
                  variant="destructive"
                  className="shrink-0"
                  disabled={loading || !!eligibilityError || blockers.length > 0 || !canAuthenticate || busy}
                >
                  <FormattedMessage id="Account deletion / Title" defaultMessage="Delete account" />
                </Button>
              </ConfirmDialog>
            </div>
            {blockers.length > 0 && (
              <div className="mt-5 rounded-lg border bg-background/60 p-4">
                <div className="flex items-start gap-3">
                  <LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    <FormattedMessage
                      id="Account deletion / Ownership blocker"
                      defaultMessage="Transfer ownership to another accepted member or delete these organizations first:"
                    />
                  </p>
                </div>
                <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                  {blockers.map(
                    (tenant) =>
                      tenant && (
                        <li key={tenant.id}>
                          <Link
                            className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-3 py-2.5 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            to={generateTenantPath(RoutesConfig.tenant.settings.members, { tenantId: tenant.id })}
                          >
                            <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span className="min-w-0 break-words">{tenant.name}</span>
                            <ArrowRight
                              className="ml-auto h-4 w-4 shrink-0 text-muted-foreground rtl:rotate-180"
                              aria-hidden="true"
                            />
                          </Link>
                        </li>
                      )
                  )}
                </ul>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
