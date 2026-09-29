import { TenantType } from '@sb/webapp-api-client/constants';

import { tenantFactory } from '../../../tests/factories/tenant';
import { getCurrentTenant } from '../currentTenantProvider.utils';

describe('currentTenantProvider.utils: getCurrentTenant', () => {
  it('should return the tenant matching the params id when the membership is accepted', () => {
    const tenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: true } });
    const result = getCurrentTenant('org-1', null, [tenant]);
    expect(result).toEqual(tenant);
  });

  it('should fall back to the personal tenant when the matching tenant has an unaccepted invitation', () => {
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const pendingTenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: false } });
    const result = getCurrentTenant('org-1', null, [personalTenant, pendingTenant]);
    expect(result).toEqual(personalTenant);
  });

  it('should return the tenant with no real membership row when the viewer is a superuser', () => {
    // Superuser owner-equivalent bypass access: no real TenantMembership row exists,
    // so `membership` is null - this must still resolve as the current tenant instead
    // of silently falling back to the viewer's own personal tenant.
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const bypassTenant = tenantFactory({ id: 'org-1', membership: null });
    const result = getCurrentTenant('org-1', null, [personalTenant, bypassTenant], true);
    expect(result).toEqual(bypassTenant);
  });

  it('should fall back to the personal tenant for a null-membership tenant when the viewer is not a superuser', () => {
    const personalTenant = tenantFactory({ id: 'personal-1', type: TenantType.PERSONAL });
    const bypassTenant = tenantFactory({ id: 'org-1', membership: null });
    const result = getCurrentTenant('org-1', null, [personalTenant, bypassTenant], false);
    expect(result).toEqual(personalTenant);
  });

  it('should use the stored tenant id when no params id is given', () => {
    const tenant = tenantFactory({ id: 'org-1', membership: { invitationAccepted: true } });
    const result = getCurrentTenant('', 'org-1', [tenant]);
    expect(result).toEqual(tenant);
  });

  it('should fall back to the first tenant when nothing matches and there is no personal tenant', () => {
    const tenant = tenantFactory({ id: 'org-1', type: TenantType.ORGANIZATION, membership: { invitationAccepted: true } });
    const result = getCurrentTenant('nonexistent', null, [tenant]);
    expect(result).toEqual(tenant);
  });
});
