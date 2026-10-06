import { CommonQueryTenantItemFragmentFragment, getFragmentData } from '@sb/webapp-api-client';
import { TenantType } from '@sb/webapp-api-client/constants';
import { commonQueryMembershipFragment } from '@sb/webapp-api-client/providers';

type Company = CommonQueryTenantItemFragmentFragment;
export const companyGroups = (tenants: (Company | null | undefined)[], isSuperuser = false) => {
  const organizations: Company[] = [];
  const invitations: Company[] = [];
  for (const tenant of tenants) {
    if (!tenant || tenant.type !== TenantType.ORGANIZATION) continue;
    const membership = getFragmentData(commonQueryMembershipFragment, tenant.membership);
    if (membership?.invitationAccepted || (!membership && isSuperuser)) organizations.push(tenant);
    else if (membership?.invitationToken) invitations.push(tenant);
  }
  return { organizations, invitations };
};

export const homeOrganization = (organizations: Company[], defaultId?: string | null) =>
  organizations.find((organization) => organization.id === defaultId) ||
  (organizations.length === 1 ? organizations[0] : null);

export const matchesCompany = (company: Company, search: string) => {
  const query = search.trim().toLocaleLowerCase();
  const digits = query.replace(/\D/g, '');
  return (
    !query ||
    (company.name || '').toLocaleLowerCase().includes(query) ||
    (company.companyName || '').toLocaleLowerCase().includes(query) ||
    (!!digits && !/[a-ząćęłńóśźż]/i.test(query) && (company.nip || '').replace(/\D/g, '').includes(digits))
  );
};
