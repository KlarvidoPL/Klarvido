import { usePermissionCheck } from '../../../hooks';
import { useCurrentTenant } from '../../../providers';
import { AuditLogCard, DirectorySyncCard, KsefTokenCard, PasskeysCard, SSOConnectionCard } from './components';

export const TenantSecuritySettings = () => {
  const { data: currentTenant } = useCurrentTenant();
  const { hasPermission: canViewKsef } = usePermissionCheck('ksef.view');
  const { hasPermission: canManageKsef } = usePermissionCheck('ksef.manage');
  // Permission checks
  const { hasPermission: canManageSSO } = usePermissionCheck('security.sso.manage');
  const { hasPermission: canManagePasskeys } = usePermissionCheck('security.passkeys.manage');
  const { hasPermission: canViewLogs } = usePermissionCheck('security.logs.view');

  return (
    <div className="space-y-6">
      {currentTenant?.country === 'PL' && canViewKsef && <KsefTokenCard canManageKsef={canManageKsef} />}
      <SSOConnectionCard canManageSSO={canManageSSO} />
      <DirectorySyncCard canManageSSO={canManageSSO} />
      <PasskeysCard canManagePasskeys={canManagePasskeys} />
      {canViewLogs && <AuditLogCard />}
    </div>
  );
};
