import { filtersFromUrl, historyStartDate, pageFromUrl } from '../invoices.utils';

it('restores filtering and pagination from shared URLs', () => {
  const params = new URLSearchParams(
    'search=FV&direction=SALE&dateFrom=2026-01-01&category=uncategorized&page=3&unexpected=amount'
  );
  expect(filtersFromUrl(params)).toEqual({
    search: 'FV',
    direction: 'SALE',
    dateFrom: '2026-01-01',
    category: 'uncategorized',
  });
  expect(pageFromUrl(params)).toBe(3);
  expect(pageFromUrl(new URLSearchParams('page=-9'))).toBe(1);
});
it('uses calendar months and clamps the last day of a month', () => {
  expect(historyStartDate(6, new Date(2026, 7, 31))).toBe('2026-02-28');
  expect(historyStartDate(12, new Date(2024, 1, 29))).toBe('2023-02-28');
});
