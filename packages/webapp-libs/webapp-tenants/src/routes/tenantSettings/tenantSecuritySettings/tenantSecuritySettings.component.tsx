import { FormattedMessage } from 'react-intl';

import { Alert, AlertDescription, AlertTitle } from '@sb/webapp-core/components/ui/alert';
import { ENV } from '@sb/webapp-core/config/env';

import { usePermissionCheck } from '../../../hooks';
import { useCurrentTenant } from '../../../providers';
import {
  AuditLogCard,
  DirectorySyncCard,
  DomainVerificationCard,
  KsefTokenCard,
  SSOConnectionCard,
} from './components';

export const TenantSecuritySettings = () => {
  const { data: currentTenant } = useCurrentTenant();
  const { hasPermission: canViewKsef } = usePermissionCheck('security.ksef.view');
  const { hasPermission: canManageKsef } = usePermissionCheck('security.ksef.manage');
  // Permission checks
  const { hasPermission: canViewSecurity } = usePermissionCheck('security.view');
  const { hasPermission: canManageSSO } = usePermissionCheck('security.sso.manage');
  const { hasPermission: canViewLogs } = usePermissionCheck('security.logs.view');

  return (
    <div className="space-y-6">
      {currentTenant?.country === 'PL' && canViewKsef && <KsefTokenCard canManageKsef={canManageKsef} />}
      {canViewSecurity && (
        <>
          {!ENV.SSO_CONFIGURATION_ENABLED && (
            <Alert>
              <AlertTitle>
                <FormattedMessage defaultMessage="Single sign-on is not available yet" id="SSO Settings / Not available title" />
              </AlertTitle>
              <AlertDescription>
                <FormattedMessage
                  defaultMessage="Domains, identity provider connections and directory sync can't be set up yet. This section will be enabled in a later release."
                  id="SSO Settings / Not available description"
                />
              </AlertDescription>
            </Alert>
          )}
          {/* While SSO is unavailable the cards are shown greyed out and cannot be used */}
          <div
            aria-disabled={!ENV.SSO_CONFIGURATION_ENABLED}
            className={ENV.SSO_CONFIGURATION_ENABLED ? undefined : 'pointer-events-none space-y-6 opacity-50'}
          >
            <DomainVerificationCard canManageSSO={canManageSSO && ENV.SSO_CONFIGURATION_ENABLED} />
            <SSOConnectionCard canManageSSO={canManageSSO && ENV.SSO_CONFIGURATION_ENABLED} />
            <DirectorySyncCard canManageSSO={canManageSSO && ENV.SSO_CONFIGURATION_ENABLED} />
          </div>
        </>
      )}
      {canViewLogs && <AuditLogCard />}
    </div>
  );
};
