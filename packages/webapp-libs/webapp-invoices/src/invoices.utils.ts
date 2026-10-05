import type { InvoiceFilters } from '@sb/webapp-api-client/graphql';

export const filtersFromUrl = (params: URLSearchParams): InvoiceFilters => {
  const filters: InvoiceFilters = {};
  for (const key of ['search', 'direction', 'dateFrom', 'dateTo', 'category', 'sort'] as const) {
    const value = params.get(key);
    if (value) filters[key] = value;
  }
  return filters;
};
export const pageFromUrl = (params: URLSearchParams) =>
  Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1);
export const historyStartDate = (months: number, now = new Date()) => {
  const day = now.getDate();
  const start = new Date(now.getFullYear(), now.getMonth() - months, 1);
  start.setDate(Math.min(day, new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate()));
  return `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
};
export const download = (text: string, name: string, type: string) => {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
