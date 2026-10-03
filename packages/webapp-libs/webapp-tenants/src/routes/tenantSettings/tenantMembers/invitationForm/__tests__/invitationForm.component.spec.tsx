import { TenantUserRole } from '@sb/webapp-api-client';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedListQueryResult, composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { tenantMembersListQuery } from '../../../../../components/tenantMembersList/tenantMembersList.graphql';
import { RoutesConfig } from '../../../../../config/routes';
import { allOrganizationRolesQuery } from '../../../tenantRoles/tenantRoles.graphql';
import { tenantFactory } from '../../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../../tests/utils/rendering';
import { createTenantInvitation } from '../invitationForm.graphql';
import { InvitationForm } from '../invitationForm.component';

jest.mock('@sb/webapp-core/services/analytics');

const mockRoles = [
  {
    id: 'role-1',
    name: 'Member',
    description: 'Basic member role',
    color: 'BLUE',
    isSystemRole: true,
    isOwnerRole: false,
    memberCount: 5,
    permissions: [],
  },
  {
    id: 'role-2',
    name: 'Admin',
    description: 'Admin role',
    color: 'GREEN',
    isSystemRole: true,
    isOwnerRole: false,
    memberCount: 2,
    permissions: [],
  },
];

const createRolesMock = (tenantId: string) => {
  return composeMockedListQueryResult(allOrganizationRolesQuery, 'allOrganizationRoles', 'OrganizationRoleType', {
    variables: { tenantId },
    data: mockRoles,
  });
};

describe('InvitationForm: Component', () => {
  const Component = () => <InvitationForm />;

  it('should display empty form', async () => {
    const tenants = [tenantFactory({ membership: { role: TenantUserRole.MEMBER } })];
    const currentUser = currentUserFactory({ tenants });
    const rolesMock = createRolesMock(tenants[0].id);
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: tenants[0].id });

    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: [fillCommonQueryWithUser(currentUser), rolesMock],
      routerProps,
    });
    await waitForApolloMocks();

    const emailInput = await screen.findByLabelText(/email/i);
    expect(emailInput).toHaveValue('');

    expect(await screen.findByText(/Select roles/i)).toBeInTheDocument();
  });

  describe('action completes successfully', () => {
    it('should commit mutation', async () => {
      const tenants = [tenantFactory({ membership: { role: TenantUserRole.MEMBER } })];
      const currentUser = currentUserFactory({ tenants });
      const tenantId = tenants[0].id;

      const emailValue = 'example@example.com';
      const roleIds = ['role-1'];

      const rolesMock = createRolesMock(tenantId);

      const variables = {
        input: {
          email: emailValue,
          organizationRoleIds: roleIds,
          tenantId,
        },
      };

      const data = {
        createTenantInvitation: {
          ok: true,
        },
      };
      const requestMock = composeMockedQueryResult(createTenantInvitation, {
        variables,
        data,
      });

      const refetchData = {
        tenant: {
          userMemberships: [],
        },
      };

      const refetchMock = composeMockedQueryResult(tenantMembersListQuery, {
        data: refetchData,
        variables: {
          id: tenantId,
        },
      });

      const apolloMocks = [fillCommonQueryWithUser(currentUser), rolesMock, requestMock, refetchMock];
      const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId });

      const { waitForApolloMocks } = render(<Component />, { apolloMocks, routerProps });

      await waitForApolloMocks(1);

      // Type email
      await userEvent.type(await screen.findByLabelText(/email/i), emailValue);

      // Wait for roles to load and open dropdown
      const rolesButton = await screen.findByText(/Select roles/i);
      await userEvent.click(rolesButton);

      // Select a role
      const memberRole = await screen.findByText('Member');
      await userEvent.click(memberRole);

      // Submit the form
      await userEvent.click(screen.getByRole('button', { name: /invite/i }));

      // Wait for the toast (proves mutation completed)
      const toast = await screen.findByTestId('toast-1');
      expect(toast).toHaveTextContent('User invited successfully!');

      expect(requestMock.result).toHaveBeenCalled();
      expect(trackEvent).toHaveBeenCalledWith('tenantInvitation', 'invite', tenantId);
    });
  });

  describe('action fails validation', () => {
    const setupErrorTest = async (errorExtensions: Record<string, unknown>) => {
      const tenants = [tenantFactory({ membership: { role: TenantUserRole.MEMBER } })];
      const currentUser = currentUserFactory({ tenants });
      const tenantId = tenants[0].id;

      const emailValue = 'someone@example.com';
      const roleIds = ['role-1'];

      const rolesMock = createRolesMock(tenantId);

      const variables = {
        input: {
          email: emailValue,
          organizationRoleIds: roleIds,
          tenantId,
        },
      };

      const requestMock = composeMockedQueryResult(createTenantInvitation, {
        variables,
        data: null,
        errors: [{ message: 'GraphQlValidationError', extensions: errorExtensions }],
      });

      const apolloMocks = [fillCommonQueryWithUser(currentUser), rolesMock, requestMock];
      const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId });

      const { waitForApolloMocks } = render(<Component />, { apolloMocks, routerProps });

      await waitForApolloMocks(1);

      await userEvent.type(await screen.findByLabelText(/email/i), emailValue);

      const rolesButton = await screen.findByText(/Select roles/i);
      await userEvent.click(rolesButton);

      const memberRole = await screen.findByText('Member');
      await userEvent.click(memberRole);

      await userEvent.click(screen.getByRole('button', { name: /invite/i }));

      return screen.findByTestId('toast-1');
    };

    it('should show a translated, frontend-owned message for a known error code - never the raw server text', async () => {
      // Backend text is deliberately different from the frontend copy here to prove
      // the toast is driven by the `code`, not by echoing the server's message.
      const toast = await setupErrorTest({
        non_field_errors: [{ message: 'raw backend text that must never reach the UI', code: 'user_cannot_be_invited' }],
      });

      expect(toast).toHaveTextContent('This user cannot be a member of this organization.');
      expect(toast).not.toHaveTextContent('raw backend text');
    });

    it('should fall back to a generic translated message for an unrecognized error code', async () => {
      const toast = await setupErrorTest({
        non_field_errors: [{ message: 'Invitation already exists', code: 'invalid' }],
      });

      expect(toast).toHaveTextContent('Failed to invite user. Please try again.');
      expect(toast).not.toHaveTextContent('Invitation already exists');
    });

    it('should show a translated message when a non-owner tries to invite with the Owner role', async () => {
      const toast = await setupErrorTest({
        non_field_errors: [{ message: 'Only organization owners can invite members with the Owner role.', code: 'invalid' }],
      });

      expect(toast).toHaveTextContent('Only organization owners can invite members with the Owner role.');
    });

    it('should show a translated message naming the missing permission when the inviter lacks permissions the role grants', async () => {
      const toast = await setupErrorTest({
        non_field_errors: [
          { message: "You cannot invite a member with permissions you don't have: billing.manage", code: 'invalid' },
        ],
      });

      expect(toast).toHaveTextContent(/because you don.t have them yourself/i);
      expect(toast).not.toHaveTextContent("You cannot invite a member with permissions you don't have");
    });
  });
});
