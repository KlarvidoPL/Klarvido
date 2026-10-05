import { TenantSecuritySsoDomainsQueryDocument, TenantUserRole } from '@sb/webapp-api-client';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen } from '@testing-library/react';

import { RoutesConfig } from '../../../../../config/routes';
import { membershipFactory, tenantFactory } from '../../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../../tests/utils/rendering';
import { DomainVerificationCard } from '../domainVerificationCard';

const createMockDomain = (overrides = {}) => ({
  id: 'domain-1',
  domain: 'client.pl',
  status: 'PENDING',
  verifiedAt: null,
  verificationRecordName: 'client.pl',
  verificationRecordValue: 'klarvido-domain-verification=token-123',
  ...overrides,
});

const createDomainsMock = (domains: ReturnType<typeof createMockDomain>[]) =>
  composeMockedQueryResult(TenantSecuritySsoDomainsQueryDocument, {
    variables: { tenantId: 'tenant-1' },
    data: { ssoDomains: domains },
  });

describe('DomainVerificationCard: Component', () => {
  const renderComponent = (canManageSSO = true, domains: ReturnType<typeof createMockDomain>[] = []) => {
    const tenant = tenantFactory({
      id: 'tenant-1',
      membership: membershipFactory({
        role: canManageSSO ? TenantUserRole.OWNER : TenantUserRole.MEMBER,
      }),
    });
    const user = currentUserFactory({ tenants: [tenant] });

    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.security, { tenantId: 'tenant-1' });

    return render(<DomainVerificationCard canManageSSO={canManageSSO} />, {
      apolloMocks: [fillCommonQueryWithUser(user), createDomainsMock(domains)],
      routerProps,
    });
  };

  it('shows the empty state when no domain is claimed', async () => {
    renderComponent(true);

    expect(await screen.findByText(/No domains claimed yet/i)).toBeInTheDocument();
  });

  it('shows the DNS record and a Verify action for a pending domain', async () => {
    renderComponent(true, [createMockDomain()]);

    // The domain name appears in the header and in the DNS record name
    expect((await screen.findAllByText('client.pl')).length).toBeGreaterThan(0);
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('klarvido-domain-verification=token-123')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Verify/i })).toBeInTheDocument();
  });

  it('shows a verified domain without a Verify action or DNS record', async () => {
    renderComponent(true, [createMockDomain({ status: 'VERIFIED', verifiedAt: '2026-10-01T10:00:00Z' })]);

    expect(await screen.findByText('client.pl')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Verify$/i })).not.toBeInTheDocument();
    expect(screen.queryByText('klarvido-domain-verification=token-123')).not.toBeInTheDocument();
  });

  it('shows the add form to users who can manage SSO', async () => {
    renderComponent(true);

    await screen.findByText(/No domains claimed yet/i);
    expect(screen.getByRole('button', { name: /Add domain/i })).toBeInTheDocument();
  });

  it('hides the add form and actions from users who cannot manage SSO', async () => {
    renderComponent(false, [createMockDomain()]);

    expect((await screen.findAllByText('client.pl')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /Add domain/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Verify/i })).not.toBeInTheDocument();
  });
});
