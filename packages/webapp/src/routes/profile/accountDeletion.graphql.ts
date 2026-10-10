import { gql } from '@sb/webapp-api-client/graphql';

export const accountDeletionEligibilityQuery = gql(/* GraphQL */ `
  query accountDeletionEligibilityQuery {
    accountDeletionBlockers {
      id
      name
    }
    myPasskeys {
      edges {
        node {
          id
          isActive
        }
      }
    }
  }
`);

export const deleteAccountMutation = gql(/* GraphQL */ `
  mutation deleteAccountMutation($input: DeleteAccountMutationInput!) {
    deleteAccount(input: $input) {
      ok
    }
  }
`);
