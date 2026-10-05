import { useMutation, useQuery } from '@apollo/client/react';
import { gql } from '@sb/webapp-api-client/graphql';

const SSO_DOMAINS_QUERY = gql(`
  query TenantSecuritySSODomainsQuery($tenantId: ID!) {
    ssoDomains(tenantId: $tenantId) {
      id
      domain
      status
      verifiedAt
      verificationRecordName
      verificationRecordValue
    }
  }
`);

const ADD_SSO_DOMAIN = gql(`
  mutation TenantSecurityAddSSODomainMutation($tenantId: ID!, $domain: String!) {
    addSsoDomain(tenantId: $tenantId, domain: $domain) {
      ssoDomain {
        id
        domain
        status
        verifiedAt
        verificationRecordName
        verificationRecordValue
      }
    }
  }
`);

const VERIFY_SSO_DOMAIN = gql(`
  mutation TenantSecurityVerifySSODomainMutation($id: ID!, $tenantId: ID!) {
    verifySsoDomain(id: $id, tenantId: $tenantId) {
      ssoDomain {
        id
        domain
        status
        verifiedAt
        verificationRecordName
        verificationRecordValue
      }
    }
  }
`);

const DELETE_SSO_DOMAIN = gql(`
  mutation TenantSecurityDeleteSSODomainMutation($id: ID!, $tenantId: ID!) {
    deleteSsoDomain(id: $id, tenantId: $tenantId) {
      ok
    }
  }
`);

export function useTenantSSODomains(tenantId: string | undefined) {
  const { data, loading, error, refetch } = useQuery(SSO_DOMAINS_QUERY, {
    variables: { tenantId: tenantId ?? '' },
    skip: !tenantId,
  });

  const [addDomain, { loading: adding }] = useMutation(ADD_SSO_DOMAIN, {
    onCompleted: () => refetch(),
  });

  const [verifyDomain, { loading: verifying }] = useMutation(VERIFY_SSO_DOMAIN, {
    onCompleted: () => refetch(),
  });

  const [deleteDomain, { loading: deleting }] = useMutation(DELETE_SSO_DOMAIN, {
    onCompleted: () => refetch(),
  });

  const domains = (data?.ssoDomains ?? []).flatMap((domain) => (domain ? [domain] : []));

  return {
    domains,
    loading,
    error,
    refetch,
    addDomain,
    adding,
    verifyDomain,
    verifying,
    deleteDomain,
    deleting,
  };
}
