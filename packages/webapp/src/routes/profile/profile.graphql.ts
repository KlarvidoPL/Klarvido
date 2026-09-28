import { gql } from '@sb/webapp-api-client/graphql';

export const profileResendConfirmationEmailMutation = gql(/* GraphQL */ `
  mutation profileResendConfirmationEmailMutation($input: ResendConfirmationEmailMutationInput!) {
    resendConfirmationEmail(input: $input) {
      ok
    }
  }
`);
