import { useLazyQuery, useMutation, useQuery } from '@apollo/client/react';
import { askKlarvido } from '@sb/webapp-ai-assistant';
import { ComponentKind } from '@sb/webapp-api-client/graphql';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@sb/webapp-core/components/ui/table';
import { RoutesConfig as TenantRoutesConfig } from '@sb/webapp-tenants/config/routes';
import { useGenerateTenantPath, usePermissionCheck } from '@sb/webapp-tenants/hooks';
import { useCurrentTenant } from '@sb/webapp-tenants/providers';
import { Download, Receipt, RefreshCw, Sparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { Link, Navigate, Route, Routes, useParams, useSearchParams } from 'react-router-dom';

import { RoutesConfig } from './config/routes';
import {
  invoiceCsvQuery,
  invoiceQuery,
  invoiceSetupQuery,
  invoiceXmlQuery,
  invoicesQuery,
  setInvoiceCategoryMutation,
  startInvoiceSyncMutation,
} from './invoices.graphql';
import { invoiceMessages } from './invoices.messages';
import { download, filtersFromUrl, historyStartDate, pageFromUrl } from './invoices.utils';

const selectClass = 'h-10 rounded-md border border-input bg-background px-3 text-sm';
const T = ({ id, defaultMessage }: { id: string; defaultMessage: string }) => (
  <FormattedMessage
    {...(invoiceMessages[id as keyof typeof invoiceMessages] || { id: `Invoices / ${id}`, defaultMessage })}
  />
);

const errorMessages: Record<string, { id: string; defaultMessage: string }> = {
  NO_PERMISSIONS: {
    id: 'Invoices / No KSeF permission',
    defaultMessage: 'Token nie ma uprawnienia InvoiceRead do pobierania faktur.',
  },
  INVALID_TOKEN: {
    id: 'Invoices / Invalid token',
    defaultMessage: 'KSeF odrzucił token. Sprawdź połączenie w ustawieniach bezpieczeństwa.',
  },
  NOT_CONFIGURED: {
    id: 'Invoices / Missing token',
    defaultMessage: 'Połącz organizację z KSeF w ustawieniach bezpieczeństwa.',
  },
  RATE_LIMITED: {
    id: 'Invoices / Rate limit',
    defaultMessage: 'KSeF ograniczył liczbę zapytań. Synchronizacja zostanie ponowiona automatycznie.',
  },
  SERVICE_UNAVAILABLE: {
    id: 'Invoices / Unavailable',
    defaultMessage: 'KSeF jest chwilowo niedostępny. Pobrane faktury pozostają dostępne.',
  },
  CONTEXT_CHANGED: {
    id: 'Invoices / Context changed',
    defaultMessage: 'NIP lub środowisko zmieniło się. Wybierz zakres dla nowego importu.',
  },
  DOCUMENT_IMPORT_FAILED: {
    id: 'Invoices / XML error',
    defaultMessage:
      'Nie udało się odczytać części dokumentów. Źródła zostały zachowane; możesz ponowić synchronizację.',
  },
};
const ErrorNotice = ({ code }: { code?: string }) => {
  const intl = useIntl();
  return (
    <p role="alert" className="text-sm text-destructive">
      {intl.formatMessage(
        errorMessages[code || ''] || {
          id: 'Invoices / Request failed',
          defaultMessage: 'Operacja nie powiodła się. Spróbuj ponownie.',
        }
      )}
    </p>
  );
};

const SyncPanel = ({ tenantId }: { tenantId: string }) => {
  const intl = useIntl();
  const { hasPermission: canSync } = usePermissionCheck('invoices.sync');
  const { data, error } = useQuery(invoiceSetupQuery, { variables: { tenantId }, pollInterval: 10000 });
  const [startSync, { loading, error: mutationError }] = useMutation(startInvoiceSyncMutation);
  const [range, setRange] = useState('12');
  const [customDate, setCustomDate] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const status = data?.invoiceSyncStatus;
  const run = status?.runs[0];
  const active = run?.status === 'QUEUED' || run?.status === 'RUNNING';
  const generatePath = useGenerateTenantPath();
  const labels: Record<string, string> = {
    QUEUED: intl.formatMessage({ id: 'Invoices / Queued', defaultMessage: 'Oczekuje' }),
    RUNNING: intl.formatMessage({ id: 'Invoices / Running', defaultMessage: 'Trwa' }),
    COMPLETED: intl.formatMessage({ id: 'Invoices / Completed', defaultMessage: 'Zakończona' }),
    PARTIAL: intl.formatMessage({ id: 'Invoices / Partial', defaultMessage: 'Częściowo zakończona' }),
    FAILED: intl.formatMessage({ id: 'Invoices / Failed', defaultMessage: 'Błąd' }),
  };
  const start = async (withRange: boolean) => {
    try {
      await startSync({
        variables: {
          input: {
            tenantId,
            ...(withRange ? { startDate: range === 'custom' ? customDate : historyStartDate(Number(range)) } : {}),
          },
        },
        refetchQueries: [invoiceSetupQuery],
      });
      setHistoryOpen(false);
    } catch {
      /* Apollo exposes the error below. */
    }
  };
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-lg">
            <T id="KSeF sync" defaultMessage="Synchronizacja KSeF" />
          </CardTitle>
          {run && <Badge variant="outline">{labels[run.status] || run.status}</Badge>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && <ErrorNotice />}
        {status && !status.connected && (
          <p className="text-sm text-muted-foreground">
            <T
              id="Connection needed"
              defaultMessage="Aby pobrać faktury, skonfiguruj połączenie KSeF w ustawieniach bezpieczeństwa."
            />{' '}
            <Link className="underline" to={generatePath(TenantRoutesConfig.tenant.settings.security)}>
              <T id="Security settings" defaultMessage="Ustawienia bezpieczeństwa" />
            </Link>
          </p>
        )}
        {status?.startDate && (
          <p className="text-sm text-muted-foreground">
            <T id="History from" defaultMessage="Historia od" /> {intl.formatDate(status.startDate)} ·{' '}
            <T id="Last success" defaultMessage="Ostatnia udana synchronizacja" />:{' '}
            {status.lastSuccessAt
              ? intl.formatDate(status.lastSuccessAt, { dateStyle: 'medium', timeStyle: 'short' })
              : '—'}
          </p>
        )}
        {run?.errorCode && <ErrorNotice code={run.errorCode} />}
        {mutationError && <ErrorNotice />}
        {active && (
          <p className="flex items-center gap-2 text-sm">
            <RefreshCw className="h-4 w-4 animate-spin" />
            <T id="Import active" defaultMessage="Pobieranie w tle. Możesz przeglądać wcześniej pobrane faktury." />
          </p>
        )}
        {!!status?.importErrorCount && (
          <p className="text-sm text-destructive">
            <T id="Document errors" defaultMessage="Dokumenty z błędem importu" />: {status.importErrorCount}
          </p>
        )}
        {canSync && status?.connected && !active && (
          <>
            {status.startDate && (
              <div className="flex flex-wrap gap-2">
                <Button disabled={loading} onClick={() => void start(false)}>
                  <RefreshCw className="h-4 w-4" />
                  <T id="Sync now" defaultMessage="Synchronizuj teraz" />
                </Button>
                <Button variant="outline" onClick={() => setHistoryOpen(!historyOpen)}>
                  <T id="Extend history" defaultMessage="Rozszerz historię" />
                </Button>
              </div>
            )}
            {(!status.startDate || historyOpen) && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  <T
                    id="First range explanation"
                    defaultMessage="Wybierz historię według daty trwałego zapisu w KSeF, do chwili uruchomienia importu. Filtry na liście dotyczą daty wystawienia. Po uruchomieniu faktury będą synchronizowane co 2 godziny."
                  />
                </p>
                <div className="flex flex-wrap items-end gap-3">
                  <label className="flex flex-col gap-1 text-sm">
                    <T id="History range" defaultMessage="Zakres historii" />
                    <select className={selectClass} value={range} onChange={(event) => setRange(event.target.value)}>
                      <option value="12">
                        {intl.formatMessage({ id: 'Invoices / Twelve months', defaultMessage: '12 miesięcy' })}
                      </option>
                      <option value="6">
                        {intl.formatMessage({ id: 'Invoices / Six months', defaultMessage: '6 miesięcy' })}
                      </option>
                      <option value="custom">
                        {intl.formatMessage({ id: 'Invoices / Custom date', defaultMessage: 'Własna data' })}
                      </option>
                    </select>
                  </label>
                  {range === 'custom' && (
                    <label className="flex flex-col gap-1 text-sm">
                      <T id="Start date" defaultMessage="Data początkowa" />
                      <Input
                        type="date"
                        value={customDate}
                        max={historyStartDate(0)}
                        onChange={(event) => setCustomDate(event.target.value)}
                      />
                    </label>
                  )}
                  <Button
                    disabled={loading || (range === 'custom' && (!customDate || customDate > historyStartDate(0)))}
                    onClick={() => void start(true)}
                  >
                    <T id="Start import" defaultMessage="Pobierz faktury z KSeF" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
        {status?.startDate && (
          <p className="text-xs text-muted-foreground">
            <T
              id="Auto sync"
              defaultMessage="Automatyczna synchronizacja co 2 godziny. Kwoty pochodzą z dokumentów w wybranym środowisku KSeF."
            />
          </p>
        )}
      </CardContent>
    </Card>
  );
};

const CategorySelect = ({
  tenantId,
  invoiceId,
  categoryId,
  onChanged,
}: {
  tenantId: string;
  invoiceId: string;
  categoryId?: string | null;
  onChanged: () => void;
}) => {
  const intl = useIntl();
  const { hasPermission } = usePermissionCheck('invoices.categorize');
  const { data } = useQuery(invoiceSetupQuery, { variables: { tenantId } });
  const [setCategory, { loading, error }] = useMutation(setInvoiceCategoryMutation);
  if (!hasPermission)
    return <span>{data?.invoiceCategories?.find((category) => category?.id === categoryId)?.name || '—'}</span>;
  return (
    <div className="space-y-1">
      <select
        className={`${selectClass} max-w-52`}
        aria-label={intl.formatMessage({ id: 'Invoices / Category', defaultMessage: 'Kategoria' })}
        value={categoryId || ''}
        disabled={loading}
        onChange={async (event) => {
          try {
            await setCategory({
              variables: {
                input: { tenantId, invoiceId, categoryId: event.target.value ? Number(event.target.value) : null },
              },
            });
            onChanged();
          } catch {
            /* Error below. */
          }
        }}
      >
        <option value="">
          {intl.formatMessage({ id: 'Invoices / Uncategorized', defaultMessage: 'Bez kategorii' })}
        </option>
        {data?.invoiceCategories?.map(
          (category) =>
            category && (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            )
        )}
      </select>
      {error && <ErrorNotice />}
    </div>
  );
};

export const InvoiceList = () => {
  const intl = useIntl();
  const { data: tenant } = useCurrentTenant();
  const tenantId = tenant?.id || '';
  const generatePath = useGenerateTenantPath();
  const [params, setParams] = useSearchParams();
  const filters = filtersFromUrl(params);
  const page = pageFromUrl(params);
  const { hasPermission: canExport } = usePermissionCheck('invoices.export');
  const { hasPermission: canAi } = usePermissionCheck('features.ai.use');
  const { data, loading, error, refetch } = useQuery(invoicesQuery, {
    variables: { tenantId, filters, page },
    skip: !tenantId,
    pollInterval: 10000,
    fetchPolicy: 'cache-and-network',
  });
  const { data: setup } = useQuery(invoiceSetupQuery, { variables: { tenantId }, skip: !tenantId });
  const [exportCsv, { loading: exporting, error: exportError }] = useLazyQuery(invoiceCsvQuery, {
    fetchPolicy: 'network-only',
  });
  const [selected, setSelected] = useState<string[]>([]);
  const urlKey = params.toString();
  useEffect(() => {
    setSelected([]);
  }, [tenantId, urlKey]);
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next, { replace: true });
  };
  const total = data?.invoices?.totalCount || 0;
  const rows = data?.invoices?.items || [];
  const money = (amount: unknown) => String(amount ?? '—');
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-3 text-3xl font-bold">
          <Receipt className="h-8 w-8" />
          <T id="Title" defaultMessage="Faktury" />
        </h1>
        <div className="flex flex-wrap gap-2">
          {canAi && (
            <Button
              variant="outline"
              onClick={() =>
                askKlarvido(
                  tenantId,
                  intl.formatMessage({ id: 'Invoices / List context', defaultMessage: 'Lista faktur z filtrami' }),
                  { kind: ComponentKind.INVOICE_LIST, filters }
                )
              }
            >
              <Sparkles className="h-4 w-4" />
              <T id="Ask" defaultMessage="Zapytaj Klarvido" />
            </Button>
          )}
          {canAi && selected.length > 0 && (
            <Button
              variant="outline"
              onClick={() =>
                askKlarvido(
                  tenantId,
                  intl.formatMessage(
                    { id: 'Invoices / Selection context', defaultMessage: 'Zaznaczone faktury ({count})' },
                    { count: selected.length }
                  ),
                  { kind: ComponentKind.INVOICE_SELECTION, invoiceIds: selected }
                )
              }
            >
              <T id="Ask selected" defaultMessage="Zapytaj o zaznaczone" />
            </Button>
          )}
          {canExport && (
            <Button
              variant="outline"
              disabled={exporting}
              onClick={async () => {
                try {
                  const result = await exportCsv({ variables: { tenantId, filters } });
                  if (result.data?.invoiceCsv != null)
                    download('\uFEFF' + result.data.invoiceCsv, 'faktury.csv', 'text/csv;charset=utf-8');
                } catch {
                  /* Error below. */
                }
              }}
            >
              <Download className="h-4 w-4" />
              <T id="CSV" defaultMessage="Eksport CSV" />
            </Button>
          )}
        </div>
      </div>
      <SyncPanel key={tenantId} tenantId={tenantId} />
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="space-y-1 text-sm">
              <T id="Search" defaultMessage="Numer, kontrahent lub NIP" />
              <Input value={params.get('search') || ''} onChange={(event) => update('search', event.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <T id="Direction" defaultMessage="Typ" />
              <select
                className={selectClass}
                value={params.get('direction') || ''}
                onChange={(event) => update('direction', event.target.value)}
              >
                <option value="">
                  {intl.formatMessage({ id: 'Invoices / All directions', defaultMessage: 'Sprzedaż i zakupy' })}
                </option>
                <option value="SALE">
                  {intl.formatMessage({ id: 'Invoices / Sale', defaultMessage: 'Sprzedaż' })}
                </option>
                <option value="PURCHASE">
                  {intl.formatMessage({ id: 'Invoices / Purchase', defaultMessage: 'Zakup' })}
                </option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <T id="Category" defaultMessage="Kategoria" />
              <select
                className={selectClass}
                value={params.get('category') || ''}
                onChange={(event) => update('category', event.target.value)}
              >
                <option value="">
                  {intl.formatMessage({ id: 'Invoices / All categories', defaultMessage: 'Wszystkie kategorie' })}
                </option>
                <option value="uncategorized">
                  {intl.formatMessage({ id: 'Invoices / Uncategorized', defaultMessage: 'Bez kategorii' })}
                </option>
                {setup?.invoiceCategories?.map(
                  (category) =>
                    category && (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    )
                )}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <T id="Issue from" defaultMessage="Data wystawienia od" />
              <Input
                type="date"
                value={params.get('dateFrom') || ''}
                onChange={(event) => update('dateFrom', event.target.value)}
              />
            </label>
            <label className="space-y-1 text-sm">
              <T id="Issue to" defaultMessage="Data wystawienia do" />
              <Input
                type="date"
                value={params.get('dateTo') || ''}
                onChange={(event) => update('dateTo', event.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <T id="Sort" defaultMessage="Sortowanie" />
              <select
                className={selectClass}
                value={params.get('sort') || '-issue_date'}
                onChange={(event) => update('sort', event.target.value)}
              >
                <option value="-issue_date">
                  {intl.formatMessage({ id: 'Invoices / Newest', defaultMessage: 'Od najnowszych' })}
                </option>
                <option value="issue_date">
                  {intl.formatMessage({ id: 'Invoices / Oldest', defaultMessage: 'Od najstarszych' })}
                </option>
                <option value="number">
                  {intl.formatMessage({ id: 'Invoices / By number', defaultMessage: 'Według numeru' })}
                </option>
              </select>
            </label>
          </div>
          {(error || exportError) && <ErrorNotice />}
          {loading && !data && (
            <p role="status">
              <T id="Loading" defaultMessage="Wczytywanie faktur…" />
            </p>
          )}
          {!loading && !error && !rows.length && (
            <p className="py-8 text-center text-muted-foreground">
              {Object.keys(filters).length ? (
                <T id="No results" defaultMessage="Brak faktur pasujących do filtrów." />
              ) : (
                <T id="No invoices" defaultMessage="Brak pobranych faktur. Uruchom import z KSeF, aby je zobaczyć." />
              )}
            </p>
          )}
          {rows.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  {canAi && (
                    <TableHead>
                      <input
                        type="checkbox"
                        aria-label={intl.formatMessage({
                          id: 'Invoices / Select page',
                          defaultMessage: 'Zaznacz stronę',
                        })}
                        checked={rows.every((row) => selected.includes(row.id))}
                        onChange={(event) => setSelected(event.target.checked ? rows.map((row) => row.id) : [])}
                      />
                    </TableHead>
                  )}
                  {[
                    ['Number', 'Numer'],
                    ['Counterparty', 'Kontrahent'],
                    ['Direction', 'Typ'],
                    ['Date', 'Data'],
                    ['Currency', 'Waluta'],
                    ['Net', 'Netto'],
                    ['VAT', 'VAT'],
                    ['Gross', 'Brutto'],
                    ['Category', 'Kategoria'],
                  ].map(([id, label]) => (
                    <TableHead key={id}>
                      <T id={id} defaultMessage={label} />
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    {canAi && (
                      <TableCell>
                        <input
                          type="checkbox"
                          aria-label={intl.formatMessage(
                            { id: 'Invoices / Select invoice', defaultMessage: 'Zaznacz fakturę {number}' },
                            { number: row.number }
                          )}
                          checked={selected.includes(row.id)}
                          onChange={(event) =>
                            setSelected((items) =>
                              event.target.checked ? [...items, row.id] : items.filter((id) => id !== row.id)
                            )
                          }
                        />
                      </TableCell>
                    )}
                    <TableCell>
                      <Link
                        className="font-medium underline-offset-4 hover:underline"
                        to={generatePath(`invoices/${row.id}`)}
                      >
                        {row.number}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {row.direction === 'SALE' ? row.buyerName : row.sellerName}
                      <p className="text-xs text-muted-foreground">
                        {row.direction === 'SALE' ? row.buyerNip : row.sellerNip}
                      </p>
                    </TableCell>
                    <TableCell>
                      {row.direction === 'SALE' ? (
                        <T id="Sale" defaultMessage="Sprzedaż" />
                      ) : (
                        <T id="Purchase" defaultMessage="Zakup" />
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{intl.formatDate(row.issueDate)}</TableCell>
                    <TableCell>{row.currency}</TableCell>
                    <TableCell>{money(row.net)}</TableCell>
                    <TableCell>{money(row.vat)}</TableCell>
                    <TableCell>{money(row.gross)}</TableCell>
                    <TableCell>
                      <CategorySelect
                        tenantId={tenantId}
                        invoiceId={row.id}
                        categoryId={row.category?.id}
                        onChanged={() => void refetch()}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>
              <T id="Count" defaultMessage="Liczba faktur" />: {total}
            </span>
            <div className="flex items-center gap-3">
              <Button variant="outline" disabled={page <= 1} onClick={() => update('page', String(page - 1))}>
                <T id="Previous" defaultMessage="Poprzednia" />
              </Button>
              <span>
                {page} / {Math.max(1, Math.ceil(total / 25))}
              </span>
              <Button variant="outline" disabled={page * 25 >= total} onClick={() => update('page', String(page + 1))}>
                <T id="Next" defaultMessage="Następna" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export const InvoiceDetails = () => {
  const intl = useIntl();
  const { data: tenant } = useCurrentTenant();
  const { id = '' } = useParams();
  const tenantId = tenant?.id || '';
  const generatePath = useGenerateTenantPath();
  const { data, loading, error, refetch } = useQuery(invoiceQuery, {
    variables: { tenantId, id },
    skip: !tenantId,
    fetchPolicy: 'cache-and-network',
  });
  const { hasPermission: canExport } = usePermissionCheck('invoices.export');
  const { hasPermission: canAi } = usePermissionCheck('features.ai.use');
  const [exportXml, { loading: exporting, error: exportError }] = useLazyQuery(invoiceXmlQuery, {
    fetchPolicy: 'network-only',
  });
  const invoice = data?.invoice;
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
      <Link className="text-sm underline" to={generatePath(RoutesConfig.invoices.list)}>
        <T id="Back" defaultMessage="Wróć do faktur" />
      </Link>
      {(error || exportError) && <ErrorNotice />}
      {loading && !invoice && (
        <p>
          <T id="Loading" defaultMessage="Wczytywanie faktur…" />
        </p>
      )}
      {invoice && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-3xl font-bold">{invoice.number}</h1>
              <p className="mt-1 text-sm text-muted-foreground">KSeF: {invoice.ksefNumber}</p>
            </div>
            <div className="flex gap-2">
              {canAi && (
                <Button
                  variant="outline"
                  onClick={() =>
                    askKlarvido(tenantId, invoice.number, {
                      kind: ComponentKind.INVOICE_DETAILS,
                      invoiceIds: [invoice.id],
                    })
                  }
                >
                  <Sparkles className="h-4 w-4" />
                  <T id="Ask" defaultMessage="Zapytaj Klarvido" />
                </Button>
              )}
              {canExport && (
                <Button
                  variant="outline"
                  disabled={exporting}
                  onClick={async () => {
                    try {
                      const result = await exportXml({ variables: { tenantId, id } });
                      if (result.data?.invoiceXml)
                        download(result.data.invoiceXml, `${invoice.ksefNumber}.xml`, 'application/xml;charset=utf-8');
                    } catch {
                      /* Error below. */
                    }
                  }}
                >
                  <Download className="h-4 w-4" />
                  <T id="XML" defaultMessage="Pobierz XML" />
                </Button>
              )}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {[
              ['Seller', 'Sprzedawca', invoice.sellerName, invoice.sellerNip],
              ['Buyer', 'Nabywca', invoice.buyerName, invoice.buyerNip],
            ].map(([key, label, name, nip]) => (
              <Card key={key}>
                <CardHeader>
                  <CardTitle className="text-lg">
                    <T id={key} defaultMessage={label} />
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="font-medium">{name}</p>
                  <p className="text-sm text-muted-foreground">NIP: {nip || '—'}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardContent className="grid gap-4 pt-6 sm:grid-cols-3">
              <div>
                <T id="Date" defaultMessage="Data" />
                <p className="font-medium">{intl.formatDate(invoice.issueDate)}</p>
              </div>
              <div>
                <T id="Kind" defaultMessage="Rodzaj faktury" />
                <p className="font-medium">{invoice.kind}</p>
              </div>
              <div>
                <T id="Category" defaultMessage="Kategoria" />
                <CategorySelect
                  tenantId={tenantId}
                  invoiceId={invoice.id}
                  categoryId={invoice.category?.id}
                  onChanged={() => void refetch()}
                />
              </div>
              {[
                ['Net', 'Netto', invoice.net],
                ['VAT', 'VAT', invoice.vat],
                ['Gross', 'Brutto', invoice.gross],
              ].map(([key, label, amount]) => (
                <div key={String(key)}>
                  <T id={String(key)} defaultMessage={String(label)} />
                  <p className="text-xl font-semibold">
                    {String(amount)} {invoice.currency}
                  </p>
                </div>
              ))}
              <div className="text-xs text-muted-foreground">
                <T id="Stored date" defaultMessage="Trwały zapis w KSeF" />:{' '}
                {intl.formatDate(invoice.permanentStorageDate)}
              </div>
              <div className="text-xs text-muted-foreground">
                <T id="Imported date" defaultMessage="Import do Klarvido" />: {intl.formatDate(invoice.createdAt)}
              </div>
            </CardContent>
          </Card>
          {Array.isArray(invoice.correctedKsefNumbers) && invoice.correctedKsefNumbers.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  <T id="Correction" defaultMessage="Faktury pierwotne" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  <T
                    id="Correction note"
                    defaultMessage="Korekta jest osobnym dokumentem. Faktura pierwotna może znajdować się poza pobraną historią."
                  />
                </p>
                {invoice.correctedKsefNumbers.map((number: string) => (
                  <Link
                    key={number}
                    className="mt-2 block underline"
                    to={`${generatePath(RoutesConfig.invoices.list)}?search=${encodeURIComponent(number)}`}
                  >
                    {number}
                  </Link>
                ))}
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                <T id="Lines" defaultMessage="Pozycje faktury" />
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    {[
                      ['Description', 'Opis'],
                      ['Quantity', 'Ilość'],
                      ['Unit', 'Jednostka'],
                      ['Price', 'Cena jednostkowa'],
                      ['Net', 'Netto'],
                      ['VAT rate', 'Stawka VAT'],
                    ].map(([key, label]) => (
                      <TableHead key={key}>
                        <T id={key} defaultMessage={label} />
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoice.lines.map((line) => (
                    <TableRow key={line.position}>
                      <TableCell>{line.description}</TableCell>
                      <TableCell>{line.quantity ?? '—'}</TableCell>
                      <TableCell>{line.unit || '—'}</TableCell>
                      <TableCell>{line.unitPrice ?? '—'}</TableCell>
                      <TableCell>{line.net ?? '—'}</TableCell>
                      <TableCell>{line.vatRate || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export const Invoices = () => (
  <Routes>
    <Route index element={<InvoiceList />} />
    <Route path=":id" element={<InvoiceDetails />} />
    <Route path="*" element={<Navigate to=".." replace />} />
  </Routes>
);
export default Invoices;
