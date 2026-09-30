import { TenantType as TenantTypeField } from '@sb/webapp-api-client/constants';
import { commonQueryCurrentUserQuery } from '@sb/webapp-api-client/providers';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { RoutesConfig } from '../../../../config/routes';
import { companyLookupByNipQuery } from '../../../../hooks/useCompanyLookup';
import { tenantFactory } from '../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../tests/utils/rendering';
import { currentUserPermissionsQuery } from '../../tenantRoles/tenantRoles.graphql';
import { TenantGeneralSettings } from '../tenantGeneralSettings.component';
import { updateTenantMutation } from '../tenantGeneralSettings.graphql';

const MOCKED_TENANT_ID = '1';

const COMPANY_DETAILS = {
  nip: '9721382373',
  companyName: 'ACME SP. Z O.O.',
  regon: '123456785',
  address: 'UL. PRZYKŁADOWA 1, 00-001 WARSZAWA',
  vatStatus: 'ACTIVE',
};

const createPermissionsMock = (permissions: string[] = []) => {
  return composeMockedQueryResult(currentUserPermissionsQuery, {
    variables: { tenantId: MOCKED_TENANT_ID },
    data: {
      currentUserPermissions: permissions,
    },
  });
};

const renderWithTenant = (extraMocks: ReturnType<typeof composeMockedQueryResult>[] = []) => {
  const user = currentUserFactory({
    tenants: [tenantFactory({ name: 'name', id: MOCKED_TENANT_ID, ...COMPANY_DETAILS })],
  });
  const commonQueryMock = fillCommonQueryWithUser(user);
  const permissionsMock = createPermissionsMock(['org.settings.edit', 'org.delete']);
  const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID });

  render(<TenantGeneralSettings />, { apolloMocks: [commonQueryMock, permissionsMock, ...extraMocks], routerProps });
  return { user };
};

describe('TenantGeneralSettings: Component', () => {
  it('should show the company details of the current organization', async () => {
    renderWithTenant();

    expect(await screen.findByDisplayValue(COMPANY_DETAILS.nip)).toBeInTheDocument();
    expect(screen.getByDisplayValue(COMPANY_DETAILS.companyName)).toBeInTheDocument();
    expect(screen.getByDisplayValue(COMPANY_DETAILS.regon)).toBeInTheDocument();
    expect(screen.getByDisplayValue(COMPANY_DETAILS.address)).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveTextContent('Active VAT payer');
  });

  it('should commit update mutation', async () => {
    const variables = {
      input: { id: MOCKED_TENANT_ID, tenantId: MOCKED_TENANT_ID, name: 'name - new item name', ...COMPANY_DETAILS },
    };
    const requestMock = composeMockedQueryResult(updateTenantMutation, {
      variables,
      data: { updateTenant: { tenant: variables.input } },
    });

    const user = currentUserFactory({
      tenants: [tenantFactory({ name: 'name', id: MOCKED_TENANT_ID, ...COMPANY_DETAILS })],
    });
    const refetchMock = composeMockedQueryResult(commonQueryCurrentUserQuery, {
      data: {
        ...user,
        tenants: [
          tenantFactory({
            id: MOCKED_TENANT_ID,
            name: variables.input.name,
            type: TenantTypeField.ORGANIZATION,
            ...COMPANY_DETAILS,
          }),
        ],
      },
    });

    renderWithTenant([requestMock, refetchMock]);

    // Wait for permissions to load and form to be enabled
    const nameInput = await screen.findByPlaceholderText('Name');
    await waitFor(() => {
      expect(nameInput).not.toBeDisabled();
    });

    await userEvent.type(nameInput, ' - new item name');
    await userEvent.click(screen.getByRole('button', { name: /save/i }));

    // Wait for the toast first (proves mutation completed), then verify mock was called
    const toast = await screen.findByTestId('toast-1');
    expect(toast).toHaveTextContent('Organization updated successfully!');
    expect(requestMock.result).toHaveBeenCalled();
  });

  it('should refresh company details from MF', async () => {
    const lookupMock = composeMockedQueryResult(companyLookupByNipQuery, {
      variables: { nip: COMPANY_DETAILS.nip },
      data: {
        companyLookupByNip: {
          __typename: 'CompanyLookupType',
          found: true,
          nip: COMPANY_DETAILS.nip,
          companyName: 'ACME NEW NAME SP. Z O.O.',
          regon: COMPANY_DETAILS.regon,
          address: 'UL. NOWA 5, 00-002 WARSZAWA',
          vatStatus: 'EXEMPT',
        },
      },
    });

    renderWithTenant([lookupMock]);

    const refreshButton = await screen.findByRole('button', { name: /refresh from mf/i });
    await waitFor(() => expect(screen.getByPlaceholderText('Name')).not.toBeDisabled());
    await userEvent.click(refreshButton);

    expect(await screen.findByDisplayValue('ACME NEW NAME SP. Z O.O.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('UL. NOWA 5, 00-002 WARSZAWA')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveTextContent('Exempt from VAT');
  });

  it('should keep existing values the MF register is missing and say which', async () => {
    const lookupMock = composeMockedQueryResult(companyLookupByNipQuery, {
      variables: { nip: COMPANY_DETAILS.nip },
      data: {
        companyLookupByNip: {
          __typename: 'CompanyLookupType',
          found: true,
          nip: COMPANY_DETAILS.nip,
          companyName: 'ACME NEW NAME SP. Z O.O.',
          regon: COMPANY_DETAILS.regon,
          address: null,
          vatStatus: 'ACTIVE',
        },
      },
    });

    renderWithTenant([lookupMock]);

    const refreshButton = await screen.findByRole('button', { name: /refresh from mf/i });
    await waitFor(() => expect(screen.getByPlaceholderText('Name')).not.toBeDisabled());
    await userEvent.click(refreshButton);

    expect(await screen.findByDisplayValue('ACME NEW NAME SP. Z O.O.')).toBeInTheDocument();
    // The address wasn't returned, so the saved one stays
    expect(screen.getByDisplayValue(COMPANY_DETAILS.address)).toBeInTheDocument();
    expect(await screen.findByTestId('toast-1')).toHaveTextContent('the register has no address');
  });

  it('should make a saved NIP and REGON read-only', async () => {
    renderWithTenant();

    expect(await screen.findByDisplayValue(COMPANY_DETAILS.nip)).toHaveAttribute('readonly');
    expect(screen.getByDisplayValue(COMPANY_DETAILS.regon)).toHaveAttribute('readonly');
    expect(screen.getByDisplayValue(COMPANY_DETAILS.address)).not.toHaveAttribute('readonly');
    expect(screen.getByText("NIP and REGON can't be changed once saved.")).toBeInTheDocument();
  });

  it('should let an organization without a NIP yet fill it in', async () => {
    const user = currentUserFactory({
      tenants: [tenantFactory({ name: 'name', id: MOCKED_TENANT_ID, nip: '', regon: '' })],
    });
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: MOCKED_TENANT_ID });
    render(<TenantGeneralSettings />, {
      apolloMocks: [fillCommonQueryWithUser(user), createPermissionsMock(['org.settings.edit'])],
      routerProps,
    });

    const nipInput = await screen.findByLabelText(/nip/i);
    expect(nipInput).not.toHaveAttribute('readonly');
    expect(screen.getByLabelText(/regon/i)).not.toHaveAttribute('readonly');
    expect(screen.queryByText("NIP and REGON can't be changed once saved.")).not.toBeInTheDocument();
  });
});
