import { gql } from '@sb/webapp-api-client/graphql';

export const setDefaultOrganizationMutation = gql(/* GraphQL */ `
  mutation setDefaultOrganizationMutation($organizationId: ID) {
    setDefaultOrganization(input: { organizationId: $organizationId }) {
      defaultOrganizationId
    }
  }
`);
