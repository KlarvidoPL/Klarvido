import { useQuery } from '@apollo/client/react';
import { Button } from '@sb/webapp-core/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@sb/webapp-core/components/ui/dialog';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Skeleton } from '@sb/webapp-core/components/ui/skeleton';
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table';
import {
  ArrowDown,
  ArrowUp,
  Building2,
  ChevronDown,
  Download,
  FileSearch,
  Filter,
  RefreshCw,
  Search,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { useIntl } from 'react-intl';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { KlarvidoProductRoute } from '../klarvidoShell/klarvidoShell.types';
import { klarvidoOverviewQuery } from './klarvidoOverview.graphql';
import './klarvidoWorkspace.css';

type Value = { value?: string | null; unit: string };
type TrendPoint = { label: string; amount?: Value | null };
type Party = {
  id: string;
  name: string;
  taxIdentifier: string;
  amount: Value;
  share: Value;
  percentageChange?: Value | null;
  invoiceCount: Value;
  trend: TrendPoint[];
};
type Portfolio = {
  total: Value;
  activeCount: Value;
  topThreeConcentration: Value;
  largestParty: Party;
  parties: Party[];
};
type Invoice = {
  id: string;
  documentNumber: string;
  invoiceType: string;
  status: string;
  issueDate: string;
  dueDate?: string | null;
  counterpartyName: string;
  counterpartyTaxIdentifier: string;
  currency: string;
  netAmount: string;
  taxAmount: string;
  grossAmount: string;
  categories: string[];
  sourceSystem: string;
  sourceExternalId: string;
  qualityStatus: string;
};
type Overview = {
  period: { startDate: string; endDate: string };
  company?: {
    legalName: string;
    taxIdentifier: string;
    regon: string;
    pkdCode: string;
    countryCode: string;
    defaultCurrency: string;
  } | null;
  financialSummary: {
    revenue: Value;
    costs: Value;
    preTaxResult: Value;
    grossMargin: Value;
    revenueChange?: Value | null;
    costsChange?: Value | null;
    preTaxResultChange?: Value | null;
    grossMarginChange?: Value | null;
  };
  monthlySummaries: Array<{
    label: string;
    summary: { revenue: Value; costs: Value; preTaxResult: Value; grossMargin: Value };
  }>;
  customers: Portfolio;
  suppliers: Portfolio;
  costStructure: { total: Value; categories: Array<{ code?: string | null; name: string; amount: Value; share: Value }> };
  invoices: Invoice[];
  readiness: Array<{ analysis: string; status: string; score: number; limitations: string[] }>;
};

type AnalysisSection = 'company' | 'clients' | 'suppliers' | 'costs';
type Props = { activeRoute: KlarvidoProductRoute; tenantId?: string };
const chartColors = ['#0B2545', '#F59E0B', '#13A66A', '#4F7CAC', '#E34D59', '#8494A8'];

const numeric = (value?: string | null) => Number(value || 0);

export const KlarvidoWorkspace = ({ activeRoute, tenantId }: Props) => {
  const intl = useIntl();
  const [preset, setPreset] = useState('half_year');
  const [analysisSection, setAnalysisSection] = useState<AnalysisSection>('company');
  const { data, loading, error, refetch } = useQuery(klarvidoOverviewQuery, {
    variables: { tenantId: tenantId || '', preset },
    skip: !tenantId,
  });
  const overview = data?.klarvidoOverview as Overview | null | undefined;

  const t = (id: string, defaultMessage: string) => intl.formatMessage({ id, defaultMessage });

  if (!tenantId) {
    return <WorkspaceState title={t('klarvido.empty.tenant', 'Wybierz firmę, aby zobaczyć jej dane.')} />;
  }
  if (loading) return <LoadingState />;
  if (error) {
    return (
      <WorkspaceState
        title={t('klarvido.error.title', 'Nie udało się pobrać danych')}
        description={t('klarvido.error.description', 'Sprawdź połączenie z backendem i spróbuj ponownie.')}
        action={<Button onClick={() => refetch()}><RefreshCw className="h-4 w-4" />{t('klarvido.error.retry', 'Spróbuj ponownie')}</Button>}
      />
    );
  }
  if (!overview) {
    return (
      <WorkspaceState
        title={t('klarvido.empty.data', 'Brak danych firmy')}
        description={t('klarvido.empty.dataDescription', 'Załaduj dane demonstracyjne lub połącz źródło danych.')}
      />
    );
  }

  const periodControl = <PeriodControl value={preset} onChange={setPreset} />;
  if (activeRoute === 'today') return <StartView overview={overview} periodControl={periodControl} />;
  if (activeRoute === 'analysis') {
    return (
      <AnalysisView
        overview={overview}
        periodControl={periodControl}
        section={analysisSection}
        onSectionChange={setAnalysisSection}
      />
    );
  }
  if (activeRoute === 'invoices') return <InvoicesView invoices={overview.invoices} />;
  if (activeRoute === 'sources') return <SourcesView overview={overview} />;

  const future = {
    decisions: [t('klarvido.future.decisions', 'Decyzje'), t('klarvido.future.decisionsDescription', 'Pakiety decyzyjne pojawią się w kolejnym etapie.')],
    actions: [t('klarvido.future.actions', 'Działania'), t('klarvido.future.actionsDescription', 'Historia działań zostanie podłączona po Decision Engine.')],
    settings: [t('klarvido.future.settings', 'Ustawienia'), t('klarvido.future.settingsDescription', 'Ustawienia produktu są przygotowywane jako natywny moduł React.')],
  }[activeRoute];
  return <WorkspaceState title={future?.[0] || ''} description={future?.[1]} />;
};

const PeriodControl = ({ value, onChange }: { value: string; onChange: (value: string) => void }) => {
  const intl = useIntl();
  return (
    <label className="klarvido-period-control">
      <span>{intl.formatMessage({ id: 'klarvido.period.label', defaultMessage: 'Okres' })}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="latest_month">{intl.formatMessage({ id: 'klarvido.period.latest', defaultMessage: 'Ostatni miesiąc' })}</option>
        <option value="last_quarter">{intl.formatMessage({ id: 'klarvido.period.quarter', defaultMessage: 'Ostatnie 3 miesiące' })}</option>
        <option value="half_year">{intl.formatMessage({ id: 'klarvido.period.halfYear', defaultMessage: 'Ostatnie 6 miesięcy' })}</option>
        <option value="year_to_date">{intl.formatMessage({ id: 'klarvido.period.ytd', defaultMessage: 'Od początku roku' })}</option>
      </select>
      <ChevronDown className="h-4 w-4" />
    </label>
  );
};

const StartView = ({ overview, periodControl }: { overview: Overview; periodControl: React.ReactNode }) => {
  const intl = useIntl();
  const metrics = overview.financialSummary;
  return (
    <Page>
      <PageHeader
        eyebrow={intl.formatMessage({ id: 'klarvido.start.eyebrow', defaultMessage: 'Twój pulpit' })}
        title={intl.formatMessage({ id: 'klarvido.start.title', defaultMessage: 'Dzień dobry. Oto sytuacja firmy.' })}
        description={intl.formatMessage({ id: 'klarvido.start.description', defaultMessage: 'Najważniejsze liczby i źródła w jednym miejscu.' })}
        leading={periodControl}
      />
      <KpiGrid metrics={metrics} />
      <div className="klarvido-grid-2">
        <Panel title={intl.formatMessage({ id: 'klarvido.start.trend', defaultMessage: 'Sprzedaż i koszty' })}>
          <FinancialChart data={overview.monthlySummaries} />
        </Panel>
        <Panel title={intl.formatMessage({ id: 'klarvido.start.readiness', defaultMessage: 'Gotowość danych' })}>
          <ReadinessList items={overview.readiness} />
        </Panel>
      </div>
      <div className="klarvido-grid-2">
        <Panel title={intl.formatMessage({ id: 'klarvido.start.customers', defaultMessage: 'Najwięksi klienci' })}>
          <CompactRanking parties={overview.customers.parties.slice(0, 5)} />
        </Panel>
        <Panel title={intl.formatMessage({ id: 'klarvido.start.suppliers', defaultMessage: 'Najwięksi dostawcy' })}>
          <CompactRanking parties={overview.suppliers.parties.slice(0, 5)} />
        </Panel>
      </div>
    </Page>
  );
};

const AnalysisView = ({ overview, periodControl, section, onSectionChange }: {
  overview: Overview; periodControl: React.ReactNode; section: AnalysisSection; onSectionChange: (section: AnalysisSection) => void;
}) => {
  const intl = useIntl();
  const tabs: Array<[AnalysisSection, string]> = [
    ['company', intl.formatMessage({ id: 'klarvido.analysis.company', defaultMessage: 'Firma' })],
    ['clients', intl.formatMessage({ id: 'klarvido.analysis.clients', defaultMessage: 'Klienci' })],
    ['suppliers', intl.formatMessage({ id: 'klarvido.analysis.suppliers', defaultMessage: 'Dostawcy' })],
    ['costs', intl.formatMessage({ id: 'klarvido.analysis.costs', defaultMessage: 'Koszty' })],
  ];
  return (
    <Page>
      <PageHeader
        title={intl.formatMessage({ id: 'klarvido.analysis.title', defaultMessage: 'Analiza firmy' })}
        description={intl.formatMessage({ id: 'klarvido.analysis.description', defaultMessage: 'Najpierw interpretacja, potem dane.' })}
        leading={periodControl}
      />
      <div className="klarvido-analysis-tabs" role="tablist">
        {tabs.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={section === key} onClick={() => onSectionChange(key)}>{label}</button>)}
      </div>
      {section === 'company' && <CompanyView overview={overview} />}
      {section === 'clients' && <PartiesView kind="customers" portfolio={overview.customers} />}
      {section === 'suppliers' && <PartiesView kind="suppliers" portfolio={overview.suppliers} />}
      {section === 'costs' && <CostsView overview={overview} />}
    </Page>
  );
};

const CompanyView = ({ overview }: { overview: Overview }) => {
  const intl = useIntl();
  return <><KpiGrid metrics={overview.financialSummary} /><div className="klarvido-grid-2"><Panel title={intl.formatMessage({ id: 'klarvido.company.chart', defaultMessage: 'Sprzedaż i koszty' })}><FinancialChart data={overview.monthlySummaries} /></Panel><Panel title={intl.formatMessage({ id: 'klarvido.company.profile', defaultMessage: 'Dane firmy' })}><dl className="klarvido-company-details"><div><dt>Nazwa</dt><dd>{overview.company?.legalName || '—'}</dd></div><div><dt>NIP</dt><dd>{overview.company?.taxIdentifier || '—'}</dd></div><div><dt>REGON</dt><dd>{overview.company?.regon || '—'}</dd></div><div><dt>PKD</dt><dd>{overview.company?.pkdCode || '—'}</dd></div></dl></Panel></div></>;
};

const KpiGrid = ({ metrics }: { metrics: Overview['financialSummary'] }) => {
  const intl = useIntl();
  return <div className="klarvido-kpi-grid"><KpiCard label={intl.formatMessage({ id: 'klarvido.kpi.revenue', defaultMessage: 'Przychód' })} value={metrics.revenue} change={metrics.revenueChange} tone="green" /><KpiCard label={intl.formatMessage({ id: 'klarvido.kpi.costs', defaultMessage: 'Koszty' })} value={metrics.costs} change={metrics.costsChange} tone="red" /><KpiCard label={intl.formatMessage({ id: 'klarvido.kpi.result', defaultMessage: 'Wynik przed podatkiem' })} value={metrics.preTaxResult} change={metrics.preTaxResultChange} tone="navy" /><KpiCard label={intl.formatMessage({ id: 'klarvido.kpi.margin', defaultMessage: 'Marża brutto' })} value={metrics.grossMargin} change={metrics.grossMarginChange} tone="amber" /></div>;
};

const KpiCard = ({ label, value, change, tone }: { label: string; value: Value; change?: Value | null; tone: string }) => {
  const delta = numeric(change?.value);
  return <article className={`klarvido-kpi klarvido-kpi--${tone}`}><span>{label}</span><strong>{formatValue(value)}</strong><small className={delta < 0 ? 'down' : 'up'}>{change?.value ? <>{delta < 0 ? <ArrowDown /> : <ArrowUp />}{formatValue(change)}</> : 'Brak okresu porównawczego'}</small></article>;
};

const FinancialChart = ({ data }: { data: Overview['monthlySummaries'] }) => {
  const rows = data.map((item) => ({ name: shortMonth(item.label), revenue: numeric(item.summary.revenue.value), costs: numeric(item.summary.costs.value) }));
  return <div className="klarvido-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows} barGap={8}><CartesianGrid vertical={false} stroke="#E7ECF2" /><XAxis dataKey="name" tickLine={false} axisLine={false} /><YAxis tickFormatter={compactMoney} tickLine={false} axisLine={false} width={54} /><Tooltip formatter={(value) => money(Number(value))} /><Bar dataKey="revenue" name="Przychód" fill="#0B2545" radius={[3, 3, 0, 0]} /><Bar dataKey="costs" name="Koszty" fill="#F59E0B" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div>;
};

const PartiesView = ({ portfolio, kind }: { portfolio: Portfolio; kind: 'customers' | 'suppliers' }) => {
  const intl = useIntl();
  const isCustomers = kind === 'customers';
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Party | null>(null);
  const filtered = useMemo(() => portfolio.parties.filter((party) => party.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())), [portfolio.parties, search]);
  const columns = useMemo<ColumnDef<Party>[]>(() => [
    { accessorKey: 'name', header: isCustomers ? 'Klient' : 'Dostawca', cell: ({ row }) => <button className="klarvido-table-link" onClick={() => setSelected(row.original)}>{row.original.name}<small>{row.original.taxIdentifier}</small></button> },
    { id: 'amount', accessorFn: (row) => numeric(row.amount.value), header: 'Wartość', cell: ({ row }) => money(numeric(row.original.amount.value)) },
    { id: 'change', accessorFn: (row) => numeric(row.percentageChange?.value), header: 'Zmiana', cell: ({ row }) => <Change value={row.original.percentageChange} /> },
    { id: 'share', accessorFn: (row) => numeric(row.share.value), header: 'Udział', cell: ({ row }) => percent(numeric(row.original.share.value)) },
    { id: 'invoices', accessorFn: (row) => numeric(row.invoiceCount.value), header: 'Faktury' },
  ], [isCustomers]);
  return <><div className="klarvido-kpi-grid klarvido-kpi-grid--3"><KpiCard label={isCustomers ? 'Sprzedaż' : 'Zakupy'} value={portfolio.total} tone="navy" /><KpiCard label={isCustomers ? 'Aktywni klienci' : 'Aktywni dostawcy'} value={portfolio.activeCount} tone="green" /><KpiCard label="Koncentracja TOP 3" value={portfolio.topThreeConcentration} tone="amber" /></div><Panel title={isCustomers ? intl.formatMessage({ id: 'klarvido.clients.table', defaultMessage: 'Portfel klientów' }) : intl.formatMessage({ id: 'klarvido.suppliers.table', defaultMessage: 'Portfel dostawców' })} action={<SearchField value={search} onChange={setSearch} placeholder={isCustomers ? 'Nazwa klienta' : 'Nazwa dostawcy'} />}><DataTable columns={columns} data={filtered} /></Panel><PartyDialog party={selected} onClose={() => setSelected(null)} kind={kind} /></>;
};

const CostsView = ({ overview }: { overview: Overview }) => {
  const intl = useIntl();
  const rows = overview.costStructure.categories.map((category) => ({ name: category.name, value: numeric(category.amount.value) }));
  return <><div className="klarvido-grid-2"><Panel title={intl.formatMessage({ id: 'klarvido.costs.structure', defaultMessage: 'Struktura kosztów' })}><div className="klarvido-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={rows} dataKey="value" nameKey="name" innerRadius="52%" outerRadius="78%" paddingAngle={2}>{rows.map((_, index) => <Cell key={index} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip formatter={(value) => money(Number(value))} /></PieChart></ResponsiveContainer></div></Panel><Panel title={intl.formatMessage({ id: 'klarvido.costs.categories', defaultMessage: 'Kategorie kosztów' })}><CompactCategories categories={overview.costStructure.categories} /></Panel></div><Panel title={intl.formatMessage({ id: 'klarvido.costs.sources', defaultMessage: 'Faktury kosztowe' })}><InvoiceMiniTable invoices={overview.invoices.filter((invoice) => invoice.invoiceType === 'PURCHASE')} /></Panel></>;
};

const InvoicesView = ({ invoices }: { invoices: Invoice[] }) => {
  const intl = useIntl();
  const [search, setSearch] = useState('');
  const [type, setType] = useState('ALL');
  const [selected, setSelected] = useState<Invoice | null>(null);
  const filtered = useMemo(() => invoices.filter((invoice) => (type === 'ALL' || invoice.invoiceType === type) && `${invoice.documentNumber} ${invoice.counterpartyName}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())), [invoices, search, type]);
  const columns = useMemo<ColumnDef<Invoice>[]>(() => [
    { accessorKey: 'documentNumber', header: 'Numer', cell: ({ row }) => <button className="klarvido-table-link" onClick={() => setSelected(row.original)}>{row.original.documentNumber}<small>{row.original.sourceSystem}</small></button> },
    { accessorKey: 'counterpartyName', header: 'Kontrahent' },
    { accessorKey: 'invoiceType', header: 'Typ', cell: ({ row }) => <StatusPill value={row.original.invoiceType === 'SALES' ? 'Sprzedaż' : 'Zakup'} tone={row.original.invoiceType === 'SALES' ? 'green' : 'blue'} /> },
    { accessorKey: 'issueDate', header: 'Data' },
    { id: 'net', accessorFn: (row) => numeric(row.netAmount), header: 'Netto', cell: ({ row }) => money(numeric(row.original.netAmount)) },
    { id: 'gross', accessorFn: (row) => numeric(row.grossAmount), header: 'Brutto', cell: ({ row }) => money(numeric(row.original.grossAmount)) },
    { id: 'categories', header: 'Kategoria', cell: ({ row }) => row.original.categories.join(', ') },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusPill value={row.original.status === 'ISSUED' ? 'Wystawiona' : row.original.status} tone="blue" /> },
  ], []);
  return <Page><PageHeader title={intl.formatMessage({ id: 'klarvido.invoices.title', defaultMessage: 'Faktury' })} description={intl.formatMessage({ id: 'klarvido.invoices.description', defaultMessage: 'Wszystkie dokumenty źródłowe wykorzystywane w analizach.' })} /><Panel title={intl.formatMessage({ id: 'klarvido.invoices.list', defaultMessage: 'Dokumenty' })} action={<div className="klarvido-table-actions"><SearchField value={search} onChange={setSearch} placeholder="Numer lub kontrahent" /><label className="klarvido-filter"><Filter /><select value={type} onChange={(event) => setType(event.target.value)}><option value="ALL">Wszystkie typy</option><option value="SALES">Sprzedaż</option><option value="PURCHASE">Zakup</option></select></label><Button variant="outline" onClick={() => exportCsv(filtered)}><Download className="h-4 w-4" />CSV</Button></div>}><div className="klarvido-result-count">{filtered.length} z {invoices.length} faktur</div><DataTable columns={columns} data={filtered} /></Panel><InvoiceDialog invoice={selected} onClose={() => setSelected(null)} /></Page>;
};

const SourcesView = ({ overview }: { overview: Overview }) => {
  const intl = useIntl();
  return <Page><PageHeader title={intl.formatMessage({ id: 'klarvido.sources.title', defaultMessage: 'Źródła danych' })} description={intl.formatMessage({ id: 'klarvido.sources.description', defaultMessage: 'Zawsze wiesz, na czym opierają się analizy Klarvido.' })} /><div className="klarvido-source-grid"><Panel title="Dane demonstracyjne"><div className="klarvido-source-heading"><span>DEMO</span><div><b>MockDataAdapter</b><small>Aktywne źródło</small></div></div><p>Faktury, kontrahenci, pozycje oraz metadane źródłowe.</p><StatusPill value={`${overview.invoices.length} dokumentów`} tone="green" /></Panel><Panel title="Krajowy System e-Faktur"><div className="klarvido-source-heading"><span>KSeF</span><div><b>KSeF</b><small>Niepołączono</small></div></div><p>Adapter jest przygotowany jako kolejna implementacja wspólnego kontraktu.</p></Panel><Panel title="Data Readiness"><ReadinessList items={overview.readiness} /></Panel></div></Page>;
};

function DataTable<T>({ columns, data }: { columns: ColumnDef<T>[]; data: T[] }) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const table = useReactTable({ data, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  return <div className="klarvido-table-wrap"><table className="klarvido-data-table"><thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id}><button type="button" disabled={!header.column.getCanSort()} onClick={header.column.getToggleSortingHandler()}>{flexRender(header.column.columnDef.header, header.getContext())}{header.column.getIsSorted() === 'asc' ? <ArrowUp /> : header.column.getIsSorted() === 'desc' ? <ArrowDown /> : null}</button></th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.length ? table.getRowModel().rows.map((row) => <tr key={row.id}>{row.getVisibleCells().map((cell) => <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>) : <tr><td colSpan={columns.length} className="klarvido-empty-row">Brak danych pasujących do filtrów.</td></tr>}</tbody></table></div>;
}

const PartyDialog = ({ party, onClose, kind }: { party: Party | null; onClose: () => void; kind: string }) => <Dialog open={Boolean(party)} onOpenChange={(open) => !open && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{party?.name}</DialogTitle><DialogDescription>{kind === 'customers' ? 'Klient' : 'Dostawca'} · NIP {party?.taxIdentifier || '—'}</DialogDescription></DialogHeader>{party && <><div className="klarvido-dialog-kpis"><KpiCard label="Wartość" value={party.amount} change={party.percentageChange} tone="navy" /><KpiCard label="Udział" value={party.share} tone="amber" /><KpiCard label="Faktury" value={party.invoiceCount} tone="green" /></div><div className="klarvido-chart klarvido-chart--dialog"><ResponsiveContainer width="100%" height="100%"><LineChart data={party.trend.map((point) => ({ name: shortMonth(point.label), value: numeric(point.amount?.value) }))}><CartesianGrid vertical={false} stroke="#E7ECF2" /><XAxis dataKey="name" /><YAxis tickFormatter={compactMoney} /><Tooltip formatter={(value) => money(Number(value))} /><Line type="monotone" dataKey="value" stroke="#0B2545" strokeWidth={3} dot={{ fill: '#F59E0B' }} /></LineChart></ResponsiveContainer></div></>}</DialogContent></Dialog>;

const InvoiceDialog = ({ invoice, onClose }: { invoice: Invoice | null; onClose: () => void }) => <Dialog open={Boolean(invoice)} onOpenChange={(open) => !open && onClose()}><DialogContent><DialogHeader><DialogTitle>{invoice?.documentNumber}</DialogTitle><DialogDescription>{invoice?.counterpartyName}</DialogDescription></DialogHeader>{invoice && <dl className="klarvido-invoice-details"><div><dt>Data wystawienia</dt><dd>{invoice.issueDate}</dd></div><div><dt>Termin płatności</dt><dd>{invoice.dueDate || '—'}</dd></div><div><dt>Netto</dt><dd>{money(numeric(invoice.netAmount))}</dd></div><div><dt>VAT</dt><dd>{money(numeric(invoice.taxAmount))}</dd></div><div><dt>Brutto</dt><dd>{money(numeric(invoice.grossAmount))}</dd></div><div><dt>Źródło</dt><dd>{invoice.sourceSystem} · {invoice.sourceExternalId}</dd></div><div><dt>Jakość</dt><dd>{invoice.qualityStatus}</dd></div><div><dt>Kategorie</dt><dd>{invoice.categories.join(', ')}</dd></div></dl>}</DialogContent></Dialog>;

const Panel = ({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) => <section className="klarvido-panel"><header><h2>{title}</h2>{action}</header>{children}</section>;
const Page = ({ children }: { children: React.ReactNode }) => <div className="klarvido-page">{children}</div>;
const PageHeader = ({ eyebrow, title, description, leading }: { eyebrow?: string; title: string; description?: string; leading?: React.ReactNode }) => <header className="klarvido-page-header"><div className="klarvido-page-leading">{leading}</div><div>{eyebrow && <span>{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div><div /></header>;
const SearchField = ({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) => <label className="klarvido-search"><Search /><Input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>;
const StatusPill = ({ value, tone }: { value: string; tone: string }) => <span className={`klarvido-pill klarvido-pill--${tone}`}>{value}</span>;
const Change = ({ value }: { value?: Value | null }) => value?.value ? <span className={numeric(value.value) < 0 ? 'klarvido-change down' : 'klarvido-change up'}>{formatValue(value)}</span> : <span>—</span>;
const CompactRanking = ({ parties }: { parties: Party[] }) => <div className="klarvido-ranking">{parties.map((party, index) => <div key={party.id}><span>{index + 1}</span><b>{party.name}</b><small>{percent(numeric(party.share.value))}</small><strong>{money(numeric(party.amount.value))}</strong></div>)}</div>;
const CompactCategories = ({ categories }: { categories: Overview['costStructure']['categories'] }) => <div className="klarvido-ranking">{categories.map((category, index) => <div key={category.code || category.name}><span style={{ background: chartColors[index % chartColors.length] }} /><b>{category.name}</b><small>{percent(numeric(category.share.value))}</small><strong>{money(numeric(category.amount.value))}</strong></div>)}</div>;
const InvoiceMiniTable = ({ invoices }: { invoices: Invoice[] }) => <div className="klarvido-mini-table">{invoices.slice(0, 8).map((invoice) => <div key={invoice.id}><b>{invoice.documentNumber}</b><span>{invoice.counterpartyName}</span><small>{invoice.issueDate}</small><strong>{money(numeric(invoice.netAmount))}</strong></div>)}</div>;
const ReadinessList = ({ items }: { items: Overview['readiness'] }) => <div className="klarvido-readiness">{items.map((item) => <div key={item.analysis}><span className={`klarvido-readiness-dot klarvido-readiness-dot--${item.status.toLowerCase()}`} /><b>{readinessName(item.analysis)}</b><small>{Math.round(item.score * 100)}%</small><StatusPill value={item.status} tone={item.status === 'READY' ? 'green' : item.status === 'LIMITED' ? 'amber' : 'red'} /></div>)}</div>;

const WorkspaceState = ({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) => <div className="klarvido-workspace-state"><FileSearch /><h1>{title}</h1>{description && <p>{description}</p>}{action}</div>;
const LoadingState = () => <div className="klarvido-page"><div className="klarvido-loading-heading"><Skeleton className="h-10 w-72" /><Skeleton className="h-5 w-96" /></div><div className="klarvido-kpi-grid">{Array.from({ length: 4 }, (_, index) => <Skeleton key={index} className="h-36" />)}</div><Skeleton className="h-80 w-full" /></div>;

const money = (value: number) => new Intl.NumberFormat('pl-PL', { style: 'currency', currency: 'PLN', maximumFractionDigits: 0 }).format(value);
const percent = (value: number) => `${new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 }).format(value)}%`;
const formatValue = (value?: Value | null) => !value?.value ? '—' : value.unit === 'PLN' ? money(numeric(value.value)) : value.unit === '%' ? percent(numeric(value.value)) : value.unit === 'pp' ? `${numeric(value.value).toFixed(1)} pp` : new Intl.NumberFormat('pl-PL').format(numeric(value.value));
const compactMoney = (value: number) => `${Math.round(value / 1000)} tys.`;
const shortMonth = (label: string) => label.slice(0, 3);
const readinessName = (analysis: string) => ({ customer_concentration: 'Koncentracja klientów', customer_trend: 'Trend klientów', supplier_concentration: 'Koncentracja dostawców', cost_structure: 'Struktura kosztów' }[analysis] || analysis);

const exportCsv = (invoices: Invoice[]) => {
  const header = ['Numer', 'Kontrahent', 'Typ', 'Data', 'Netto', 'VAT', 'Brutto', 'Kategoria'];
  const quote = (value: string) => `"${value.replaceAll('"', '""')}"`;
  const rows = invoices.map((invoice) => [invoice.documentNumber, invoice.counterpartyName, invoice.invoiceType, invoice.issueDate, invoice.netAmount, invoice.taxAmount, invoice.grossAmount, invoice.categories.join(', ')].map(quote).join(';'));
  const url = URL.createObjectURL(new Blob([`\uFEFF${[header.join(';'), ...rows].join('\n')}`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'klarvido-faktury.csv';
  link.click();
  URL.revokeObjectURL(url);
};
