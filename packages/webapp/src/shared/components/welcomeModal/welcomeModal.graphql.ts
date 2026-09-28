import { gql } from '@sb/webapp-api-client/graphql';

export const welcomeModalMarkSeenMutation = gql(/* GraphQL */ `
  mutation welcomeModalMarkSeenMutation($input: MarkWelcomeModalSeenMutationInput!) {
    markWelcomeModalSeen(input: $input) {
      ok
    }
  }
`);
