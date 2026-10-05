import { nestedPath } from '@sb/webapp-core/utils';

export const RoutesConfig = { invoices: nestedPath('invoices', { list: '', details: ':id' }) };
