import { RoutesConfig as CoreRoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { ReactNode } from 'react';
import { FormattedMessage } from 'react-intl';
import { Navigate, useParams } from 'react-router-dom';

import { RoutesConfig } from '../../config/routes';
import { useGenerateTenantPath, useTenants } from '../../hooks';
import { useCurrentTenant } from '../../providers';
import { companyGroups, homeOrganization } from './companySelection.utils';
import { useCompanyUser } from './companyUser.hook';

export const CompanyHomeRoute = ({ children }: { children: ReactNode }) => {
  const { tenantId } = useParams();
  const { user, loading, error } = useCompanyUser();
  const tenants = useTenants();
  const { data: currentTenant } = useCurrentTenant();
  const localePath = useGenerateLocalePath();
  const tenantPath = useGenerateTenantPath();
  if (loading && !user)
    return (
      <p role="status">
        <FormattedMessage id="Companies / Loading" defaultMessage="Loading organizations…" />
      </p>
    );
  if (error || !user)
    return (
      <p role="alert">
        <FormattedMessage
          id="Companies / Load error"
          defaultMessage="Could not load organizations. Refresh the page and try again."
        />
      </p>
    );
  if (tenantId) {
    if (currentTenant?.id !== tenantId) return <Navigate to={localePath(CoreRoutesConfig.notFound)} replace />;
    if (currentTenant.onboardingRequired && !currentTenant.onboardingCompleted) {
      return <Navigate to={tenantPath(RoutesConfig.tenant.onboarding)} replace />;
    }
    return <>{children}</>;
  }
  const { organizations } = companyGroups(tenants, !!user.isSuperuser);
  const selected = homeOrganization(organizations, user.defaultOrganizationId);
  if (selected) return <Navigate to={tenantPath(CoreRoutesConfig.home, { tenantId: selected.id })} replace />;
  return (
    <Navigate to={localePath(organizations.length ? RoutesConfig.organizations : CoreRoutesConfig.addTenant)} replace />
  );
};
