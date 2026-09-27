import { MockedProvider } from '@apollo/client/testing/react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IntlProvider } from 'react-intl';

import { klarvidoOverviewQuery } from '../klarvidoOverview.graphql';
import { KlarvidoWorkspace } from '../klarvidoWorkspace.component';

const tenantId = 'VGVuYW50VHlwZTox';
const value = (amount: string, unit = 'PLN') => ({ __typename: 'AnalyticalValueType', value: amount, unit });
const party = {
  __typename: 'PartyType',
  id: 'customer-1',
  name: 'MebloDom',
  taxIdentifier: '1234567890',
  amount: value('530000.00'),
  share: value('43.59', '%'),
  percentageChange: value('-4.20', '%'),
  invoiceCount: value('12', 'count'),
  trend: [{ __typename: 'PartyTrendPointType', label: 'Czerwiec 2026', amount: value('90000.00') }],
};
const invoice = {
  __typename: 'InvoiceType',
  id: 'invoice-1',
  documentNumber: 'FV/2026/001',
  invoiceType: 'SALES',
  status: 'ISSUED',
  issueDate: '2026-06-20',
  dueDate: '2026-07-04',
  counterpartyName: 'MebloDom',
  counterpartyTaxIdentifier: '1234567890',
  currency: 'PLN',
  netAmount: '90000.00',
  taxAmount: '20700.00',
  grossAmount: '110700.00',
  categories: ['Sprzedaż mebli'],
  sourceSystem: 'MOCK',
  sourceExternalId: 'invoice-1',
  qualityStatus: 'VALID',
};

const overview = {
  __typename: 'KlarvidoOverviewType',
  preset: 'half_year',
  period: { __typename: 'PeriodType', startDate: '2026-01-01', endDate: '2026-06-30' },
  comparisonPeriod: null,
  company: { __typename: 'CompanyType', legalName: 'Meble Kowalski Sp. z o.o.', taxIdentifier: '9876543210', regon: '123456789', pkdCode: '31.09.Z', countryCode: 'PL', defaultCurrency: 'PLN' },
  financialSummary: {
    __typename: 'FinancialSummaryType',
    revenue: { ...value('1215800.00'), kind: 'fact', calculationVersion: 'revenue:v1', calculatedAt: '2026-07-01T08:00:00Z', quality: { __typename: 'DataQualityType', status: 'VALID', score: 1, limitations: [] }, revenueSources: [{ __typename: 'SourceReferenceType', sourceSystem: 'MOCK', externalId: 'invoice-1', sourceRecordId: 'source-1' }] },
    costs: { ...value('614640.00'), kind: 'fact', calculationVersion: 'costs:v1', calculatedAt: '2026-07-01T08:00:00Z', quality: { __typename: 'DataQualityType', status: 'VALID', score: 1, limitations: [] } },
    preTaxResult: { ...value('601160.00'), kind: 'fact', calculationVersion: 'pre-tax-result:v1', calculatedAt: '2026-07-01T08:00:00Z', quality: { __typename: 'DataQualityType', status: 'VALID', score: 1, limitations: [] } },
    grossMargin: { ...value('49.45', '%'), kind: 'fact', calculationVersion: 'gross-margin:v1', calculatedAt: '2026-07-01T08:00:00Z', quality: { __typename: 'DataQualityType', status: 'VALID', score: 1, limitations: [] } },
    revenueChange: null, costsChange: null, preTaxResultChange: null, grossMarginChange: null,
  },
  monthlySummaries: [{ __typename: 'MonthlySummaryType', label: 'Czerwiec 2026', period: { __typename: 'PeriodType', startDate: '2026-06-01', endDate: '2026-06-30' }, summary: { __typename: 'FinancialSummaryType', revenue: value('201900.00'), costs: value('123590.00'), preTaxResult: value('78310.00'), grossMargin: value('38.79', '%') } }],
  customers: { __typename: 'PortfolioType', total: value('1215800.00'), activeCount: value('12', 'count'), topThreeConcentration: value('67.00', '%'), largestParty: party, parties: [party] },
  suppliers: { __typename: 'PortfolioType', total: value('614640.00'), activeCount: value('11', 'count'), topThreeConcentration: value('71.00', '%'), largestParty: { ...party, id: 'supplier-1', name: 'DrewnoPol' }, parties: [{ ...party, id: 'supplier-1', name: 'DrewnoPol' }] },
  costStructure: { __typename: 'CostStructureType', total: value('614640.00'), categories: [{ __typename: 'CategoryType', code: 'materials', name: 'Materiały', amount: value('320000.00'), share: value('52.06', '%') }] },
  invoices: [invoice],
  readiness: [{ __typename: 'ReadinessType', analysis: 'customer_trend', status: 'READY', score: 1, limitations: [], policyVersion: 'data-readiness:v1', checkedAt: '2026-07-01T08:00:00Z', metrics: [] }],
};

const mock = {
  request: { query: klarvidoOverviewQuery, variables: { tenantId, preset: 'half_year' } },
  result: { data: { klarvidoOverview: overview } },
};

const renderWorkspace = (activeRoute: 'today' | 'analysis' | 'invoices' = 'today') => render(
  <MockedProvider mocks={[mock]}>
    <IntlProvider locale="en">
      <KlarvidoWorkspace activeRoute={activeRoute} tenantId={tenantId} />
    </IntlProvider>
  </MockedProvider>,
);

describe('KlarvidoWorkspace (KLV-008)', () => {
  it('shows an explicit empty state when no tenant is selected', () => {
    render(
      <MockedProvider>
        <IntlProvider locale="en">
          <KlarvidoWorkspace activeRoute="today" />
        </IntlProvider>
      </MockedProvider>,
    );

    expect(screen.getByText('Wybierz firmę, aby zobaczyć jej dane.')).toBeInTheDocument();
  });

  it('shows a retryable error state when GraphQL fails', async () => {
    render(
      <MockedProvider
        mocks={[
          {
            request: mock.request,
            error: new Error('Backend unavailable'),
          },
        ]}
      >
        <IntlProvider locale="en">
          <KlarvidoWorkspace activeRoute="today" tenantId={tenantId} />
        </IntlProvider>
      </MockedProvider>,
    );

    expect(await screen.findByText('Nie udało się pobrać danych')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Spróbuj ponownie' })).toBeInTheDocument();
  });

  it('renders canonical KPI and readiness returned by GraphQL', async () => {
    renderWorkspace();

    expect(await screen.findByText('Dzień dobry. Oto sytuacja firmy.')).toBeInTheDocument();
    expect(screen.getByText('1 215 800 zł')).toBeInTheDocument();
    expect(screen.getByText('Gotowość danych')).toBeInTheDocument();
    expect(screen.getByText('READY')).toBeInTheDocument();
  });

  it('filters invoices and opens their source drill-down', async () => {
    renderWorkspace('invoices');

    expect(await screen.findByText('FV/2026/001')).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText('Numer lub kontrahent'), 'brak');
    expect(screen.getByText('Brak danych pasujących do filtrów.')).toBeInTheDocument();
    await userEvent.clear(screen.getByPlaceholderText('Numer lub kontrahent'));
    await userEvent.click(await screen.findByText('FV/2026/001'));
    expect(await screen.findByText('MOCK · invoice-1')).toBeInTheDocument();
    expect(screen.getByText('VALID')).toBeInTheDocument();
  });

  it('switches between company and portfolio analysis views', async () => {
    renderWorkspace('analysis');

    expect(await screen.findByText('Dane firmy')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Klienci' }));

    expect(await screen.findByText('Portfel klientów')).toBeInTheDocument();
    expect(screen.getByText('MebloDom')).toBeInTheDocument();
  });

  it('filters invoices by document type', async () => {
    renderWorkspace('invoices');

    expect(await screen.findByText('FV/2026/001')).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole('combobox'), 'PURCHASE');

    expect(screen.getByText('Brak danych pasujących do filtrów.')).toBeInTheDocument();
    expect(screen.getByText('0 z 1 faktur')).toBeInTheDocument();
  });

  it('exports the currently visible invoices as CSV', async () => {
    const createObjectURL = jest.fn(() => 'blob:klarvido');
    const revokeObjectURL = jest.fn();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
    jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    renderWorkspace('invoices');

    await userEvent.click(await screen.findByRole('button', { name: 'CSV' }));

    await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:klarvido');
  });
});
