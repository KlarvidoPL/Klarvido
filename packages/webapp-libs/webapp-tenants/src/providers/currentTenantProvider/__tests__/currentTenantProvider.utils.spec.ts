import { TenantType } from '@sb/webapp-api-client/constants';

import { tenantFactory } from '../../../tests/factories/tenant';
import { getCurrentTenant } from '../currentTenantProvider.utils';

describe('currentTenantProvider.utils: getCurrentTenant', () => {
  it('should return the tenant matching the params id when the membership is accepted', () => {
    const tenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: true } });
    const result = getCurrentTenant('org-1', null, [tenant]);
    expect(result).toEqual(tenant);
  });

  it('should not resolve a tenant matching the params id when the invitation is unaccepted', () => {
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const pendingTenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: false } });
    const result = getCurrentTenant('org-1', null, [personalTenant, pendingTenant]);
    expect(result).toEqual(null);
  });

  it('should return the tenant with no real membership row when the viewer is a superuser (params match)', () => {
    // Superuser owner-equivalent bypass access: no real TenantMembership row exists,
    // so `membership` is null - this must still resolve as the current tenant instead
    // of falling through to the "nothing selected" state.
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const bypassTenant = tenantFactory({ id: 'org-1', membership: null });
    const result = getCurrentTenant('org-1', null, [personalTenant, bypassTenant], true);
    expect(result).toEqual(bypassTenant);
  });

  it('should not resolve a null-membership tenant matching the params id when the viewer is not a superuser', () => {
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const bypassTenant = tenantFactory({ id: 'org-1', membership: null });
    const result = getCurrentTenant('org-1', null, [personalTenant, bypassTenant], false);
    expect(result).toEqual(null);
  });

  it('should use the stored tenant id when it is a real organization tenant and no params id is given', () => {
    const tenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: true } });
    const result = getCurrentTenant('', 'org-1', [tenant]);
    expect(result).toEqual(tenant);
  });

  it('should not stick to a stored id pointing at a personal tenant', () => {
    // The old fallback behavior used to persist a personal tenant's id to storage -
    // a personal tenant id in storage must never silently become "the current tenant".
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const result = getCurrentTenant('', 'personal-1', [personalTenant]);
    expect(result).toEqual(null);
  });

  it('should auto-select the single real organization tenant when nothing matches in params or storage', () => {
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const orgTenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: true } });
    const pendingInviteTenant = tenantFactory({ id: 'org-2', membership: { invitationAccepted: false } });
    const result = getCurrentTenant('', null, [personalTenant, orgTenant, pendingInviteTenant]);
    expect(result).toEqual(orgTenant);
  });

  it('should select nothing when there are two or more real organization tenants and nothing is stored', () => {
    const orgOne = tenantFactory({ id: 'org-1', membership: { invitationAccepted: true } });
    const orgTwo = tenantFactory({ id: 'org-2', membership: { invitationAccepted: true } });
    const result = getCurrentTenant('', null, [orgOne, orgTwo]);
    expect(result).toEqual(null);
  });

  it('should select nothing for a superuser with only bypass-visible organizations (no real memberships)', () => {
    const bypassOne = tenantFactory({ id: 'org-1', membership: null });
    const bypassTwo = tenantFactory({ id: 'org-2', membership: null });
    const result = getCurrentTenant('', null, [bypassOne, bypassTwo], true);
    expect(result).toEqual(null);
  });

  it('should select nothing when there are no real organization tenants at all', () => {
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const result = getCurrentTenant('', null, [personalTenant]);
    expect(result).toEqual(null);
  });
});
