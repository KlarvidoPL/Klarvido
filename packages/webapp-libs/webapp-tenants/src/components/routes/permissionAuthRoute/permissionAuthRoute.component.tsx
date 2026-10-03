import { TenantType } from '@sb/webapp-api-client/constants';
import { Navigate, Outlet, useOutletContext } from 'react-router-dom';

import { usePermissionCheck, PermissionCode } from '../../../hooks/usePermissionCheck';
import { useGenerateTenantPath } from '../../../hooks/useGenerateTenantPath';
import { RoutesConfig } from '../../../config/routes';
import { useCurrentTenant } from '../../../providers';

export type PermissionAuthRouteProps = {
  /**
   * Required permission(s) to access the route
   */
  permissions: PermissionCode | PermissionCode[];
  /**
   * How to check multiple permissions:
   * - 'any' (default): User needs at least one permission
   * - 'all': User needs all permissions
   */
  mode?: 'any' | 'all';
  /**
   * Where to redirect when access is denied
   * - 'accessDenied' (default): Show access denied page
   * - 'home': Redirect to tenant home
   * - Custom path: Redirect to specific path
   */
  fallback?: 'accessDenied' | 'home' | string;
  /**
   * When true, also requires the current tenant to be a real organization (not the
   * personal/no-selection state) - redirects home regardless of `fallback`, since
   * "access denied" is the wrong message when there's no org context to check
   * permissions against at all.
   */
  requiresOrganization?: boolean;
};

/**
 * Renders route only for users that have specific permission(s).
 * Shows an Access Denied page instead of silently redirecting.
 *
 * @example
 * ```tsx
 * <Route path="/settings" element={<PermissionAuthRoute permissions="org.settings.view" />}>
 *   <Route index element={<SettingsPage />} />
 * </Route>
 *
 * // Multiple permissions (any)
 * <Route path="/admin" element={<PermissionAuthRoute permissions={['org.roles.manage', 'members.invite']} mode="any" />}>
 *   <Route index element={<AdminPage />} />
 * </Route>
 * ```
 */
export const PermissionAuthRoute = ({
  permissions,
  mode = 'any',
  fallback = 'accessDenied',
  requiresOrganization = false,
}: PermissionAuthRouteProps) => {
  const { hasPermission, hasAnyPermission, hasAllPermissions, loading } = usePermissionCheck(permissions);
  const generateTenantPath = useGenerateTenantPath();
  const { data: currentTenant } = useCurrentTenant();
  // Forward whatever outlet context a parent layout route (e.g. ActiveSubscriptionContext)
  // passed down - rendering a plain <Outlet /> here would otherwise shadow it with
  // undefined for any descendant route nested through this permission check.
  const outletContext = useOutletContext();

  // Show nothing while loading permissions
  if (loading) {
    return null;
  }

  // No org context to even check permissions against - always send home, regardless
  // of `fallback`.
  if (requiresOrganization && currentTenant?.type !== TenantType.ORGANIZATION) {
    return <Navigate to={generateTenantPath(RoutesConfig.home)} replace />;
  }

  const permissionsArray = Array.isArray(permissions) ? permissions : [permissions];
  const hasAccess =
    permissionsArray.length === 1 ? hasPermission : mode === 'all' ? hasAllPermissions : hasAnyPermission;

  if (hasAccess) {
    return <Outlet context={outletContext} />;
  }

  // Determine where to redirect
  if (fallback === 'accessDenied') {
    return <Navigate to={generateTenantPath(RoutesConfig.tenant.accessDenied)} replace />;
  }
  
  if (fallback === 'home') {
    return <Navigate to={generateTenantPath(RoutesConfig.home)} replace />;
  }

  return <Navigate to={fallback} replace />;
};
