import { TenantType } from '@sb/webapp-api-client/constants';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { Tabs } from '@sb/webapp-core/components/ui/tabs';
import { screen } from '@testing-library/react';

import { RoutesConfig } from '../../../../config/routes';
import { tenantFactory } from '../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../tests/utils/rendering';
import { TenantMembers } from '../tenantMembers.component';

const tenantId = 'testId';

describe('TenantMembers: Component', () => {
  const Component = () => (
    <Tabs value={`/en/${tenantId}/tenant/settings/members`}>
      <TenantMembers />
    </Tabs>
  );

  it('should render members with invitation form', async () => {
    const tenant = tenantFactory({ id: tenantId, type: TenantType.ORGANIZATION });
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId });

    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] }))];

    render(<Component />, { apolloMocks, routerProps });

    expect(await screen.findByTestId('tenant-members-list')).toBeInTheDocument();
  });
});
