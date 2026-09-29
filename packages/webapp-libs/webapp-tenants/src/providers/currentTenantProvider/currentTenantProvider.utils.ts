import { CommonQueryTenantItemFragmentFragment, getFragmentData } from '@sb/webapp-api-client';
import { TenantType } from '@sb/webapp-api-client/constants';
import { commonQueryMembershipFragment } from '@sb/webapp-api-client/providers';

export const parseStoredState = (storedState: string, userId = '') => {
  try {
    const parsedStoredState = JSON.parse(storedState);

    return {
      parsedStoredState,
      storedTenantId: parsedStoredState?.[userId] ?? null,
    };
  } catch {
    return {
      parsedStoredState: {},
      storedTenantId: null,
    };
  }
};

const matchTenantById = (
  id: string,
  tenants: (CommonQueryTenantItemFragmentFragment | null | undefined)[],
  isSuperuser: boolean
) =>
  tenants.find((t) => {
    if (t?.id !== id) return false;
    const membership = getFragmentData(commonQueryMembershipFragment, t.membership);
    // A superuser can have no real membership row for a tenant they can still fully
    // access via the owner-equivalent bypass - that's not a pending invitation, so it
    // must still resolve as the current tenant instead of falling through below.
    if (!membership) return isSuperuser;
    return !!membership.invitationAccepted;
  });

export const getCurrentTenant = (
  paramsTenantId = '',
  storedTenantId: string | null,
  tenants: (CommonQueryTenantItemFragmentFragment | null | undefined)[],
  isSuperuser = false
) => {
  // 1. Explicit URL selection always wins - this can still resolve to a personal
  //    tenant deliberately (e.g. a bookmarked settings URL); only default
  //    resolution below must never land there.
  if (paramsTenantId) {
    const tenant = matchTenantById(paramsTenantId, tenants, isSuperuser);
    if (tenant) return tenant;
  }

  // 2. Remembered selection - only "sticks" for a real organization tenant (or a
  //    superuser bypass tenant). A personal tenant id must never silently become
  //    "the current tenant" just because it happens to be in storage.
  if (storedTenantId) {
    const tenant = matchTenantById(storedTenantId, tenants, isSuperuser);
    if (tenant && tenant.type === TenantType.ORGANIZATION) return tenant;
  }

  // 3. Nothing selected: auto-select only if there is EXACTLY one real
  //    (accepted-membership) organization tenant. Pending invitations and
  //    superuser bypass-visible tenants (membership === null) never count.
  const realOrganizationTenants = tenants.filter((t) => {
    if (t?.type !== TenantType.ORGANIZATION) return false;
    const membership = getFragmentData(commonQueryMembershipFragment, t.membership);
    return !!membership?.invitationAccepted;
  });

  return realOrganizationTenants.length === 1 ? realOrganizationTenants[0] : null;
};
