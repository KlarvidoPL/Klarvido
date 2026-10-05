import { useQuery, useMutation } from '@apollo/client/react';
import { gql } from '@sb/webapp-api-client/graphql';

// Passkeys are personal: each user lists and deletes only their own, from their Profile.
const MY_PASSKEYS_QUERY = gql(`
  query MyPasskeysQuery {
    myPasskeys(first: 50) {
      edges {
        node {
          id
          name
          authenticatorType
          createdAt
          lastUsedAt
          useCount
        }
      }
    }
  }
`);

const DELETE_PASSKEY = gql(`
  mutation TenantSecurityDeletePasskey($input: DeletePasskeyMutationInput!) {
    deletePasskey(input: $input) {
      deletedIds
    }
  }
`);

export function useTenantPasskeys() {
  const myQuery = useQuery(MY_PASSKEYS_QUERY);

  const [deletePasskey] = useMutation(DELETE_PASSKEY, {
    onCompleted: () => myQuery.refetch(),
  });

  type PasskeyNode = { id: string; name: string; authenticatorType: string; createdAt: unknown; lastUsedAt?: unknown; useCount: number };
  const passkeys: PasskeyNode[] = (myQuery.data?.myPasskeys?.edges ?? [])
    .filter((edge): edge is { node: PasskeyNode } => !!edge?.node)
    .map((edge) => edge.node);

  return {
    passkeys,
    loading: myQuery.loading,
    refetch: myQuery.refetch,
    deletePasskey,
  };
}
