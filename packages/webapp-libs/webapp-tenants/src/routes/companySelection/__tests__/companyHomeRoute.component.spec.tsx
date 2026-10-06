import { MockedProvider } from '@apollo/client/testing/react';
import { CurrentUserType } from '@sb/webapp-api-client';
import { CommonQuery, commonQueryCurrentUserQuery } from '@sb/webapp-api-client/providers';
import { currentUserFactory } from '@sb/webapp-api-client/tests/factories';
import { Locale, formatTranslationMessages } from '@sb/webapp-core/config/i18n';
import plMessages from '@sb/webapp-core/translations/pl.json';
import { render, screen } from '@testing-library/react';
import { IntlProvider } from 'react-intl';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';

import { CurrentTenantProvider } from '../../../providers';
import { tenantFactory } from '../../../tests/factories/tenant';
import { CompanyHomeRoute } from '../companyHomeRoute.component';

const one = tenantFactory({ id: 'one', name: 'Firma Alpha', nip: '1234567890', onboardingRequired: false });
const two = tenantFactory({ id: 'two', name: 'Firma Beta', nip: '9876543210', onboardingRequired: false });
const Location = () => <output data-testid="location">{useLocation().pathname}</output>;
const Providers = () => (
  <CurrentTenantProvider>
    <Outlet />
    <Location />
  </CurrentTenantProvider>
);

const show = (user: CurrentUserType, path: string) =>
  render(
    <MockedProvider
      mocks={[
        {
          request: { query: commonQueryCurrentUserQuery },
          result: {
            data: {
              currentUser: {
                ...user,
                __typename: 'CurrentUserType',
                hasUsablePassword: true,
                tenants: user.tenants?.map(
                  (company) =>
                    company && {
                      actionLoggingEnabled: true,
                      country: 'PL',
                      nip: null,
                      companyName: null,
                      regon: null,
                      address: null,
                      vatStatus: null,
                      ...company,
                      membership: company.membership && {
                        inviteeEmailAddress: null,
                        userId: null,
                        firstName: null,
                        lastName: null,
                        userEmail: null,
                        avatar: null,
                        ...company.membership,
                      },
                    }
                ),
              },
            },
          },
          maxUsageCount: Infinity,
        },
      ]}
    >
      <IntlProvider locale="pl" defaultLocale="en" messages={formatTranslationMessages(Locale.POLISH, plMessages)}>
        <MemoryRouter initialEntries={[path]}>
          <CommonQuery>
            <Routes>
              <Route path="/:lang" element={<Providers />}>
                <Route
                  index
                  element={
                    <CompanyHomeRoute>
                      <span>Dashboard</span>
                    </CompanyHomeRoute>
                  }
                />
                <Route path="organizations" element={<span>Organization list</span>} />
                <Route path="add-organization" element={<span>Add organization page</span>} />
                <Route
                  path=":tenantId"
                  element={
                    <CompanyHomeRoute>
                      <span>Tenant dashboard</span>
                    </CompanyHomeRoute>
                  }
                />
                <Route path=":tenantId/tenant/onboarding" element={<span>Onboarding</span>} />
                <Route path="404" element={<span>Not found</span>} />
              </Route>
            </Routes>
          </CommonQuery>
        </MemoryRouter>
      </IntlProvider>
    </MockedProvider>
  );

beforeEach(() => localStorage.clear());

describe('CompanyHomeRoute', () => {
  it('opens the stored default organization from the home route', async () => {
    show(currentUserFactory({ tenants: [one, two], defaultOrganizationId: 'two' }), '/pl/');

    await screen.findByText('Tenant dashboard');
    expect(screen.getByTestId('location')).toHaveTextContent('/pl/two');
  });

  it('opens the only organization when no default is stored', async () => {
    show(currentUserFactory({ tenants: [one], defaultOrganizationId: null }), '/pl/');

    await screen.findByText('Tenant dashboard');
    expect(screen.getByTestId('location')).toHaveTextContent('/pl/one');
  });

  it('sends several organizations without a usable default to the organization list', async () => {
    show(currentUserFactory({ tenants: [one, two], defaultOrganizationId: 'revoked' }), '/pl/');

    await screen.findByText('Organization list');
    expect(screen.getByTestId('location')).toHaveTextContent('/pl/organizations');
  });

  it('renders the home content without redirecting when the user has no organizations', async () => {
    show(currentUserFactory({ tenants: [], defaultOrganizationId: 'revoked' }), '/pl/');

    await screen.findByText('Dashboard');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/pl\/$/);
    expect(screen.queryByText('Add organization page')).not.toBeInTheDocument();
  });
});
