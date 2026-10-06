import { usePermissionCheck } from '../../../hooks';
import { useCurrentTenant } from '../../../providers';
import { AuditLogCard, KsefTokenCard } from './components';

export const TenantSecuritySettings = () => {
  const { data: currentTenant } = useCurrentTenant();
  const { hasPermission: canViewKsef } = usePermissionCheck('security.ksef.view');
  const { hasPermission: canManageKsef } = usePermissionCheck('security.ksef.manage');
  const { hasPermission: canViewLogs } = usePermissionCheck('security.logs.view');

  return (
    <div className="space-y-6">
      {currentTenant?.country === 'PL' && canViewKsef && <KsefTokenCard canManageKsef={canManageKsef} />}
      {canViewLogs && <AuditLogCard />}
    </div>
  );
};
