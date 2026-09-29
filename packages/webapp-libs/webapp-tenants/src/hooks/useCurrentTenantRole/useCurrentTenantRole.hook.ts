import { getFragmentData, TenantUserRole } from '@sb/webapp-api-client/graphql';
import { commonQueryCurrentUserFragment, useCommonQuery } from '@sb/webapp-api-client/providers';

import { useCurrentTenantMembership } from '../../hooks';

/**
 * Hook that retrieves the user's role of the current tenant.
 *
 * This hook uses the `useCurrentTenant` hook to get the current tenant's data, and then extracts the role from the
 * tenant's membership data. A superuser with no real membership in the current tenant (owner-equivalent access via
 * the backend permission bypass) falls back to `OWNER` instead of `null`.
 *
 * @returns {string | null} The role of the current tenant if available, or `null` otherwise.
 *
 */
export const useCurrentTenantRole = () => {
  const { currentMembership } = useCurrentTenantMembership();
  const { data } = useCommonQuery();
  const currentUser = getFragmentData(commonQueryCurrentUserFragment, data?.currentUser);

  if (!currentMembership?.invitationAccepted) {
    return currentUser?.isSuperuser ? TenantUserRole.OWNER : null;
  }
  return currentMembership?.role ?? null;
};
