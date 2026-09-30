import { gql } from '@sb/webapp-api-client/graphql';

export const companyLookupByNipQuery = gql(/* GraphQL */ `
  query companyLookupByNipQuery($nip: String!) {
    companyLookupByNip(nip: $nip) {
      found
      nip
      companyName
      regon
      address
      vatStatus
    }
  }
`);
