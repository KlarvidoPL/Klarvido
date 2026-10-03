import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Paragraph } from '@sb/webapp-core/components/typography';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@sb/webapp-core/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@sb/webapp-core/components/ui/tabs';
import { RoutesConfig as FinancesRoutesConfig } from '@sb/webapp-finances/config/routes';
import { Building2 } from 'lucide-react';
import { useEffect, useMemo } from 'react';
import { Helmet } from 'react-helmet-async';
import { FormattedMessage, useIntl } from 'react-intl';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { RoutesConfig } from '../../config/routes';
import { useGenerateTenantPath, usePermissionCheck } from '../../hooks';
import { useCurrentTenant } from '../../providers';

export const TenantSettings = () => {
  const intl = useIntl();
  const location = useLocation();
  const navigate = useNavigate();
  const generateTenantPath = useGenerateTenantPath();

  // Permission-based tab visibility
  const { hasPermission: canViewMembers, loading: loadingMembers } = usePermissionCheck('members.view');
  const { hasPermission: canViewRoles, loading: loadingRoles } = usePermissionCheck('org.roles.view');
  const { hasPermission: canViewSettings, loading: loadingSettings } = usePermissionCheck('org.settings.view');
  const { hasPermission: canViewBilling, loading: loadingBilling } = usePermissionCheck('billing.view');
  const { hasPermission: canViewSecurity, loading: loadingSecurity } = usePermissionCheck('security.view');
  const { hasPermission: canViewKsef, loading: loadingKsef } = usePermissionCheck('security.ksef.view');
  const { data: currentTenant } = useCurrentTenant();
  const { hasPermission: canViewActivityLogs, loading: loadingLogs } = usePermissionCheck('security.logs.view');
  const { hasPermission: canViewBackup, loading: loadingBackup } = usePermissionCheck('backup.view');

  // KSeF is the only Security-tab card for non-Security roles, and it is Polish-only
  const canSeeKsefCard = canViewKsef && currentTenant?.country === 'PL';
  const canViewSecurityTab = canViewSecurity || canSeeKsefCard;

  const isLoading = loadingMembers || loadingRoles || loadingSettings || loadingBilling || loadingSecurity || loadingKsef || loadingLogs || loadingBackup;

  // Determine the first available tab based on permissions
  const availableTabs = useMemo(() => {
    const tabs = [];
    if (canViewMembers) tabs.push({ path: RoutesConfig.tenant.settings.members, permission: 'members.view' });
    if (canViewRoles) tabs.push({ path: RoutesConfig.tenant.settings.roles, permission: 'org.roles.view' });
    if (canViewSettings) tabs.push({ path: RoutesConfig.tenant.settings.general, permission: 'org.settings.view' });
    if (canViewBilling) tabs.push({ path: FinancesRoutesConfig.subscriptions.index, permission: 'billing.view' });
    if (canViewSecurityTab) {
      tabs.push({ path: RoutesConfig.tenant.settings.security, permission: canViewSecurity ? 'security.view' : 'security.ksef.view' });
    }
    if (canViewActivityLogs) tabs.push({ path: RoutesConfig.tenant.settings.activityLogs, permission: 'security.logs.view' });
    if (canViewBackup) tabs.push({ path: RoutesConfig.tenant.settings.backup, permission: 'backup.view' });
    return tabs;
  }, [canViewMembers, canViewRoles, canViewSettings, canViewBilling, canViewSecurityTab, canViewSecurity, canViewActivityLogs, canViewBackup]);

  // Redirect to first available tab if current path is not accessible
  useEffect(() => {
    if (isLoading || availableTabs.length === 0) return;

    const currentPath = location.pathname;
    const isOnValidTab = availableTabs.some((tab) => generateTenantPath(tab.path) === currentPath);

    if (!isOnValidTab && availableTabs.length > 0) {
      navigate(generateTenantPath(availableTabs[0].path), { replace: true });
    }
  }, [isLoading, availableTabs, location.pathname, generateTenantPath, navigate]);

  return (
    <PageLayout>
      <Helmet
        title={intl.formatMessage({
          defaultMessage: 'Organization Settings',
          id: 'Tenant settings / page title',
        })}
      />

      <div className="mx-auto w-full max-w-5xl space-y-8">
        {/* Hero Section */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Building2 className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-bold tracking-tight">
              <FormattedMessage defaultMessage="Organization settings" id="Tenant settings / Header" />
            </h1>
          </div>
          <Paragraph className="text-lg text-muted-foreground">
            <FormattedMessage defaultMessage="Manage your organization" id="Tenant settings / Subheading" />
          </Paragraph>
        </div>

        <Tabs value={location.pathname} className="space-y-6">
          <TabsList className="hidden gap-2 lg:flex lg:h-10 lg:w-fit">
            {canViewMembers && (
              <Link to={generateTenantPath(RoutesConfig.tenant.settings.members)} replace>
                <TabsTrigger value={generateTenantPath(RoutesConfig.tenant.settings.members)}>
                  <FormattedMessage defaultMessage="Members" id="Tenant settings / Members" />
                </TabsTrigger>
              </Link>
            )}
            {canViewRoles && (
              <Link to={generateTenantPath(RoutesConfig.tenant.settings.roles)} replace>
                <TabsTrigger value={generateTenantPath(RoutesConfig.tenant.settings.roles)}>
                  <FormattedMessage defaultMessage="Roles" id="Tenant settings / Roles" />
                </TabsTrigger>
              </Link>
            )}
            {canViewSettings && (
              <Link to={generateTenantPath(RoutesConfig.tenant.settings.general)} replace>
                <TabsTrigger value={generateTenantPath(RoutesConfig.tenant.settings.general)}>
                  <FormattedMessage defaultMessage="General" id="Tenant settings / General" />
                </TabsTrigger>
              </Link>
            )}
            {canViewBilling && (
              <Link to={generateTenantPath(FinancesRoutesConfig.subscriptions.index)}>
                <TabsTrigger value={generateTenantPath(FinancesRoutesConfig.subscriptions.index)}>
                  <FormattedMessage defaultMessage="Subscription" id="Tenant settings / Subscription" />
                </TabsTrigger>
              </Link>
            )}
            {canViewSecurityTab && (
              <Link to={generateTenantPath(RoutesConfig.tenant.settings.security)} replace>
                <TabsTrigger value={generateTenantPath(RoutesConfig.tenant.settings.security)}>
                  <FormattedMessage defaultMessage="Security" id="Tenant settings / Security" />
                </TabsTrigger>
              </Link>
            )}
            {canViewActivityLogs && (
              <Link to={generateTenantPath(RoutesConfig.tenant.settings.activityLogs)} replace>
                <TabsTrigger value={generateTenantPath(RoutesConfig.tenant.settings.activityLogs)}>
                  <FormattedMessage defaultMessage="Activity Logs" id="Tenant settings / Activity Logs" />
                </TabsTrigger>
              </Link>
            )}
            {canViewBackup && (
              <Link to={generateTenantPath(RoutesConfig.tenant.settings.backup)} replace>
                <TabsTrigger value={generateTenantPath(RoutesConfig.tenant.settings.backup)}>
                  <FormattedMessage defaultMessage="Backups" id="Tenant settings / Backups" />
                </TabsTrigger>
              </Link>
            )}
          </TabsList>

          <div className="lg:hidden">
            <Select value={location.pathname} onValueChange={(value) => navigate(value, { replace: true })}>
              <SelectTrigger className="border-transparent bg-muted">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {canViewMembers && (
                  <SelectItem value={generateTenantPath(RoutesConfig.tenant.settings.members)}>
                    <FormattedMessage defaultMessage="Members" id="Tenant settings / Members" />
                  </SelectItem>
                )}
                {canViewRoles && (
                  <SelectItem value={generateTenantPath(RoutesConfig.tenant.settings.roles)}>
                    <FormattedMessage defaultMessage="Roles" id="Tenant settings / Roles" />
                  </SelectItem>
                )}
                {canViewSettings && (
                  <SelectItem value={generateTenantPath(RoutesConfig.tenant.settings.general)}>
                    <FormattedMessage defaultMessage="General" id="Tenant settings / General" />
                  </SelectItem>
                )}
                {canViewBilling && (
                  <SelectItem value={generateTenantPath(FinancesRoutesConfig.subscriptions.index)}>
                    <FormattedMessage defaultMessage="Subscription" id="Tenant settings / Subscription" />
                  </SelectItem>
                )}
                {canViewSecurityTab && (
                  <SelectItem value={generateTenantPath(RoutesConfig.tenant.settings.security)}>
                    <FormattedMessage defaultMessage="Security" id="Tenant settings / Security" />
                  </SelectItem>
                )}
                {canViewActivityLogs && (
                  <SelectItem value={generateTenantPath(RoutesConfig.tenant.settings.activityLogs)}>
                    <FormattedMessage defaultMessage="Activity Logs" id="Tenant settings / Activity Logs" />
                  </SelectItem>
                )}
                {canViewBackup && (
                  <SelectItem value={generateTenantPath(RoutesConfig.tenant.settings.backup)}>
                    <FormattedMessage defaultMessage="Backups" id="Tenant settings / Backups" />
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="mt-6">
            <Outlet />
          </div>
        </Tabs>
      </div>
    </PageLayout>
  );
};
