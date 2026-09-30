import { gql } from '@sb/webapp-api-client/graphql';

export const addTenantMutation = gql(/* GraphQL */ `
  mutation addTenantMutation($input: CreateTenantMutationInput!) {
    createTenant(input: $input) {
      tenantEdge {
        node {
          id
          name
        }
      }
    }
  }
`);
