import { TenantType } from '@sb/webapp-api-client/constants';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { tenantFactory } from '../../../tests/factories/tenant';
import {
  CurrentTenantRouteWrapper,
  createMockRouterProps,
  render,
} from '../../../tests/utils/rendering';
import { RoutesConfig } from '../../../config/routes';
import { TenantSwitchSidebar } from '../tenantSwitchSidebar.component';

describe('TenantSwitchSidebar: Component', () => {
  const orgTenant = tenantFactory({
    id: 'org-1',
    name: 'Org One',
    type: TenantType.ORGANIZATION,
    membership: { role: 'OWNER', invitationAccepted: true, invitationToken: 'token', id: 'm1' },
  });
  const user = currentUserFactory({ tenants: [orgTenant] });

  const Component = (props: { collapsed?: boolean } = {}) => (
    <CurrentTenantRouteWrapper>
      <TenantSwitchSidebar {...props} />
    </CurrentTenantRouteWrapper>
  );

  it('should render current tenant name when not collapsed', async () => {
    const apolloMocks = [fillCommonQueryWithUser(user)];
    const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: orgTenant.id });

    render(<Component />, { apolloMocks, routerProps });

    const trigger = await screen.findByRole('button');
    await userEvent.click(trigger);

    const orgOneElements = screen.getAllByText(/org one/i);
    expect(orgOneElements.length).toBeGreaterThan(0);
    expect(screen.getByText(/organizations/i)).toBeInTheDocument();
  });

  it('should render create new organization option', async () => {
    const apolloMocks = [fillCommonQueryWithUser(user)];
    const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: orgTenant.id });

    render(<Component />, { apolloMocks, routerProps });

    const trigger = await screen.findByRole('button');
    await userEvent.click(trigger);

    expect(screen.getByText(/create new organization/i)).toBeInTheDocument();
  });

  describe('superuser cross-tenant access', () => {
    // A superuser sees a tenant they have no real membership in (owner-equivalent
    // access bypass) - the backend returns `membership: null` for it, which must
    // not be mistaken for a genuine unaccepted invitation.
    const bypassTenant = tenantFactory({
      id: 'org-2',
      name: 'Bypass Org',
      type: TenantType.ORGANIZATION,
      membership: null,
    });

    it('should list a superuser bypass tenant under Organizations, not Invitations', async () => {
      const superuser = currentUserFactory({ tenants: [orgTenant, bypassTenant], isSuperuser: true });
      const apolloMocks = [fillCommonQueryWithUser(superuser)];
      const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: orgTenant.id });

      render(<Component />, { apolloMocks, routerProps });

      const trigger = await screen.findByRole('button');
      await userEvent.click(trigger);

      expect(await screen.findByText(/bypass org/i)).toBeInTheDocument();
      expect(screen.queryByText(/invitations/i)).not.toBeInTheDocument();
    });

    it('should still show a real unaccepted invitation for a superuser under Invitations', async () => {
      const realInvitation = tenantFactory({
        id: 'org-3',
        name: 'Real Invite Org',
        type: TenantType.ORGANIZATION,
        membership: { role: 'MEMBER', invitationAccepted: false, invitationToken: 'real-token', id: 'm3' },
      });
      const superuser = currentUserFactory({ tenants: [orgTenant, realInvitation], isSuperuser: true });
      const apolloMocks = [fillCommonQueryWithUser(superuser)];
      const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: orgTenant.id });

      render(<Component />, { apolloMocks, routerProps });

      const trigger = await screen.findByRole('button');
      await userEvent.click(trigger);

      expect(screen.getByText(/invitations/i)).toBeInTheDocument();
      expect(screen.getByText(/real invite org/i)).toBeInTheDocument();
    });

    it('should keep bucketing a null-membership tenant as an invitation for a regular user', async () => {
      const regularUser = currentUserFactory({ tenants: [orgTenant, bypassTenant], isSuperuser: false });
      const apolloMocks = [fillCommonQueryWithUser(regularUser)];
      const routerProps = createMockRouterProps(RoutesConfig.home, { tenantId: orgTenant.id });

      render(<Component />, { apolloMocks, routerProps });

      const trigger = await screen.findByRole('button');
      await userEvent.click(trigger);

      expect(screen.getByText(/invitations/i)).toBeInTheDocument();
    });
  });
});
