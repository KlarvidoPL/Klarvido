import { useIntl } from 'react-intl';

import { CompanyDetails } from './useCompanyLookup.hook';

/** Formats company field keys as a translated, human-readable list, e.g. "REGON and address". */
export const useFormatCompanyFields = () => {
  const intl = useIntl();

  const fieldNames: Record<keyof CompanyDetails, string> = {
    companyName: intl.formatMessage({ defaultMessage: 'company name', id: 'Tenant form / Field name / Company name' }),
    regon: intl.formatMessage({ defaultMessage: 'REGON', id: 'Tenant form / Field name / REGON' }),
    address: intl.formatMessage({ defaultMessage: 'address', id: 'Tenant form / Field name / Address' }),
    vatStatus: intl.formatMessage({ defaultMessage: 'VAT status', id: 'Tenant form / Field name / VAT status' }),
  };

  return (fields: Array<keyof CompanyDetails>) =>
    intl.formatList(
      fields.map((field) => fieldNames[field]),
      { type: 'conjunction' }
    );
};
