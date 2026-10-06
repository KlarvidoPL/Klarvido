import { render, screen } from '@testing-library/react';

import { usePermissionCheck } from '../../../../hooks';
import { useCurrentTenant } from '../../../../providers';
import { TenantSecuritySettings } from '../tenantSecuritySettings.component';

jest.mock('../../../../hooks', () => ({ usePermissionCheck: jest.fn() }));
jest.mock('../../../../providers', () => ({ useCurrentTenant: jest.fn() }));
jest.mock('../components', () => ({
  AuditLogCard: () => <div>Audit Log</div>,
  KsefTokenCard: () => <div>KSeF Token</div>,
}));

const mockPermissions = usePermissionCheck as jest.Mock;
const mockTenant = useCurrentTenant as jest.Mock;

describe('TenantSecuritySettings with enterprise SSO disabled', () => {
  beforeEach(() => {
    mockTenant.mockReturnValue({ data: { country: 'PL' } });
    mockPermissions.mockImplementation(() => ({ hasPermission: true }));
  });

  it('keeps KSeF and audit logs without SSO or directory provisioning', () => {
    render(<TenantSecuritySettings />);
    expect(screen.getByText('KSeF Token')).toBeInTheDocument();
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
    expect(screen.queryByText(/SSO|Single Sign-On|SCIM|Directory Sync/i)).not.toBeInTheDocument();
    expect(mockPermissions).not.toHaveBeenCalledWith('security.sso.manage');
  });

  it('respects the remaining permissions and organization country', () => {
    mockTenant.mockReturnValue({ data: { country: 'DE' } });
    mockPermissions.mockImplementation(() => ({ hasPermission: false }));
    render(<TenantSecuritySettings />);
    expect(screen.queryByText(/Audit Log|KSeF Token/i)).not.toBeInTheDocument();
  });
});
