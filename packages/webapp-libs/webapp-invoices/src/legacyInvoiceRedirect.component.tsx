import { useGenerateTenantPath } from '@sb/webapp-tenants/hooks';
import { Navigate } from 'react-router-dom';

import { RoutesConfig } from './config/routes';

export const LegacyInvoiceRedirect = () => {
  const generatePath = useGenerateTenantPath();
  return <Navigate to={generatePath(RoutesConfig.invoices.list)} replace />;
};
