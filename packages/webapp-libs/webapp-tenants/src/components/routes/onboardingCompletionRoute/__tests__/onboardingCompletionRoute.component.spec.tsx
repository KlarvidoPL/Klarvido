import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';

import { RoutesConfig } from '../../../../config/routes';
import { tenantFactory } from '../../../../tests/factories/tenant';
import {
  CurrentTenantRouteWrapper,
  PLACEHOLDER_CONTENT,
  PLACEHOLDER_TEST_ID,
  createMockRouterProps,
  render,
} from '../../../../tests/utils/rendering';
import { OnboardingCompletionRoute } from '../onboardingCompletionRoute.component';

const TENANT_ID = 'onboarding-tenant';

const routes = (
  <Routes>
    <Route element={<OnboardingCompletionRoute />}>
      <Route path={RoutesConfig.tenant.settings.general} element={PLACEHOLDER_CONTENT} />
    </Route>
    <Route path={RoutesConfig.tenant.onboarding} element={<span data-testid="onboarding">onboarding</span>} />
  </Routes>
);

const renderForTenant = (onboardingRequired: boolean, onboardingCompleted: boolean) => {
  const tenant = tenantFactory({ id: TENANT_ID, onboardingRequired, onboardingCompleted });
  const user = currentUserFactory({ tenants: [tenant] });
  return render(routes, {
    TenantWrapper: CurrentTenantRouteWrapper,
    routerProps: createMockRouterProps(RoutesConfig.tenant.settings.general, { tenantId: TENANT_ID }),
    apolloMocks: [fillCommonQueryWithUser(user)],
  });
};

describe('OnboardingCompletionRoute', () => {
  it('redirects an incomplete required organization to onboarding', async () => {
    renderForTenant(true, false);
    expect(await screen.findByTestId('onboarding')).toBeInTheDocument();
    expect(screen.queryByTestId(PLACEHOLDER_TEST_ID)).not.toBeInTheDocument();
  });

  it.each([
    [false, false],
    [true, true],
  ])('allows optional or completed onboarding', async (required, completed) => {
    renderForTenant(required, completed);
    expect(await screen.findByTestId(PLACEHOLDER_TEST_ID)).toBeInTheDocument();
  });
});
