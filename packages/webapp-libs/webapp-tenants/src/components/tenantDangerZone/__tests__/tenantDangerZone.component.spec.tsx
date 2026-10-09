import { TenantUserRole } from '@sb/webapp-api-client';
import { commonQueryCurrentUserQuery } from '@sb/webapp-api-client/providers';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql';

import { RoutesConfig } from '../../../config/routes';
import { currentUserPermissionsQuery } from '../../../routes/tenantSettings/tenantRoles/tenantRoles.graphql';
import { membershipFactory, tenantFactory } from '../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../tests/utils/rendering';
import { TenantDangerZone } from '../tenantDangerZone.component';
import { deleteTenantMutation } from '../tenantDangerZone.graphql';

const MOCKED_TENANT_ID = '1';

const createPermissionsMock = (permissions: string[] = []) => {
  return composeMockedQueryResult(currentUserPermissionsQuery, {
    variables: { tenantId: MOCKED_TENANT_ID },
    data: {
      currentUserPermissions: permissions,
    },
  });
};

describe('TenantDangerSettings: Component', () => {
  const Component = () => <TenantDangerZone />;

  it('requires OTP and keeps the dialog open for correcting an invalid code', async () => {
    const user = currentUserFactory({
      otpEnabled: true,
      otpVerified: true,
      tenants: [tenantFactory({ name: 'name', id: MOCKED_TENANT_ID })],
    });
    const failed = composeMockedQueryResult(deleteTenantMutation, {
      variables: { input: { id: MOCKED_TENANT_ID, tenantId: MOCKED_TENANT_ID, otpToken: '123456' } },
      errors: [
        new GraphQLError('GraphQlValidationError', {
          extensions: { otp_token: [{ message: 'Invalid code', code: 'otp_verification_failure' }] },
        }),
      ],
    });
    render(<Component />, {
      apolloMocks: [fillCommonQueryWithUser(user), createPermissionsMock(['org.delete']), failed],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID }),
    });
    const trigger = await screen.findByRole('button', { name: /delete organization/i });
    await waitFor(() => expect(trigger).not.toBeDisabled());
    await userEvent.click(trigger);
    await userEvent.type(screen.getByLabelText(/Type DELETE name to confirm/i), 'DELETE name');
    const submit = screen.getByRole('button', { name: /continue/i });
    expect(submit).toBeDisabled();
    const code = screen.getByLabelText('Authentication code');
    await userEvent.type(code, '12345');
    expect(submit).toBeDisabled();
    await userEvent.type(code, '6');
    expect(submit).not.toBeDisabled();
    await userEvent.click(submit);
    expect(await screen.findByText('The verification code is invalid.')).toBeInTheDocument();
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await userEvent.click(trigger);
    expect(screen.getByLabelText('Authentication code')).toHaveValue('');
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled();
  });

  it('should render title', async () => {
    const user = currentUserFactory({
      tenants: [
        tenantFactory({
          name: 'name',
          id: MOCKED_TENANT_ID,
        }),
      ],
    });
    const commonQueryMock = fillCommonQueryWithUser(user);
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID });

    render(<Component />, { apolloMocks: [commonQueryMock], routerProps });

    expect(await screen.findByText('Danger Zone')).toBeInTheDocument();
  });

  it('should render delete organization', async () => {
    const user = currentUserFactory({
      tenants: [
        tenantFactory({
          name: 'name',
          id: MOCKED_TENANT_ID,
        }),
      ],
    });
    const commonQueryMock = fillCommonQueryWithUser(user);
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID });

    render(<Component />, { apolloMocks: [commonQueryMock], routerProps });

    expect(await screen.findByText('Delete this organization')).toBeInTheDocument();
    expect(screen.getByText('Delete organization')).toBeInTheDocument();
  });

  it('should render no permission message when user cannot delete', async () => {
    const user = currentUserFactory({
      tenants: [
        tenantFactory({
          name: 'name',
          id: MOCKED_TENANT_ID,
          membership: membershipFactory({ role: TenantUserRole.MEMBER }),
        }),
      ],
    });
    const commonQueryMock = fillCommonQueryWithUser(user);
    // Mock permissions query to return no delete permission
    const permissionsMock = createPermissionsMock([]);
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID });

    render(<Component />, { apolloMocks: [commonQueryMock, permissionsMock], routerProps });

    const button = await screen.findByRole('button', { name: /delete organization/i });
    expect(button).toBeInTheDocument();

    // Wait for permissions to load and check for no permission message
    await waitFor(() => {
      expect(screen.getByText(/You don't have permission to delete this organization/i)).toBeInTheDocument();
    });
  });

  it('should delete organization when user has permission', async () => {
    const user = currentUserFactory({
      tenants: [
        tenantFactory({
          name: 'name',
          id: MOCKED_TENANT_ID,
          membership: membershipFactory({ role: TenantUserRole.OWNER }),
        }),
      ],
    });
    const commonQueryMock = fillCommonQueryWithUser(user);
    // Mock permissions query to return delete permission
    const permissionsMock = createPermissionsMock(['org.delete']);

    const variables = {
      input: { id: MOCKED_TENANT_ID, tenantId: MOCKED_TENANT_ID },
    };
    const data = {
      deleteTenant: {
        deletedIds: [MOCKED_TENANT_ID],
        clientMutationId: '123',
      },
    };
    const requestMock = composeMockedQueryResult(deleteTenantMutation, {
      variables,
      data,
    });
    const currentUserRefetchData = {
      ...user,
      tenants: [],
    };
    const refetchMock = composeMockedQueryResult(commonQueryCurrentUserQuery, {
      data: currentUserRefetchData,
    });

    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID });
    render(<Component />, {
      apolloMocks: [commonQueryMock, permissionsMock, requestMock, refetchMock],
      routerProps,
    });

    // Wait for the button to be enabled (permissions loaded)
    const button = await screen.findByRole('button', { name: /delete organization/i });

    // Wait for the button to be enabled
    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });

    await userEvent.click(button);

    // Wait for dialog to open and find Continue button
    const continueButton = await screen.findByRole('button', { name: /continue/i });

    // Continue stays disabled until the exact "DELETE <org name>" confirmation is typed
    expect(continueButton).toBeDisabled();

    const confirmationInput = screen.getByRole('textbox');
    await userEvent.type(confirmationInput, 'DELETE name');

    expect(continueButton).not.toBeDisabled();

    await userEvent.click(continueButton);

    // Wait for the toast (proves mutation completed)
    const toast = await screen.findByTestId('toast-1');
    expect(toast).toHaveTextContent('Organization deleted successfully!');
    expect(requestMock.result).toHaveBeenCalled();
  });
});
