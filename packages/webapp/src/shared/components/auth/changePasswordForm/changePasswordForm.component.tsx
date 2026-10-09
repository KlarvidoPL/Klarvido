import { useMutation } from '@apollo/client/react';
import { getFragmentData } from '@sb/webapp-api-client/graphql';
import { commonQueryCurrentUserFragment, useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button } from '@sb/webapp-core/components/buttons';
import { Input } from '@sb/webapp-core/components/forms';
import {
  PasswordRequirements,
  PasswordStrengthIndicator,
  validatePassword,
} from '@sb/webapp-core/components/passwordStrength';
import { Small } from '@sb/webapp-core/components/typography';
import { OtpInput } from '@sb/webapp-core/components/ui/otpInput';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { BaseSyntheticEvent, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

import { OtpReauthDialog } from '../twoFactorAuthForm/otpReauthDialog.component';
import { requestPasswordSetLinkMutation } from './changePasswordForm.graphql';
import { useChangePasswordForm } from './changePasswordForm.hooks';

export type ChangePasswordFormProps = {
  hasUsablePassword: boolean;
};

export const ChangePasswordForm = ({ hasUsablePassword }: ChangePasswordFormProps) => {
  const intl = useIntl();
  const { toast } = useToast();
  const { data: commonData } = useCommonQuery();
  const currentUser = getFragmentData(commonQueryCurrentUserFragment, commonData?.currentUser);
  const otpEnabled = currentUser?.otpEnabled === true;
  const { passkeys } = useTenantPasskeys();

  // E04: a bare session is not fresh-auth proof for setting a first password on a
  // passwordless account. An account with a passkey or 2FA proves freshness through the
  // same grant 2FA setup/disable already uses; an account with neither has no stronger
  // factor and gets an emailed one-time link instead (see requestPasswordSetLinkMutation).
  const canUseGrant = !hasUsablePassword && (passkeys.length > 0 || otpEnabled);
  const needsEmailLink = !hasUsablePassword && !canUseGrant;

  const [pendingReauth, setPendingReauth] = useState(false);
  const [requestingLink, setRequestingLink] = useState(false);

  const {
    form: {
      formState: { errors },
      register,
      getValues,
      watch,
      setValue,
    },
    genericError,
    hasGenericErrorOnly,
    loading,
    handleChangePassword,
  } = useChangePasswordForm(hasUsablePassword, otpEnabled);

  const [commitRequestPasswordSetLinkMutation] = useMutation(requestPasswordSetLinkMutation, {
    variables: { input: {} },
  });

  const newPassword = watch('newPassword') || '';

  const handleRequestLink = async () => {
    setRequestingLink(true);
    try {
      await commitRequestPasswordSetLinkMutation();
      toast({
        description: intl.formatMessage({
          defaultMessage: "We've emailed you a link to set your password.",
          id: 'Auth / Change password / Set link sent',
        }),
        variant: 'success',
      });
    } catch {
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Something went wrong. Please try again.',
          id: 'Auth / Change password / Set link failed',
        }),
        variant: 'destructive',
      });
    } finally {
      setRequestingLink(false);
    }
  };

  if (needsEmailLink) {
    return (
      <div className="w-full space-y-4">
        <p className="text-sm text-muted-foreground">
          <FormattedMessage
            defaultMessage="This account doesn't have a password yet. We'll email you a link to set one."
            id="Auth / Change password / Set link description"
          />
        </p>
        <Button disabled={requestingLink} onClick={handleRequestLink} className="w-full sm:w-fit">
          <FormattedMessage
            defaultMessage="Email me a link to set a password"
            id="Auth / Change password / Request set link button"
          />
        </Button>
      </div>
    );
  }

  const onSubmit = (event?: BaseSyntheticEvent) => {
    if (canUseGrant) {
      event?.preventDefault();
      setPendingReauth(true);
      return;
    }
    return handleChangePassword()(event);
  };

  return (
    <div className="w-full">
      <form noValidate onSubmit={onSubmit} className="flex w-full flex-col gap-6">
        {hasUsablePassword && (
          <div className="w-full">
            <Input
              {...register('oldPassword', {
                required: {
                  value: true,
                  message: intl.formatMessage({
                    defaultMessage: 'Old password is required',
                    id: 'Auth / Change password / Old password required',
                  }),
                },
              })}
              type="password"
              label={intl.formatMessage({
                defaultMessage: 'Old password',
                id: 'Auth / Change password / Old password placeholder',
              })}
              error={errors.oldPassword?.message}
            />
          </div>
        )}

        {hasUsablePassword && otpEnabled && (
          <div className="w-full">
            <OtpInput
              value={watch('otpToken') || ''}
              onValueChange={(value) => setValue('otpToken', value)}
              disabled={loading}
              label={intl.formatMessage({
                defaultMessage: 'Authentication code',
                id: 'Auth / Change password / OTP label',
              })}
            />
            {errors.otpToken?.message && (
              <div className="mt-1 text-sm text-destructive dark:text-red-400">
                <Small>{errors.otpToken.message}</Small>
              </div>
            )}
          </div>
        )}

        <div className="flex w-full flex-col gap-6">
          <div className="w-full">
            <Input
              {...register('newPassword', {
                required: {
                  value: true,
                  message: intl.formatMessage({
                    defaultMessage: 'New password is required',
                    id: 'Auth / Change password / Password required',
                  }),
                },
                validate: {
                  minLength: (value) =>
                    value.length >= 8 ||
                    intl.formatMessage({
                      defaultMessage: 'Password must be at least 8 characters long',
                      id: 'Auth / Change password / Password too short',
                    }),
                  notCommon: (value) => {
                    const validation = validatePassword(value);
                    return (
                      validation.notCommon ||
                      intl.formatMessage({
                        defaultMessage: 'This password is too common. Please choose a more unique password.',
                        id: 'Auth / Change password / Password too common frontend',
                      })
                    );
                  },
                  notNumericOnly: (value) => {
                    const validation = validatePassword(value);
                    return (
                      validation.notNumericOnly ||
                      intl.formatMessage({
                        defaultMessage: "Password can't be entirely numeric.",
                        id: 'Auth / Change password / Password numeric only',
                      })
                    );
                  },
                },
              })}
              type="password"
              label={intl.formatMessage({
                defaultMessage: 'New password',
                id: 'Auth / Change password / New password label',
              })}
              placeholder={intl.formatMessage({
                defaultMessage: 'Create a strong password',
                id: 'Auth / Change password / New password placeholder',
              })}
              error={errors.newPassword?.message}
            />
            <PasswordStrengthIndicator password={newPassword} className="mt-2" />
            <PasswordRequirements password={newPassword} className="mt-3" />
          </div>

          <div className="w-full">
            <Input
              {...register('confirmNewPassword', {
                validate: {
                  required: (value) =>
                    value?.length > 0 ||
                    intl.formatMessage({
                      defaultMessage: 'Confirm password is required',
                      id: 'Auth / Change password / Confirm password required',
                    }),
                  mustMatch: (value) =>
                    getValues().newPassword === value ||
                    intl.formatMessage({
                      defaultMessage: 'Passwords must match',
                      id: 'Auth / Change password / Password must match',
                    }),
                },
              })}
              type="password"
              label={intl.formatMessage({
                defaultMessage: 'Confirm new password',
                id: 'Auth / Change password / Confirm new password label',
              })}
              placeholder={intl.formatMessage({
                defaultMessage: 'Re-enter your new password',
                id: 'Auth / Change password / Confirm new password placeholder',
              })}
              error={errors.confirmNewPassword?.message}
            />
          </div>
        </div>

        {hasGenericErrorOnly && (
          <div className="text-sm text-destructive dark:text-red-400">
            <Small>{genericError}</Small>
          </div>
        )}

        <div>
          <Button disabled={loading} type="submit" className="w-full sm:w-fit">
            {hasUsablePassword ? (
              <FormattedMessage defaultMessage="Change password" id="Auth / Change password / Submit button" />
            ) : (
              <FormattedMessage defaultMessage="Set password" id="Auth / Change password / Set submit button" />
            )}
          </Button>
        </div>
      </form>

      <OtpReauthDialog
        open={pendingReauth}
        action="password_set"
        onClose={() => setPendingReauth(false)}
        onAuthorized={(authorization) => {
          setPendingReauth(false);
          handleChangePassword(authorization)();
        }}
      />
    </div>
  );
};
