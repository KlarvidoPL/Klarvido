import { TenantType } from '@sb/webapp-api-client/constants';
import { Navigate, Outlet } from 'react-router-dom';

import { RoutesConfig } from '../../../config/routes';
import { useGenerateTenantPath } from '../../../hooks';
import { useCurrentTenant } from '../../../providers';

/** Keeps newly created organizations inside onboarding until Summary is confirmed. */
export const OnboardingCompletionRoute = () => {
  const { data: tenant } = useCurrentTenant();
  const generateTenantPath = useGenerateTenantPath();

  if (tenant?.type === TenantType.ORGANIZATION && tenant.onboardingRequired && !tenant.onboardingCompleted) {
    return <Navigate to={generateTenantPath(RoutesConfig.tenant.onboarding)} replace />;
  }

  return <Outlet />;
};
