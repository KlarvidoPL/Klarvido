import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import { useApiForm } from '@sb/webapp-api-client/hooks';
import { useEffect } from 'react';

import { DEFAULT_COMPANY_COUNTRY } from '../../utils/companyCountries';
import { TenantFormFields, TenantFormProps } from './tenantForm.component';

type UseTenantFormProps = Pick<TenantFormProps, 'error' | 'onSubmit' | 'initialData'>;

export const useTenantForm = ({ error, onSubmit, initialData }: UseTenantFormProps) => {
  const form = useApiForm<TenantFormFields>({
    // Company fields are required: flag a field as soon as it's left empty, not only on submit
    mode: 'onTouched',
    defaultValues: {
      name: initialData?.name ?? '',
      country: initialData?.country || DEFAULT_COMPANY_COUNTRY,
      nip: initialData?.nip ?? '',
      companyName: initialData?.companyName ?? '',
      regon: initialData?.regon ?? '',
      address: initialData?.address ?? '',
      vatStatus: initialData?.vatStatus ?? '',
    },
  });

  const { handleSubmit, setApolloGraphQLResponseErrors } = form;

  useEffect(() => {
    const graphQLErrors = extractGraphQLErrors(error);
    if (graphQLErrors) {
      setApolloGraphQLResponseErrors(graphQLErrors);
    }
  }, [error, setApolloGraphQLResponseErrors]);

  const handleFormSubmit = handleSubmit((formData: TenantFormFields) => onSubmit(formData));

  return { ...form, handleFormSubmit };
};
