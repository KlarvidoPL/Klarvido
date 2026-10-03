import { useMutation, useQuery } from '@apollo/client/react';
import { gql } from '@sb/webapp-api-client/graphql';

// Only status metadata is queried. The KSeF token is never returned by the API.
const KSEF_CREDENTIAL_QUERY = gql(`
  query TenantSecurityKsefCredentialQuery($tenantId: ID!) {
    ksefCredential(tenantId: $tenantId) {
      status
      tokenName
      tokenHint
      lastVerifiedAt
      lastErrorCode
      updatedAt
    }
  }
`);

const SET_KSEF_TOKEN = gql(`
  mutation TenantSecuritySetKsefToken($tenantId: ID!, $token: String!) {
    setKsefToken(tenantId: $tenantId, token: $token) {
      ok
      errorCode
      ksefCredential {
        status
        tokenName
        tokenHint
        lastVerifiedAt
        lastErrorCode
        updatedAt
      }
    }
  }
`);

const TEST_KSEF_TOKEN = gql(`
  mutation TenantSecurityTestKsefToken($tenantId: ID!) {
    testKsefToken(tenantId: $tenantId) {
      ok
      errorCode
      ksefCredential {
        status
        tokenName
        tokenHint
        lastVerifiedAt
        lastErrorCode
        updatedAt
      }
    }
  }
`);

const DELETE_KSEF_TOKEN = gql(`
  mutation TenantSecurityDeleteKsefToken($tenantId: ID!) {
    deleteKsefToken(tenantId: $tenantId) {
      ok
      errorCode
    }
  }
`);

export function useTenantKsef(tenantId: string | undefined, enabled: boolean) {
  const { data, loading, error, refetch } = useQuery(KSEF_CREDENTIAL_QUERY, {
    variables: { tenantId: tenantId ?? '' },
    skip: !tenantId || !enabled,
  });

  const [setToken] = useMutation(SET_KSEF_TOKEN);
  const [testToken, { loading: testing }] = useMutation(TEST_KSEF_TOKEN, {
    onCompleted: () => refetch(),
  });
  const [deleteToken, { loading: deleting }] = useMutation(DELETE_KSEF_TOKEN, {
    onCompleted: () => refetch(),
  });

  return {
    credential: data?.ksefCredential ?? null,
    loading,
    error,
    refetch,
    setToken,
    testToken,
    testing,
    deleteToken,
    deleting,
  };
}
