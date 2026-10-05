import { useMutation, useQuery } from '@apollo/client/react';
import { gql } from '@sb/webapp-api-client/graphql';
import { useEffect } from 'react';

const SSO_DOMAINS_QUERY = gql(`
  query TenantSecuritySSODomainsQuery($tenantId: ID!) {
    ssoDomains(tenantId: $tenantId) {
      id
      domain
      status
      verifiedAt
      lastCheckedAt
      consecutiveFailures
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

  // Apollo 4 no longer supports onCompleted on useMutation, so each mutation refetches once it resolves
  const [addDomainMutation, { loading: adding }] = useMutation(ADD_SSO_DOMAIN);
  const addDomain: typeof addDomainMutation = async (options) => {
    const result = await addDomainMutation(options);
    await refetch();
    return result;
  };

  const [verifyDomainMutation, { loading: verifying }] = useMutation(VERIFY_SSO_DOMAIN);
  const verifyDomain: typeof verifyDomainMutation = async (options) => {
    const result = await verifyDomainMutation(options);
    await refetch();
    return result;
  };

  const [deleteDomainMutation, { loading: deleting }] = useMutation(DELETE_SSO_DOMAIN);
  const deleteDomain: typeof deleteDomainMutation = async (options) => {
    const result = await deleteDomainMutation(options);
    await refetch();
    return result;
  };

  // Connection saves can claim new domains; the SSO card announces them with this event
  useEffect(() => {
    const handleConnectionsChanged = () => {
      void refetch();
    };
    window.addEventListener('sso-connections-changed', handleConnectionsChanged);
    return () => window.removeEventListener('sso-connections-changed', handleConnectionsChanged);
  }, [refetch]);

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
