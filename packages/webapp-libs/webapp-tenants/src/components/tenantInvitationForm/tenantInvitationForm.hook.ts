import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useEffect } from 'react';

import { TenantInvitationFormFields } from './tenantInvitationForm.component';

export type UseTenantInvitationFormHookProps = {
  initialData?: TenantInvitationFormFields | null;
  onSubmit: (formData: TenantInvitationFormFields) => boolean | void | Promise<boolean | void>;
  error?: Error;
};

export const useTenantInvitationForm = ({ error, onSubmit, initialData }: UseTenantInvitationFormHookProps) => {
  const apiForm = useApiForm<TenantInvitationFormFields>({
    defaultValues: {
      email: initialData?.email ?? '',
      organizationRoleIds: initialData?.organizationRoleIds ?? [],
    },
  });

  const { handleSubmit, setApolloGraphQLResponseErrors, form: rhfForm } = apiForm;

  useEffect(() => {
    if (error && 'graphQLErrors' in error) {
      setApolloGraphQLResponseErrors((error as any).graphQLErrors);
    }
  }, [error, setApolloGraphQLResponseErrors]);

  const handleFormSubmit = handleSubmit(async (formData: TenantInvitationFormFields) => {
    const succeeded = await onSubmit({ ...formData, email: formData.email.trim() });
    if (succeeded !== false) {
      rhfForm.reset();
    }
  });

  return { ...apiForm, handleFormSubmit };
};
