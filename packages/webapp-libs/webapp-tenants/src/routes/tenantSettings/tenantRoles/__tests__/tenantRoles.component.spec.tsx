import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { Tabs } from '@sb/webapp-core/components/ui/tabs';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { RoutesConfig } from '../../../../config/routes';
import { membershipFactory, tenantFactory } from '../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../tests/utils/rendering';
import { TenantRoles } from '../tenantRoles.component';
import {
  allOrganizationRolesQuery,
  allPermissionsQuery,
  deleteOrganizationRoleMutation,
} from '../tenantRoles.graphql';

jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  PermissionGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  usePermissionCheck: (perm: string) => ({
    hasPermission: ['org.roles.view', 'org.roles.manage'].includes(perm),
    loading: false,
  }),
}));

const TENANT_ID = 'tenant-roles-1';

const createPermissionsMock = (permissions: string[] = []) =>
  composeMockedQueryResult(allPermissionsQuery, {
    variables: { tenantId: TENANT_ID },
    data: {
      allPermissions: {
        edges: [
          ...(permissions.includes('security.sso.manage') ? [{
            node: {
              id: 'legacy-sso', code: 'security.sso.manage', name: 'Manage SSO',
              description: 'Configure SSO and SCIM', category: 'SECURITY', sortOrder: 20,
            },
          }] : []),
          {
            node: {
              id: 'perm-1',
              code: 'org.settings.view',
              name: 'View Settings',
              description: null,
              category: 'ORGANIZATION',
              sortOrder: 1,
            },
          },
          {
            node: {
              id: 'perm-2',
              code: 'members.view',
              name: 'View Members',
              description: null,
              category: 'MEMBERS',
              sortOrder: 2,
            },
          },
        ],
      },
    },
  });

const createRolesMock = (
  roles: Array<{
    id: string;
    name: string;
    isSystemRole?: boolean;
    isOwnerRole?: boolean;
    memberCount?: number;
    color?: string;
  }> = []
) =>
  composeMockedQueryResult(allOrganizationRolesQuery, {
    variables: { tenantId: TENANT_ID },
    data: {
      allOrganizationRoles: {
        edges: roles.map((r) => ({
          node: {
            id: r.id,
            name: r.name,
            description: null,
            color: r.color || 'BLUE',
            systemRoleType: null,
            isSystemRole: r.isSystemRole ?? false,
            isOwnerRole: r.isOwnerRole ?? false,
            memberCount: r.memberCount ?? 0,
            permissions: [],
          },
        })),
      },
    },
  });

const createRolesErrorMock = () =>
  composeMockedQueryResult(allOrganizationRolesQuery, {
    variables: { tenantId: TENANT_ID },
    data: null as any,
    errors: [{ message: "Enum 'SystemRoleType' cannot represent value: ''" } as any],
  });

const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.roles, { tenantId: TENANT_ID });
const rolesPath = (routerProps.initialEntries as string[])?.[0] ?? '';

const Component = () => (
  <Tabs value={rolesPath}>
    <TenantRoles />
  </Tabs>
);

describe('TenantRoles: Component', () => {
  const renderComponent = (apolloMocks: ReturnType<typeof composeMockedQueryResult>[]) => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      membership: membershipFactory({ role: 'OWNER' }),
    });
    const user = currentUserFactory({ tenants: [tenant] });
    const commonQueryMock = fillCommonQueryWithUser(user);
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.roles, { tenantId: TENANT_ID });

    return render(<Component />, {
      apolloMocks: [commonQueryMock, ...apolloMocks],
      routerProps,
    });
  };

  it('hides a legacy SSO permission from the role editor', async () => {
    const permissionsMock = createPermissionsMock(['security.sso.manage']);
    renderComponent([permissionsMock, createRolesMock([])]);
    const createButton = await screen.findByRole('button', { name: /create role/i });
    await waitFor(() => expect(createButton).toBeEnabled());
    await userEvent.click(createButton);
    expect(await screen.findByText(/View Organization Settings/i)).toBeInTheDocument();
    expect(screen.queryByText(/Manage SSO|Configure SSO and SCIM/i)).not.toBeInTheDocument();
  });

  it('should render roles header', async () => {
    const permissionsMock = createPermissionsMock();
    const rolesMock = createRolesMock([
      { id: 'role-1', name: 'Owner', isSystemRole: true, isOwnerRole: true, memberCount: 1 },
      { id: 'role-2', name: 'Admin', isSystemRole: true, isOwnerRole: false, memberCount: 2 },
    ]);

    renderComponent([permissionsMock, rolesMock]);

    expect(await screen.findByText(/^Roles$/i)).toBeInTheDocument();
    expect(await screen.findByText(/manage roles and their default billing rates/i)).toBeInTheDocument();
  });

  it('should render Create Role button when user has manage permission', async () => {
    const permissionsMock = createPermissionsMock();
    const rolesMock = createRolesMock([]);

    renderComponent([permissionsMock, rolesMock]);

    expect(await screen.findByRole('button', { name: /create role/i })).toBeInTheDocument();
  });

  it('should render system roles section', async () => {
    const permissionsMock = createPermissionsMock();
    const rolesMock = createRolesMock([
      { id: 'role-1', name: 'Owner', isSystemRole: true, isOwnerRole: true, memberCount: 1 },
      { id: 'role-2', name: 'Admin', isSystemRole: true, isOwnerRole: false, memberCount: 2 },
    ]);

    renderComponent([permissionsMock, rolesMock]);

    expect(await screen.findByText(/system roles/i)).toBeInTheDocument();
    expect(await screen.findByText('Owner')).toBeInTheDocument();
    expect(await screen.findByText('Admin')).toBeInTheDocument();
  });

  it('should render custom roles section', async () => {
    const permissionsMock = createPermissionsMock();
    const rolesMock = createRolesMock([
      { id: 'role-1', name: 'Owner', isSystemRole: true, isOwnerRole: true },
      { id: 'role-2', name: 'Project Manager', isSystemRole: false, isOwnerRole: false, memberCount: 3 },
    ]);

    renderComponent([permissionsMock, rolesMock]);

    expect(await screen.findByText(/custom roles/i)).toBeInTheDocument();
    expect(await screen.findByText('Project Manager')).toBeInTheDocument();
  });

  it('should render empty state when no custom roles', async () => {
    const permissionsMock = createPermissionsMock();
    const rolesMock = createRolesMock([
      { id: 'role-1', name: 'Owner', isSystemRole: true, isOwnerRole: true },
    ]);

    renderComponent([permissionsMock, rolesMock]);

    expect(await screen.findByText(/no custom roles yet/i)).toBeInTheDocument();
    expect(await screen.findByText(/create custom roles to fine-tune member access/i)).toBeInTheDocument();
  });

  it('should show an error state instead of an empty list when the roles query fails', async () => {
    const permissionsMock = createPermissionsMock();
    const rolesErrorMock = createRolesErrorMock();

    renderComponent([permissionsMock, rolesErrorMock]);

    expect(await screen.findByText(/failed to load roles/i)).toBeInTheDocument();
    expect(screen.queryByText(/no custom roles yet/i)).not.toBeInTheDocument();
  });

  it('shows the real backend detail (not the raw "GraphQlValidationError" placeholder) when a role gains a member between load and delete', async () => {
    // Regression test: the role shows 0 members in this render (the data the user had when they
    // clicked delete), but by the time the mutation runs, another user has assigned a member to
    // it - a race condition the backend reports as a GraphQlValidationError, whose real detail
    // text lives in `extensions` as a list, not in the top-level `message`.
    const permissionsMock = createPermissionsMock();
    const rolesMock = createRolesMock([
      { id: 'role-2', name: 'Project Manager', isSystemRole: false, isOwnerRole: false, memberCount: 0 },
    ]);
    const deleteErrorMock = {
      request: {
        query: deleteOrganizationRoleMutation,
        variables: { id: 'role-2', tenantId: TENANT_ID },
      },
      result: {
        errors: [
          {
            message: 'GraphQlValidationError',
            extensions: [
              {
                message: 'This role is assigned to 1 member(s). Please provide a replacement role.',
                code: 'invalid',
              },
            ],
          } as any,
        ],
      },
    };

    renderComponent([permissionsMock, rolesMock, deleteErrorMock]);

    const deleteButton = await screen.findByRole('button', { name: /delete project manager role/i });
    await userEvent.click(deleteButton);

    const confirmButton = await screen.findByRole('button', { name: /delete role/i });
    await userEvent.click(confirmButton);

    expect(
      await screen.findByText(/this role is assigned to 1 member\. please choose a replacement role\./i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/^GraphQlValidationError$/)).not.toBeInTheDocument();
  });
});
