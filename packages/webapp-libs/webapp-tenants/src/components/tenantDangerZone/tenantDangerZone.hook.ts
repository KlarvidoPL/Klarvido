import { useMutation } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useCommonQuery } from '@sb/webapp-api-client/providers';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast';
import { useIntl } from 'react-intl';
import { useNavigate } from 'react-router';

import { useCurrentTenant } from '../../providers';
import { deleteTenantMutation } from './tenantDangerZone.graphql';

export const useTenantDelete = () => {
  const { data: currentTenant } = useCurrentTenant();
  const { reload: reloadCommonQuery } = useCommonQuery();
  const navigate = useNavigate();
  const { toast } = useToast();
  const intl = useIntl();
  const form = useApiForm<{ otpToken: string }>({
    defaultValues: { otpToken: '' },
    errorMessages: {
      otpToken: {
        required: intl.formatMessage({
          id: 'Auth / Validate OTP / Auth code required',
          defaultMessage: 'The authentication code is required',
        }),
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

  const generateLocalePath = useGenerateLocalePath();

  const successDeleteMessage = intl.formatMessage({
    id: 'Tenant form / DeleteTenant / Success message',
    defaultMessage: 'Organization deleted successfully!',
  });

  const failDeleteMessage = intl.formatMessage({
    id: 'Membership Entry / DeleteTenant / Fail message',
    defaultMessage: 'Unable to delete the organization.',
  });

  const [commitRemoveMutation, { loading }] = useMutation(deleteTenantMutation, {
    onCompleted: (data) => {
      const id = data.deleteTenant?.deletedIds?.[0]?.toString();
      reloadCommonQuery();
      trackEvent('tenant', 'delete', id);
      toast({ description: successDeleteMessage, variant: 'success' });
      navigate(generateLocalePath(RoutesConfig.home), { replace: true });
    },
    onError: (error) => {
      const errors = extractGraphQLErrors(error);
      if (errors) form.setApolloGraphQLResponseErrors(errors);
      toast({ description: failDeleteMessage, variant: 'destructive' });
    },
  });

  const deleteTenant = async (otpToken?: string) => {
    if (!currentTenant) return false;
    form.form.clearErrors();

    try {
      const result = await commitRemoveMutation({
        variables: {
          input: {
            id: currentTenant.id,
            // The backend resolves (and permission-checks) the organization from tenantId only, never from id
            tenantId: currentTenant.id,
            ...(otpToken !== undefined ? { otpToken } : {}),
          },
        },
      });
      return !!result.data?.deleteTenant?.deletedIds?.length;
    } catch {
      return false;
    }
  };

  return { deleteTenant, loading, form: form.form };
};
