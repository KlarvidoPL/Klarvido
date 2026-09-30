import { TenantUserRole } from '@sb/webapp-api-client';
import { TenantType as TenantTypeField } from '@sb/webapp-api-client/constants';
import { commonQueryCurrentUserQuery } from '@sb/webapp-api-client/providers';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { act, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { companyLookupByNipQuery } from '../../../hooks/useCompanyLookup';
import { membershipFactory, tenantFactory } from '../../../tests/factories/tenant';
import { render } from '../../../tests/utils/rendering';
import { AddTenantForm } from '../addTenantForm.component';
import { addTenantMutation } from '../addTenantForm.graphql';

jest.mock('@sb/webapp-core/services/analytics');

const NIP = '9721382373';

const lookupMock = (company: Record<string, string> | null) =>
  composeMockedQueryResult(companyLookupByNipQuery, {
    variables: { nip: NIP },
    data: {
      companyLookupByNip: {
        __typename: 'CompanyLookupType',
        found: !!company,
        nip: NIP,
        companyName: company?.companyName ?? null,
        regon: company?.regon ?? null,
        address: company?.address ?? null,
        vatStatus: company?.vatStatus ?? null,
      },
    },
  });

const fillStepOne = async (name = 'new item name', nip = NIP) => {
  await userEvent.type(await screen.findByPlaceholderText('Name'), name);
  await userEvent.type(screen.getByLabelText(/nip/i), nip);
  await userEvent.click(screen.getByRole('button', { name: /next/i }));
};

describe('AddTenantForm: Component', () => {
  const Component = () => <AddTenantForm />;

  it('should display empty first step', async () => {
    const { waitForApolloMocks } = render(<Component />);
    await waitForApolloMocks();
    expect(await screen.findByPlaceholderText('Name')).toHaveValue('');
    expect(screen.getByLabelText(/nip/i)).toHaveValue('');
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create organization/i })).not.toBeInTheDocument();
  });

  it('should require a valid NIP before moving to the next step', async () => {
    render(<Component />);

    await fillStepOne('Acme', '1234567890');

    expect(await screen.findByText('Invalid NIP number')).toBeInTheDocument();
    expect(screen.queryByLabelText(/company name/i)).not.toBeInTheDocument();
  });

  it('should prefill company details found in the MF register', async () => {
    render(<Component />, {
      apolloMocks: [
        lookupMock({
          companyName: 'ACME SP. Z O.O.',
          regon: '123456785',
          address: 'UL. PRZYKŁADOWA 1, 00-001 WARSZAWA',
          vatStatus: 'ACTIVE',
        }),
      ],
    });

    await fillStepOne();

    expect(await screen.findByDisplayValue('ACME SP. Z O.O.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('123456785')).toBeInTheDocument();
    expect(screen.getByDisplayValue('UL. PRZYKŁADOWA 1, 00-001 WARSZAWA')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveTextContent('Active VAT payer');
    expect(screen.getByText(/we found your company/i)).toBeInTheDocument();
  });

  it('should leave company details empty when the NIP is not in the MF register', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne();

    expect(await screen.findByText(/couldn't find this NIP/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company name/i)).toHaveValue('');
    expect(screen.getByLabelText(/regon/i)).toHaveValue('');
    expect(screen.getByLabelText(/address/i)).toHaveValue('');
  });

  it('should require every company field before creating the organization', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne();

    // Nothing was found, so every field is empty: each one is flagged and creating is blocked
    expect(await screen.findByText('Company name is required')).toBeInTheDocument();
    expect(screen.getByText('REGON is required')).toBeInTheDocument();
    expect(screen.getByText('Address is required')).toBeInTheDocument();
    expect(screen.getByText('VAT status is required')).toBeInTheDocument();
    const createButton = screen.getByRole('button', { name: /create organization/i });
    expect(createButton).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/company name/i), 'JAN KOWALSKI');
    await userEvent.type(screen.getByLabelText(/regon/i), '123456785');
    await userEvent.type(screen.getByLabelText(/address/i), 'UL. DŁUGA 1, 00-001 WARSZAWA');
    expect(screen.queryByText('Company name is required')).not.toBeInTheDocument();
    // VAT status still missing
    expect(createButton).toBeDisabled();
  });

  it('should go back to step one and stay there, keeping its values', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne('Acme');
    await userEvent.click(await screen.findByRole('button', { name: /back/i }));

    expect(await screen.findByPlaceholderText('Name')).toHaveValue('Acme');
    expect(screen.getByLabelText(/nip/i)).toHaveValue(NIP);
    // Regression: the Back click used to be turned into a form submit (= Next) that jumped straight back to step 2
    await act(() => new Promise((resolve) => setTimeout(resolve, 100)));
    expect(screen.queryByLabelText(/company name/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });

  it('should name the fields the MF register is missing', async () => {
    render(<Component />, {
      apolloMocks: [
        lookupMock({
          companyName: 'JAN KOWALSKI',
          regon: '',
          address: 'UL. DŁUGA 1, 00-001 WARSZAWA',
          vatStatus: 'ACTIVE',
        }),
      ],
    });

    await fillStepOne();

    expect(await screen.findByText(/but it has no/i)).toHaveTextContent('REGON');
    expect(screen.getByDisplayValue('JAN KOWALSKI')).toBeInTheDocument();
    expect(screen.getByLabelText(/regon/i)).toHaveValue('');
  });

  describe('action completes successfully', () => {
    it('should commit mutation', async () => {
      const user = currentUserFactory();
      const commonQueryMock = fillCommonQueryWithUser(user);

      const variables = {
        input: {
          name: 'new item name',
          nip: NIP,
          companyName: 'ACME SP. Z O.O.',
          regon: '123456785',
          address: 'UL. PRZYKŁADOWA 1, 00-001 WARSZAWA',
          vatStatus: 'ACTIVE',
        },
      };
      const data = {
        createTenant: {
          tenantEdge: {
            node: {
              id: '1',
              name: variables.input.name,
            },
          },
        },
      };
      const requestMock = composeMockedQueryResult(addTenantMutation, {
        variables,
        data,
      });

      const currentUserRefetchData = {
        ...user,
        tenants: [
          ...(user.tenants ?? []),
          tenantFactory({
            id: '1',
            name: variables.input.name,
            type: TenantTypeField.ORGANIZATION,
            membership: membershipFactory({ role: TenantUserRole.OWNER }),
          }),
        ],
      };
      const refetchMock = composeMockedQueryResult(commonQueryCurrentUserQuery, {
        data: currentUserRefetchData,
      });

      render(<Component />, {
        apolloMocks: [
          commonQueryMock,
          lookupMock({
            companyName: variables.input.companyName,
            regon: variables.input.regon,
            address: variables.input.address,
            vatStatus: variables.input.vatStatus,
          }),
          requestMock,
          refetchMock,
        ],
      });

      await fillStepOne();
      await screen.findByDisplayValue(variables.input.companyName);
      await userEvent.click(screen.getByRole('button', { name: /create organization/i }));

      // Wait for the toast first (proves mutation completed), then verify mocks were called
      const toast = await screen.findByTestId('toast-1');
      expect(toast).toHaveTextContent('Organization added successfully!');

      expect(requestMock.result).toHaveBeenCalled();
      expect(trackEvent).toHaveBeenCalledWith('tenant', 'add', '1');
    });
  });
});
