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
          <DomainVerificationCard canManageSSO={canManageSSO} />
          <SSOConnectionCard canManageSSO={canManageSSO} />
          <DirectorySyncCard canManageSSO={canManageSSO} />
        </>
      )}
      {canViewLogs && <AuditLogCard />}
    </div>
  );
};
