import { useMutation } from '@apollo/client/react';
import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast';
import { useIntl } from 'react-intl';

import { TenantInvitationForm, type TenantInvitationFormFields } from '../../../../components/tenantInvitationForm';
import { tenantMembersListQuery } from '../../../../components/tenantMembersList/tenantMembersList.graphql';
import { useCurrentTenant } from '../../../../providers';
import { createTenantInvitation } from './invitationForm.graphql';

export const InvitationForm = () => {
  const { toast } = useToast();
  const intl = useIntl();
  const currentTenant = useCurrentTenant();

  const successMessage = intl.formatMessage({
    id: 'Tenant Members / Invitation form / Success message',
    defaultMessage: 'User invited successfully!',
  });
  const fallbackErrorMessage = intl.formatMessage({
    id: 'Tenant Members / Invitation form / Error message',
    defaultMessage: 'Failed to invite user. Please try again.',
  });
  const userCannotBeInvitedMessage = intl.formatMessage({
    id: 'Tenant Members / Invitation form / User cannot be invited',
    defaultMessage: 'This user cannot be a member of this organization.',
  });

  // Backend validation messages are plain English server text, not translated -
  // this repo's i18n system only covers frontend-owned FormattedMessage strings.
  // Never show that raw text directly; map a known, stable error `code` to a
  // proper translated message instead, falling back to a generic one otherwise.
  const errorMessageForCode = (code?: string) => {
    switch (code) {
      case 'user_cannot_be_invited':
        return userCannotBeInvitedMessage;
      default:
        return fallbackErrorMessage;
    }
  };

  const [commitTenantInvitationMutation, { error, loading: loadingMutation }] = useMutation(createTenantInvitation, {
    refetchQueries: () => [
      {
        query: tenantMembersListQuery,
        variables: {
          id: currentTenant.data!.id,
        },
      },
    ],
    onCompleted: () => {
      trackEvent('tenantInvitation', 'invite', currentTenant.data?.id);
      toast({ description: successMessage, variant: 'success' });
    },
    onError: (mutationError) => {
      const graphQLErrors = extractGraphQLErrors(mutationError) ?? [];
      const validationError = graphQLErrors.find(({ message }) => message === 'GraphQlValidationError');
      const nonFieldErrors = validationError?.extensions?.['non_field_errors'] as
        | { message?: string; code?: string }[]
        | undefined;
      toast({ description: errorMessageForCode(nonFieldErrors?.[0]?.code), variant: 'destructive' });
    },
  });

  const onInvitationFormSubmit = async (formData: TenantInvitationFormFields) => {
    try {
      await commitTenantInvitationMutation({
        variables: {
          input: {
            email: formData.email,
            organizationRoleIds: formData.organizationRoleIds,
            tenantId: currentTenant.data!.id,
          },
        },
      });
    } catch {
      // Already surfaced to the user via onError (toast) and the inline form error
      // (error prop below) - swallow here so the rejection doesn't propagate further.
    }
  };

  return <TenantInvitationForm onSubmit={onInvitationFormSubmit} loading={loadingMutation} error={error} />;
};
