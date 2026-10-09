import { gql } from '@sb/webapp-api-client/graphql';

export const authChangePasswordMutation = gql(/* GraphQL */ `
  mutation authChangePasswordMutation($input: ChangePasswordMutationInput!) {
    changePassword(input: $input) {
      authenticated
    }
  }
`);

export const requestPasswordSetLinkMutation = gql(/* GraphQL */ `
  mutation requestPasswordSetLinkMutation($input: RequestPasswordSetLinkMutationInput!) {
    requestPasswordSetLink(input: $input) {
      ok
    }
  }
`);
