import { TenantUserRole } from '@sb/webapp-api-client';
import { TenantType as TenantTypeType } from '@sb/webapp-api-client/constants';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { getLocalePath, getTenantPathHelper } from '@sb/webapp-core/utils';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';

import { tenantFactory } from '../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../tests/utils/rendering';
import { TenantInvitation } from '../tenantInvitation.component';
import { acceptTenantInvitationMutation, declineTenantInvitationMutation } from '../tenantInvitation.graphql';

jest.mock('@sb/webapp-core/services/analytics');

describe('TenantInvitation: Component', () => {
  const Component = () => (
    <Routes>
      <Route path={getLocalePath(RoutesConfig.tenantInvitation)} element={<TenantInvitation />} />
      <Route path={getLocalePath(RoutesConfig.home)} element={<div>Home page mock</div>} />
      <Route path={getTenantPathHelper(RoutesConfig.home)} element={<div>Org home page mock</div>} />
    </Routes>
  );
  const routePath = RoutesConfig.tenantInvitation;

  it('shows an unverified invitation, blocks acceptance, and allows decline without a token', async () => {
    const targetTenant = tenantFactory({
      name: 'Invited organization',
      type: TenantTypeType.ORGANIZATION,
      membership: { invitationAccepted: false, invitationToken: null },
    });
    const user = currentUserFactory({ isConfirmed: false, tenants: [targetTenant] });
    const requestMock = composeMockedQueryResult(declineTenantInvitationMutation, {
      variables: { input: { id: targetTenant.membership.id } },
      data: { declineTenantInvitation: { ok: true } },
    });
    const routerProps = createMockRouterProps(routePath, { tenantId: '', token: 'pending' });
    routerProps.initialEntries = [
      `/en/tenant-invitation/pending?membershipId=${encodeURIComponent(targetTenant.membership.id)}`,
    ];
    render(<Component />, {
      routerProps,
      apolloMocks: [fillCommonQueryWithUser(user), requestMock, fillCommonQueryWithUser({ ...user, tenants: [] })],
    });
    expect(await screen.findByText('Invited organization')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /accept invitation/i })).toBeDisabled();
    expect(screen.getByText('Verify your email address before accepting this invitation.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /decline/i })).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: /decline/i }));
    expect(await screen.findByTestId('toast-1')).toHaveTextContent('Invitation declined.');
    expect(requestMock.result).toHaveBeenCalled();
  });

  it('enables acceptance after returning from email verification', async () => {
    const targetTenant = tenantFactory({
      name: 'Verification organization',
      type: TenantTypeType.ORGANIZATION,
      membership: { invitationAccepted: false, invitationToken: null },
    });
    const user = currentUserFactory({ isConfirmed: false, tenants: [targetTenant] });
    const verifiedUser = {
      ...user,
      isConfirmed: true,
      tenants: [{ ...targetTenant, membership: { ...targetTenant.membership, invitationToken: 'verified-token' } }],
    };
    const routerProps = createMockRouterProps(routePath, { tenantId: '', token: 'pending' });
    routerProps.initialEntries = [
      `/en/tenant-invitation/pending?membershipId=${encodeURIComponent(targetTenant.membership.id)}`,
    ];
    render(<Component />, {
      routerProps,
      apolloMocks: [fillCommonQueryWithUser(user), fillCommonQueryWithUser(verifiedUser)],
    });
    expect(await screen.findByText('Verification organization')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /accept invitation/i })).toBeDisabled();
    fireEvent(window, new Event('focus'));
    await waitFor(() => expect(screen.getByRole('button', { name: /accept invitation/i })).toBeEnabled());
    expect(screen.queryByText('Verify your email address before accepting this invitation.')).not.toBeInTheDocument();
  });

  describe('token is invalid', () => {
    it('should redirect to home', async () => {
      const routerProps = createMockRouterProps(routePath, { tenantId: '', token: 'invalid-token' });

      render(<Component />, { routerProps });

      expect(await screen.findByText(/Home page mock/i)).toBeInTheDocument();
    });
  });

  describe('token is already accepted', () => {
    it('should redirect to org home', async () => {
      const token = 'valid-token';
      const routerProps = createMockRouterProps(routePath, { tenantId: '', token });
      const targetTenant = tenantFactory({
        membership: { role: TenantUserRole.MEMBER, invitationAccepted: true, invitationToken: token },
        type: TenantTypeType.ORGANIZATION,
      });
      const apolloMocks = [
        fillCommonQueryWithUser(
          currentUserFactory({
            tenants: [tenantFactory({ membership: { role: TenantUserRole.OWNER } }), targetTenant],
          })
        ),
      ];

      render(<Component />, { routerProps, apolloMocks });

      expect(await screen.findByText(/Org home page mock/i)).toBeInTheDocument();
    });
  });

  describe('token is valid', () => {
    it('should send accept mutation on button click', async () => {
      const token = 'valid-token';
      const routerProps = createMockRouterProps(routePath, { tenantId: '', token });
      const targetTenant = tenantFactory({
        membership: { role: TenantUserRole.MEMBER, invitationAccepted: false, invitationToken: token },
        type: TenantTypeType.ORGANIZATION,
      });

      const user = currentUserFactory({
        tenants: [tenantFactory({ membership: { role: TenantUserRole.OWNER } }), targetTenant],
      });

      const variables = {
        input: { token, id: targetTenant.membership.id },
      };
      const data = {
        acceptTenantInvitation: {
          ok: true,
        },
      };
      const requestMock = composeMockedQueryResult(acceptTenantInvitationMutation, {
        variables,
        data,
      });

      const currentUserRefetchData = {
        ...user,
        tenants: [
          user.tenants![0],
          {
            ...targetTenant,
            membership: {
              ...targetTenant.membership,
              invitationAccepted: true,
            },
          },
        ],
      };
      const refetchMock = fillCommonQueryWithUser(currentUserRefetchData);

      const apolloMocks = [fillCommonQueryWithUser(user), requestMock, refetchMock];

      render(<Component />, { routerProps, apolloMocks });

      expect(await screen.findByText(/Accept/i)).toBeInTheDocument();

      await userEvent.click(screen.getByRole('button', { name: /accept/i }));

      // Wait for the toast first (proves mutation completed), then verify mocks were called
      const toast = await screen.findByTestId('toast-1');
      expect(toast).toHaveTextContent('Invitation accepted!');

      expect(requestMock.result).toHaveBeenCalled();
      expect(trackEvent).toHaveBeenCalledWith('tenantInvitation', 'accept', targetTenant.id);
    });

    it('should send decline mutation on button click', async () => {
      const token = 'valid-token';
      const routerProps = createMockRouterProps(routePath, { tenantId: '', token });
      const targetTenant = tenantFactory({
        membership: { role: TenantUserRole.MEMBER, invitationAccepted: false, invitationToken: token },
        type: TenantTypeType.ORGANIZATION,
      });

      const user = currentUserFactory({
        tenants: [tenantFactory({ membership: { role: TenantUserRole.OWNER } }), targetTenant],
      });

      const variables = {
        input: { token, id: targetTenant.membership.id },
      };
      const data = {
        declineTenantInvitation: {
          ok: true,
        },
      };
      const requestMock = composeMockedQueryResult(declineTenantInvitationMutation, {
        variables,
        data,
      });

      const currentUserRefetchData = {
        ...user,
        tenants: [user.tenants![0]],
      };
      const refetchMock = fillCommonQueryWithUser(currentUserRefetchData);

      const apolloMocks = [fillCommonQueryWithUser(user), requestMock, refetchMock];

      render(<Component />, { routerProps, apolloMocks });

      expect(await screen.findByText(/Decline/i)).toBeInTheDocument();

      await userEvent.click(screen.getByRole('button', { name: /decline/i }));

      // Wait for the toast first (proves mutation completed), then verify mocks were called
      const toast = await screen.findByTestId('toast-1');
      expect(toast).toHaveTextContent('Invitation declined.');

      expect(requestMock.result).toHaveBeenCalled();
      expect(trackEvent).toHaveBeenCalledWith('tenantInvitation', 'decline', targetTenant.id);
    });
  });
});
