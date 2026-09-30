import { gql } from '@sb/webapp-api-client/graphql';

export const companyLookupByNipQuery = gql(/* GraphQL */ `
  query companyLookupByNipQuery($nip: String!, $country: String!) {
    companyLookupByNip(nip: $nip, country: $country) {
      found
      country
      nip
      companyName
      regon
      address
      vatStatus
    }
  }
`);
