import { asyncComponent } from '@sb/webapp-core/utils/asyncComponent';

export const Invoices = asyncComponent(() => import('./invoices.component'));
export { LegacyInvoiceRedirect } from './legacyInvoiceRedirect.component';
