import { getFragmentData } from '@sb/webapp-api-client';
import {
  commonQueryCurrentUserFragment,
  commonQueryMembershipFragment,
  useCommonQuery,
} from '@sb/webapp-api-client/providers';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import { Navigate, useParams } from 'react-router-dom';

import { useTenants } from '../../hooks/useTenants/useTenants.hook';
import currentTenantContext from './currentTenantProvider.context';
import { setCurrentTenantStorageState, store } from './currentTenantProvider.storage';
import { CurrentTenantProviderProps } from './currentTenantProvider.types';
import { getCurrentTenant, parseStoredState } from './currentTenantProvider.utils';

export type TenantPathParams = {
  tenantId: string;
};

/**
 *
 * @param children
 * @constructor
 *
 * @category Component
 */
export const CurrentTenantProvider = ({ children }: CurrentTenantProviderProps) => {
  const tenants = useTenants();
  const params = useParams<TenantPathParams>();
  const { data, loading, error } = useCommonQuery();
  const generateLocalePath = useGenerateLocalePath();
  const storedState = useSyncExternalStore(store.subscribe, store.getSnapshot);

  const profile = getFragmentData(commonQueryCurrentUserFragment, data?.currentUser);
  const userId = profile?.id;

  const { parsedStoredState, storedTenantId } = parseStoredState(storedState, userId);

  const currentTenant = getCurrentTenant(params.tenantId, storedTenantId, tenants, !!profile?.isSuperuser);
  const currentMembership = getFragmentData(commonQueryMembershipFragment, currentTenant?.membership);

  useEffect(() => {
    if (currentTenant && userId && (!params.tenantId || currentTenant.id === params.tenantId)) {
      const { parsedStoredState: state } = parseStoredState(storedState, userId);
      state[userId] = currentTenant.id;
      setCurrentTenantStorageState(state);
    }
  }, [currentTenant, storedState, userId, params.tenantId]);

  const value = useMemo(() => ({ data: currentTenant || null }), [currentTenant]);

  // A refreshed membership list can remove the active organization after another
  // member deletes it. Redirect before child route guards handle the stale URL.
  const lostActiveTenant =
    !loading &&
    !error &&
    userId &&
    params.tenantId &&
    storedTenantId === params.tenantId &&
    currentTenant?.id !== params.tenantId;

  if (lostActiveTenant) return <Navigate to={generateLocalePath(RoutesConfig.home)} replace />;

  return <currentTenantContext.Provider value={value}>{children}</currentTenantContext.Provider>;
};
