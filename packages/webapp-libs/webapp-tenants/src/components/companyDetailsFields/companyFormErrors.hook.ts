import { useMemo } from 'react';
import { useIntl } from 'react-intl';

/** Map API validation codes to the same localized messages as the company inputs. */
export const useCompanyFormErrorMessages = () => {
  const intl = useIntl();
  return useMemo(() => {
    const fallback = intl.formatMessage({
      defaultMessage: 'Check this value and try again.',
      id: 'Tenant form / Invalid value',
    });
    const required = (message: string) => ({ required: message, blank: message, default: fallback });
    const immutable = intl.formatMessage({
      defaultMessage: "This value can't be changed once saved.",
      id: 'Tenant form / Immutable value',
    });
    return {
      name: required(
        intl.formatMessage({ defaultMessage: 'Display name is required', id: 'Tenant form / Display name required' })
      ),
      country: {
        ...required(
          intl.formatMessage({ defaultMessage: 'Country is required', id: 'Tenant form / Country required' })
        ),
        immutable,
      },
      nip: {
        ...required(intl.formatMessage({ defaultMessage: 'NIP is required', id: 'Tenant form / NIP required' })),
        invalid_nip: intl.formatMessage({ defaultMessage: 'Invalid NIP number', id: 'Tenant form / NIP invalid' }),
        immutable,
      },
      regon: {
        ...required(intl.formatMessage({ defaultMessage: 'REGON is required', id: 'Tenant form / REGON required' })),
        invalid_regon: intl.formatMessage({
          defaultMessage: 'Invalid REGON number',
          id: 'Tenant form / REGON invalid',
        }),
        immutable,
      },
      companyName: required(
        intl.formatMessage({ defaultMessage: 'Company name is required', id: 'Tenant form / Company name required' })
      ),
      address: required(
        intl.formatMessage({ defaultMessage: 'Address is required', id: 'Tenant form / Address required' })
      ),
      vatStatus: required(
        intl.formatMessage({ defaultMessage: 'VAT status is required', id: 'Tenant form / VAT status required' })
      ),
      nonFieldErrors: {
        default: intl.formatMessage({
          defaultMessage: 'Could not save this step. Please try again.',
          id: 'Onboarding / Save failed',
        }),
      },
    };
  }, [intl]);
};
