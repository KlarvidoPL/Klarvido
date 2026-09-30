import { useLazyQuery } from '@apollo/client/react';

import { companyLookupByNipQuery } from './useCompanyLookup.graphql';

export type CompanyDetails = {
  companyName: string;
  regon: string;
  address: string;
  vatStatus: string;
};

/**
 * Looks up company details in the MF White List (via the backend) for a NIP.
 * Resolves to null when nothing was found or the lookup failed - callers just leave the fields for the user to fill.
 */
export const useCompanyLookup = () => {
  const [runQuery, { loading }] = useLazyQuery(companyLookupByNipQuery, { fetchPolicy: 'network-only' });

  const lookup = async (nip: string): Promise<CompanyDetails | null> => {
    try {
      const { data } = await runQuery({ variables: { nip } });
      const result = data?.companyLookupByNip;
      if (!result?.found) return null;
      return {
        companyName: result.companyName ?? '',
        regon: result.regon ?? '',
        address: result.address ?? '',
        vatStatus: result.vatStatus ?? '',
      };
    } catch {
      return null;
    }
  };

  return { lookup, loading };
};
