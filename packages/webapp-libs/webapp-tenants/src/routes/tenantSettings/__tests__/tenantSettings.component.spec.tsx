import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { screen } from '@testing-library/react';

import { membershipFactory, tenantFactory } from '../../../tests/factories/tenant';
import { createPermissionsMock } from '../../../tests/factories/tenant';
import {
  CurrentTenantRouteWrapper,
  createMockRouterProps,
  render,
} from '../../../tests/utils/rendering';
import { RoutesConfig } from '../../../config/routes';
import { TenantSettings } from '../tenantSettings.component';

jest.mock('@sb/webapp-finances/config/routes', () => ({
  RoutesConfig: {
    subscriptions: { index: 'subscriptions' },
  },
}));

describe('TenantSettings: Component', () => {
  const tenant = tenantFactory({
    id: 'tenant-1',
    membership: membershipFactory({ role: 'OWNER' }),
  });
  const user = currentUserFactory({ tenants: [tenant] });

  const Component = () => (
    <CurrentTenantRouteWrapper>
      <TenantSettings />
    </CurrentTenantRouteWrapper>
  );

  it('should render organization settings header', async () => {
    const apolloMocks = [
      fillCommonQueryWithUser(user),
      createPermissionsMock(tenant.id, ['org.settings.view', 'members.view']),
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, {
      tenantId: tenant.id,
    });

    render(<Component />, { apolloMocks, routerProps });

    expect(await screen.findByRole('heading', { name: /organization settings/i })).toBeInTheDocument();
    expect(screen.getByText(/manage your organization/i)).toBeInTheDocument();
  });

  describe('Security tab for KSeF-only roles', () => {
    const renderWithPermissions = (country: string, permissions: string[]) => {
      const polishTenant = tenantFactory({
        id: 'tenant-1',
        country,
        membership: membershipFactory({ role: 'OWNER' }),
      });
      const polishUser = currentUserFactory({ tenants: [polishTenant] });
      const apolloMocks = [fillCommonQueryWithUser(polishUser), createPermissionsMock(polishTenant.id, permissions)];
      const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, {
        tenantId: polishTenant.id,
      });

      render(<Component />, { apolloMocks, routerProps });
    };

    it('shows the Security tab to a role that can only view KSeF on a Polish organization', async () => {
      renderWithPermissions('PL', ['security.ksef.view', 'org.settings.view']);

      expect(await screen.findByRole('tab', { name: /general|organization/i })).toBeInTheDocument();
      expect(await screen.findByRole('tab', { name: /security/i })).toBeInTheDocument();
    });

    it('hides the Security tab for KSeF permissions on a non-Polish organization', async () => {
      renderWithPermissions('DE', ['security.ksef.view', 'org.settings.view']);

      expect(await screen.findByRole('tab', { name: /general|organization/i })).toBeInTheDocument();
      expect(screen.queryByRole('tab', { name: /security/i })).not.toBeInTheDocument();
    });
  });

  it('should render Members tab when user has members.view permission', async () => {
    const apolloMocks = [
      fillCommonQueryWithUser(user),
      createPermissionsMock(tenant.id, ['members.view', 'org.settings.view']),
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.members, {
      tenantId: tenant.id,
    });

    render(<Component />, { apolloMocks, routerProps });

    expect(await screen.findByRole('tab', { name: /members/i })).toBeInTheDocument();
  });

  it('should render Roles tab when user has org.roles.view permission', async () => {
    const apolloMocks = [
      fillCommonQueryWithUser(user),
      createPermissionsMock(tenant.id, ['org.roles.view', 'org.settings.view']),
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.roles, {
      tenantId: tenant.id,
    });

    render(<Component />, { apolloMocks, routerProps });

    expect(await screen.findByRole('tab', { name: /roles/i })).toBeInTheDocument();
  });

  it('should render General tab when user has org.settings.view permission', async () => {
    const apolloMocks = [
      fillCommonQueryWithUser(user),
      createPermissionsMock(tenant.id, ['org.settings.view']),
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, {
      tenantId: tenant.id,
    });

    render(<Component />, { apolloMocks, routerProps });

    expect(await screen.findByRole('tab', { name: /general/i })).toBeInTheDocument();
  });
});
