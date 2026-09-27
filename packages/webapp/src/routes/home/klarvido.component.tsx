import { KlarvidoShell } from '@sb/webapp-klarvido';
import { useCurrentTenant } from '@sb/webapp-tenants/providers';
import { Helmet } from 'react-helmet-async';

import { useAuth } from '../../shared/hooks';

export const KlarvidoApp = () => {
  const { currentUser, logout } = useAuth();
  const { data: currentTenant } = useCurrentTenant();

  if (!currentUser) return null;

  return (
    <>
      <Helmet title="Klarvido" />
      <KlarvidoShell companyName={currentTenant?.name} onLogout={logout} user={currentUser} />
    </>
  );
};
