import { TenantUserRole } from '@sb/webapp-api-client';
import { TenantType } from '@sb/webapp-api-client/constants';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { tenantFactory } from '../../../tests/factories/tenant';
import {
  CurrentTenantRouteWrapper as TenantWrapper,
  createMockRouterProps,
  render,
} from '../../../tests/utils/rendering';
import { TenantSwitch } from '../tenantSwitch.component';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => {
  return {
    ...jest.requireActual<NodeModule>('react-router-dom'),
    useNavigate: () => mockNavigate,
  };
});

const personalTenantName = 'Test Tenant';
const organizationTenantName = 'Organization Tenant';
const organizationPendingTenantName = 'Organization Pending Tenant';

const personalTenant = tenantFactory({
  name: personalTenantName,
  type: TenantType.PERSONAL,
  membership: { role: TenantUserRole.OWNER },
});
const organizationTenant = tenantFactory({
  name: organizationTenantName,
  type: TenantType.ORGANIZATION,
  membership: { role: TenantUserRole.OWNER, invitationAccepted: true },
});
const organizationPendingTenant = tenantFactory({
  name: organizationPendingTenantName,
  type: TenantType.ORGANIZATION,
  membership: { role: TenantUserRole.MEMBER, invitationAccepted: false },
});

const tenants = [personalTenant, organizationTenant, organizationPendingTenant];
const getApolloMocks = () => [fillCommonQueryWithUser(currentUserFactory({ tenants }))];

const openSwitch = async () => {
  const trigger = await screen.findByTestId('tenant-switch-trigger-btn');
  await userEvent.click(trigger);
};

describe('TenantSwitch: Component', () => {
  const Component = () => <TenantSwitch />;

  it('should auto-select the single real organization as the current tenant', async () => {
    // Only `organizationTenant` is a real accepted-membership organization here
    // (the personal tenant and the pending invite don't count) - it must be
    // auto-selected rather than defaulting to the personal tenant.
    render(<Component />, { apolloMocks: getApolloMocks() });

    expect(await screen.findByText(organizationTenantName)).toBeInTheDocument();
    expect(screen.getByTestId('tenant-settings-btn')).toBeInTheDocument();
  });

  it('should render correct tenant name when param in url', async () => {
    const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: organizationTenant.id });
    render(<Component />, { apolloMocks: getApolloMocks(), routerProps, TenantWrapper });

    expect(await screen.findByText(organizationTenantName)).toBeInTheDocument();
    expect(screen.getByTestId('tenant-settings-btn')).toBeInTheDocument();
  });

  it('should not select a tenant via URL param when its invitation is unaccepted', async () => {
    // Zero real (accepted-membership) organizations here, so this also rules out the
    // "exactly one real org" auto-select fallback masking the assertion.
    const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: organizationPendingTenant.id });
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ tenants: [organizationPendingTenant] }))];
    render(<Component />, { apolloMocks, routerProps, TenantWrapper });

    expect(await screen.findByTestId('tenant-switch-trigger-btn')).toHaveTextContent('');
    expect(screen.queryByTestId('tenant-settings-btn')).not.toBeInTheDocument();
  });

  it('should not render organization and invitation labels if only personal tenant', async () => {
    render(<Component />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ tenants: [personalTenant] }))],
    });

    await openSwitch();

    expect(screen.queryByText(/organizations/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/invitations/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('tenant-invitation-pending-btn')).not.toBeInTheDocument();
  });

  it('should handle invitation tenant click', async () => {
    render(<Component />, { apolloMocks: getApolloMocks(), TenantWrapper });

    await openSwitch();

    expect(await screen.findByText(/invitations/i)).toBeInTheDocument();
    const invitationTenantButton = await screen.findByText(organizationPendingTenantName);

    await userEvent.click(invitationTenantButton);

    expect(mockNavigate).toHaveBeenCalledWith(
      `/en/tenant-invitation/${organizationPendingTenant.membership.invitationToken}`
    );
  });

  it('should handle tenant change', async () => {
    // Two real organizations and nothing selected yet, so `organizationTenant`'s
    // name only appears once (in the dropdown list, not also in the trigger button).
    const otherOrganizationTenant = tenantFactory({
      name: 'Other Organization Tenant',
      type: TenantType.ORGANIZATION,
      membership: { role: TenantUserRole.OWNER, invitationAccepted: true },
    });
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [organizationTenant, otherOrganizationTenant] })),
    ];
    render(<Component />, { apolloMocks, TenantWrapper });

    await openSwitch();

    expect(await screen.findByText(/organizations/i)).toBeInTheDocument();
    const invitationTenantButton = await screen.findByText(organizationTenantName);

    await userEvent.click(invitationTenantButton);

    expect(mockNavigate).toHaveBeenCalledWith(`/en/${organizationTenant.id}`);
  });

  it('should handle create new tenant click', async () => {
    render(<Component />, { apolloMocks: getApolloMocks() });

    await openSwitch();

    const newTenantButton = await screen.findByText(/create new organization/i);
    await userEvent.click(newTenantButton);

    expect(mockNavigate).toHaveBeenCalledWith(`/en/add-organization`);
  });

  it('should handle settings click', async () => {
    const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: organizationTenant.id });
    render(<Component />, { apolloMocks: getApolloMocks(), routerProps, TenantWrapper });

    const settingsButton = await screen.findByTestId('tenant-settings-btn');
    await userEvent.click(settingsButton);

    expect(mockNavigate).toHaveBeenCalledWith(`/en/${organizationTenant.id}/tenant/settings/members`);
  });

  it('should handle invitation pending badge click', async () => {
    render(<Component />, { apolloMocks: getApolloMocks() });

    const invitationPendingButton = await screen.findByTestId('tenant-invitation-pending-btn');
    await userEvent.click(invitationPendingButton);

    expect(mockNavigate).toHaveBeenCalledWith(
      `/en/tenant-invitation/${organizationPendingTenant.membership.invitationToken}`
    );
  });

  describe('superuser cross-tenant access', () => {
    // A superuser sees a tenant they have no real membership in (owner-equivalent
    // access bypass) - the backend returns `membership: null` for it, which must not
    // be mistaken for a genuine unaccepted invitation (previously this both showed
    // up under "Invitations" and did nothing on click, since there's no real
    // invitationToken to navigate with).
    const bypassTenantName = 'Bypass Org';
    const bypassTenant = tenantFactory({
      name: bypassTenantName,
      type: TenantType.ORGANIZATION,
      membership: null,
    });
    const superuserTenants = [personalTenant, bypassTenant];
    const getSuperuserApolloMocks = () => [
      fillCommonQueryWithUser(currentUserFactory({ tenants: superuserTenants, isSuperuser: true })),
    ];

    it('should list the bypass tenant under Organizations, not Invitations', async () => {
      render(<Component />, { apolloMocks: getSuperuserApolloMocks(), TenantWrapper });

      await openSwitch();

      expect(await screen.findByText(/organizations/i)).toBeInTheDocument();
      expect(screen.getByText(bypassTenantName)).toBeInTheDocument();
      expect(screen.queryByText(/invitations/i)).not.toBeInTheDocument();
    });

    it('should actually navigate when clicking the bypass tenant, not silently no-op', async () => {
      render(<Component />, { apolloMocks: getSuperuserApolloMocks(), TenantWrapper });

      await openSwitch();

      const bypassTenantButton = await screen.findByText(bypassTenantName);
      await userEvent.click(bypassTenantButton);

      expect(mockNavigate).toHaveBeenCalledWith(`/en/${bypassTenant.id}`);
    });
  });
});
