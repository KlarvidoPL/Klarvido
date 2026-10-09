import { useMutation } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useCommonQuery } from '@sb/webapp-api-client/providers';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { useIntl } from 'react-intl';

import { authChangePasswordMutation } from './changePasswordForm.graphql';
import { ChangePasswordFormFields } from './changePasswordForm.types';

export const useChangePasswordForm = (hasUsablePassword: boolean, otpEnabled: boolean) => {
  const intl = useIntl();
  const { toast } = useToast();
  const { reload: reloadCommonQuery } = useCommonQuery();

  const form = useApiForm<ChangePasswordFormFields>({
    defaultValues: {
      oldPassword: '',
      newPassword: '',
      confirmNewPassword: '',
      otpToken: '',
    },
    errorMessages: {
      nonFieldErrors: {
        too_many_attempts: intl.formatMessage({
          defaultMessage: 'Too many attempts. Try again later.',
          id: 'Auth / Change password / Too many attempts',
        }),
        rate_limit_unavailable: intl.formatMessage({
          defaultMessage: 'Sign-in is temporarily unavailable. Please try again shortly.',
          id: 'Auth / Change password / Rate limit unavailable',
        }),
      },
      oldPassword: {
        wrong_password: intl.formatMessage({
          defaultMessage: 'The current password is incorrect.',
          id: 'Auth / Change password / wrong old password',
        }),
        too_many_attempts: intl.formatMessage({
          defaultMessage: 'Too many attempts. Try again later.',
          id: 'Auth / Change password / Too many attempts',
        }),
      },
      otpToken: {
        required: intl.formatMessage({
          defaultMessage: 'The authentication code is required',
          id: 'Auth / Validate OTP / Auth code required',
        }),
        otp_verification_failure: intl.formatMessage({
          defaultMessage: 'The verification code is invalid.',
          id: 'Auth / OTP / Invalid code',
        }),
        otp_attempt_limit_exceeded: intl.formatMessage({
          defaultMessage: 'Too many incorrect codes. Try again in 15 minutes.',
          id: 'Auth / OTP / Attempt limit',
        }),
      },
      newPassword: {
        password_too_common: intl.formatMessage({
          defaultMessage: 'This password is too common. Please choose a more unique password.',
          id: 'Auth / Change password / password too common',
        }),
        password_entirely_numeric: intl.formatMessage({
          defaultMessage: "The password can't be entirely numeric.",
          id: 'Auth / Change password / password entirely numeric',
        }),
        password_too_short: intl.formatMessage({
          defaultMessage: 'Password must be at least 8 characters long.',
          id: 'Auth / Change password / password too short backend',
        }),
        password_too_similar: intl.formatMessage({
          defaultMessage: 'The password is too similar to your personal information.',
          id: 'Auth / Change password / password too similar',
        }),
      },
    },
  });

  const {
    handleSubmit,
    setApolloGraphQLResponseErrors,
    form: { reset },
  } = form;

  const [commitChangePasswordMutation, { loading }] = useMutation(authChangePasswordMutation, {
    onCompleted: async () => {
      trackEvent('profile', 'password-update');

      // A successful call without oldPassword means this was a first-time "set
      // password" for an OAuth-only account - refetch so currentUser.hasUsablePassword
      // (and thus the Old Password field) updates without a manual page refresh.
      if (!hasUsablePassword) {
        try {
          await reloadCommonQuery();
        } catch (error) {
          console.error('Failed to refresh current user after setting password:', error);
        }
      }

      reset();

      toast({
        description: hasUsablePassword
          ? intl.formatMessage({
              defaultMessage: 'Password successfully changed.',
              id: 'Auth / Change password / Success message',
            })
          : intl.formatMessage({
              defaultMessage: 'Password successfully set.',
              id: 'Auth / Change password / Set success message',
            }),
        variant: 'success',
      });
    },
    onError: (error) => {
      const graphQLErrors = extractGraphQLErrors(error);
      if (graphQLErrors) {
        setApolloGraphQLResponseErrors(graphQLErrors);
      }
    },
  });

  // Takes the fresh-auth grant token explicitly (rather than from a hook-level prop/state) so a
  // caller that just obtained one through OtpReauthDialog - used only for the first password on
  // a passwordless account with a passkey or 2FA, E04 - can re-invoke this immediately with it,
  // without waiting on a state update/re-render to see the new value.
  const handleChangePassword = (authorization?: string) =>
    handleSubmit(async ({ newPassword, oldPassword, otpToken }: ChangePasswordFormFields) => {
      try {
        await commitChangePasswordMutation({
          variables: {
            input: {
              newPassword,
              ...(hasUsablePassword ? { oldPassword } : {}),
              ...(hasUsablePassword && otpEnabled ? { otpToken } : {}),
            },
          },
          context: authorization ? { headers: { 'X-Passkey-Authorization': authorization } } : undefined,
        });
      } catch (error) {
        // Error is handled by onError callback
        // This catch prevents unhandled promise rejection
      }
    });
  return { ...form, loading, handleChangePassword };
};
