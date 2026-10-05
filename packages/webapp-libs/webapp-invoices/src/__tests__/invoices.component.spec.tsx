import { MockedProvider } from '@apollo/client/testing/react';
import { askKlarvido } from '@sb/webapp-ai-assistant';
import { ComponentKind } from '@sb/webapp-api-client/graphql';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { IntlProvider } from 'react-intl';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import { InvoiceDetails, InvoiceList } from '../invoices.component';
import { invoiceQuery, invoiceSetupQuery, invoicesQuery, startInvoiceSyncMutation } from '../invoices.graphql';
import { historyStartDate } from '../invoices.utils';

let mockPermissions = new Set(['invoices.sync', 'invoices.export', 'invoices.categorize', 'features.ai.use']);
jest.mock('@sb/webapp-tenants/hooks', () => ({
  useGenerateTenantPath: () => (path: string) => `/company/${path}`,
  usePermissionCheck: (permission: string) => ({ hasPermission: mockPermissions.has(permission) }),
}));
jest.mock('@sb/webapp-tenants/providers', () => ({ useCurrentTenant: () => ({ data: { id: 'tenant-1' } }) }));
jest.mock('@sb/webapp-ai-assistant', () => ({ askKlarvido: jest.fn() }));
const status = { connected: true, startDate: null, lastSuccessAt: null, importErrorCount: 0, runs: [] };
const setup = {
  request: { query: invoiceSetupQuery, variables: { tenantId: 'tenant-1' } },
  result: { data: { invoiceCategories: [], invoiceSyncStatus: status } },
  maxUsageCount: Infinity,
};
const invoice = {
  id: 'invoice-1',
  number: 'FV/1',
  ksefNumber: 'ksef-1',
  direction: 'SALE',
  kind: 'VAT',
  issueDate: '2026-01-01',
  sellerName: 'Seller',
  sellerNip: '5252344078',
  buyerName: 'Buyer',
  buyerNip: '1234567890',
  currency: 'PLN',
  net: '100.00',
  vat: '23.00',
  gross: '123.00',
  category: null,
};
const list = {
  request: { query: invoicesQuery, variables: { tenantId: 'tenant-1', filters: {}, page: 1 } },
  result: { data: { invoices: { totalCount: 1, items: [invoice] } } },
  maxUsageCount: Infinity,
};
const Location = () => {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
};
const wrapper = (element: React.ReactNode, mocks = [setup, list] as any[], path = '/') =>
  render(
    <MockedProvider mocks={mocks}>
      <IntlProvider locale="pl" defaultLocale="pl">
        <MemoryRouter initialEntries={[path]}>
          {element}
          <Location />
        </MemoryRouter>
      </IntlProvider>
    </MockedProvider>
  );

beforeEach(() => {
  jest.clearAllMocks();
  mockPermissions = new Set(['invoices.sync', 'invoices.export', 'invoices.categorize', 'features.ai.use']);
});

it('defaults to twelve months and imports only after clicking', async () => {
  const imported = jest.fn(() => ({ data: { startInvoiceSync: { runId: 1 } } }));
  wrapper(<InvoiceList />, [
    setup,
    list,
    {
      request: {
        query: startInvoiceSyncMutation,
        variables: { input: { tenantId: 'tenant-1', startDate: historyStartDate(12) } },
      },
      result: imported,
    },
  ]);
  const button = await screen.findByRole('button', { name: 'Pobierz faktury z KSeF' });
  expect(screen.getByLabelText('Zakres historii')).toHaveValue('12');
  expect(imported).not.toHaveBeenCalled();
  fireEvent.click(button);
  await waitFor(() => expect(imported).toHaveBeenCalledTimes(1));
});

it('attaches the filtered list and selected invoices, and stores filters in URL', async () => {
  wrapper(<InvoiceList />, [
    setup,
    list,
    {
      ...list,
      request: {
        query: invoicesQuery,
        variables: { tenantId: 'tenant-1', filters: { direction: 'PURCHASE' }, page: 1 },
      },
    },
  ]);
  await screen.findByText('FV/1');
  fireEvent.click(screen.getByRole('button', { name: 'Zapytaj Klarvido' }));
  expect(askKlarvido).toHaveBeenCalledWith('tenant-1', 'Lista faktur z filtrami', {
    kind: ComponentKind.INVOICE_LIST,
    filters: {},
  });
  fireEvent.click(screen.getByRole('checkbox', { name: 'Zaznacz fakturę FV/1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Zapytaj o zaznaczone' }));
  expect(askKlarvido).toHaveBeenLastCalledWith('tenant-1', 'Zaznaczone faktury (1)', {
    kind: ComponentKind.INVOICE_SELECTION,
    invoiceIds: ['invoice-1'],
  });
  fireEvent.click(screen.getByRole('button', { name: 'Zakupy' }));
  expect(screen.getByTestId('location')).toHaveTextContent('direction=PURCHASE');
});

it('keeps view-only users away from import, exports and category editing', async () => {
  mockPermissions = new Set();
  wrapper(<InvoiceList />);
  await screen.findByText('FV/1');
  expect(screen.queryByRole('button', { name: 'Pobierz faktury z KSeF' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Eksport CSV' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Zapytaj Klarvido' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Filtruj kategorię' }));
  expect(await screen.findByRole('combobox', { name: 'Kategoria' })).toBeInTheDocument(); // Filter remains available.
});

it('renders details and passes only the ID to AI', async () => {
  const details = {
    request: { query: invoiceQuery, variables: { tenantId: 'tenant-1', id: 'invoice-1' } },
    result: {
      data: {
        invoice: {
          ...invoice,
          permanentStorageDate: '2026-01-02T00:00:00Z',
          createdAt: '2026-01-03T00:00:00Z',
          correctedKsefNumbers: ['original-ksef'],
          lines: [
            {
              position: 1,
              description: 'Service',
              quantity: '2',
              unit: 'szt.',
              unitPrice: '50',
              net: '100',
              vatRate: '23',
            },
          ],
        },
      },
    },
  };
  wrapper(
    <Routes>
      <Route path="/invoices/:id" element={<InvoiceDetails />} />
    </Routes>,
    [setup, details],
    '/invoices/invoice-1'
  );
  await screen.findByText('Service');
  expect(screen.getByText('original-ksef')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Zapytaj Klarvido' }));
  expect(askKlarvido).toHaveBeenCalledWith('tenant-1', 'FV/1', {
    kind: ComponentKind.INVOICE_DETAILS,
    invoiceIds: ['invoice-1'],
  });
});

it('sorts through column headers, resets pagination and passes ordering to the backend', async () => {
  const variables = jest.fn(() => true);
  wrapper(
    <InvoiceList />,
    [
      setup,
      {
        request: { query: invoicesQuery, variables },
        result: list.result,
        maxUsageCount: Infinity,
      },
    ],
    '/?page=3'
  );
  await screen.findByText('FV/1');
  const date = screen.getByRole('button', { name: 'Data: sortuj rosnąco' });
  expect(date.closest('th')).toHaveAttribute('aria-sort', 'descending');
  fireEvent.click(date);
  await waitFor(() =>
    expect(variables).toHaveBeenLastCalledWith({ tenantId: 'tenant-1', filters: { sort: 'issue_date' }, page: 1 })
  );
  expect(screen.getByTestId('location')).toHaveTextContent('?sort=issue_date');
  expect((await screen.findByRole('button', { name: 'Data: sortuj malejąco' })).closest('th')).toHaveAttribute(
    'aria-sort',
    'ascending'
  );
  fireEvent.click(screen.getByRole('button', { name: 'Data: sortuj malejąco' }));
  await waitFor(() =>
    expect(variables).toHaveBeenLastCalledWith({ tenantId: 'tenant-1', filters: { sort: '-issue_date' }, page: 1 })
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Brutto: sortuj rosnąco' }));
  await waitFor(() =>
    expect(variables).toHaveBeenLastCalledWith({ tenantId: 'tenant-1', filters: { sort: 'gross' }, page: 1 })
  );
});

it('shows removable filters and clears them without discarding sorting', async () => {
  const variables = jest.fn(() => true);
  wrapper(
    <InvoiceList />,
    [
      setup,
      {
        request: { query: invoicesQuery, variables },
        result: list.result,
        maxUsageCount: Infinity,
      },
    ],
    '/?direction=SALE&category=uncategorized&dateFrom=2026-01-01&sort=-gross&page=3'
  );
  await screen.findByText('FV/1');
  expect(screen.getByRole('button', { name: 'Sprzedaż' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('button', { name: 'Usuń filtr: Kategoria' })).toHaveTextContent('Bez kategorii');
  fireEvent.click(screen.getByRole('button', { name: 'Usuń filtr: Typ' }));
  expect(screen.getByTestId('location')).not.toHaveTextContent('direction=');
  expect(screen.getByTestId('location')).not.toHaveTextContent('page=');
  fireEvent.click(screen.getByRole('button', { name: 'Wyczyść filtry' }));
  expect(screen.getByTestId('location')).toHaveTextContent('?sort=-gross');
  expect(screen.queryByRole('button', { name: /Usuń filtr:/ })).not.toBeInTheDocument();
  await waitFor(() =>
    expect(variables).toHaveBeenLastCalledWith({ tenantId: 'tenant-1', filters: { sort: '-gross' }, page: 1 })
  );
});

it('keeps the category filter available when it returns no rows', async () => {
  wrapper(
    <InvoiceList />,
    [
      setup,
      {
        request: {
          query: invoicesQuery,
          variables: { tenantId: 'tenant-1', filters: { category: 'uncategorized', sort: 'number' }, page: 1 },
        },
        result: { data: { invoices: { totalCount: 0, items: [] } } },
      },
    ],
    '/?category=uncategorized&sort=number'
  );
  await screen.findByText('Brak faktur pasujących do filtrów.');
  fireEvent.click(screen.getByRole('button', { name: 'Filtruj kategorię' }));
  expect(await screen.findByRole('combobox', { name: 'Kategoria' })).toHaveValue('uncategorized');
});
