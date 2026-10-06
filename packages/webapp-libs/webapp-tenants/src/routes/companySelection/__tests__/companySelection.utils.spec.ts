import { TenantType } from '@sb/webapp-api-client/constants';

import { tenantFactory } from '../../../tests/factories/tenant';
import { companyGroups, homeOrganization, matchesCompany } from '../companySelection.utils';

const one = tenantFactory({ id: 'one', name: 'Firma Alpha', nip: '123-456-78-90' });
const two = tenantFactory({ id: 'two', name: 'Firma Beta' });

it('separates invitations and hides personal accounts, preserving superuser bypass', () => {
  const invitation = tenantFactory({ id: 'invite', membership: { invitationAccepted: false } });
  const personal = tenantFactory({ type: TenantType.PERSONAL });
  const bypass = tenantFactory({ id: 'bypass', membership: null });
  expect(companyGroups([one, invitation, personal, bypass, null])).toEqual({
    organizations: [one],
    invitations: [invitation],
  });
  expect(companyGroups([one, bypass], true).organizations).toEqual([one, bypass]);
});

it('chooses only an accessible explicit default or the single available company', () => {
  expect(homeOrganization([], 'one')).toBeNull();
  expect(homeOrganization([one])).toBe(one);
  expect(homeOrganization([one, two])).toBeNull();
  expect(homeOrganization([one, two], 'two')).toBe(two);
  expect(homeOrganization([one, two], 'revoked')).toBeNull();
});

it('searches names without case sensitivity and normalizes NIP formatting', () => {
  expect(matchesCompany(one, ' ALPHA ')).toBe(true);
  expect(matchesCompany(one, '123 456 78')).toBe(true);
  expect(matchesCompany(one, 'beta')).toBe(false);
  expect(matchesCompany(one, 'xyz123')).toBe(false);
});
