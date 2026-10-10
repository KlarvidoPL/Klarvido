import { MockedProvider } from '@apollo/client/testing/react';
import { CurrentUserType } from '@sb/webapp-api-client';
import { CommonQuery, commonQueryCurrentUserQuery, useCommonQuery } from '@sb/webapp-api-client/providers';
import { currentUserFactory } from '@sb/webapp-api-client/tests/factories';
import { Locale, formatTranslationMessages } from '@sb/webapp-core/config/i18n';
import plMessages from '@sb/webapp-core/translations/pl.json';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IntlProvider } from 'react-intl';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';

import { CurrentTenantProvider } from '../../../providers';
import { tenantFactory } from '../../../tests/factories/tenant';
import { CompanyHomeRoute } from '../companyHomeRoute.component';

const one = tenantFactory({ id: 'one', name: 'Firma Alpha', nip: '1234567890', onboardingRequired: false });
const two = tenantFactory({ id: 'two', name: 'Firma Beta', nip: '9876543210', onboardingRequired: false });
const Location = () => <output data-testid="location">{useLocation().pathname}</output>;
const Refresh = () => {
  const { reload } = useCommonQuery();
  return <button onClick={() => reload()}>Refresh organizations</button>;
};
const Providers = () => (
  <CurrentTenantProvider>
    <Outlet />
    <Location />
    <Refresh />
  </CurrentTenantProvider>
);

const show = (initialUser: CurrentUserType, path: string, refreshedUser = initialUser) => {
  let requests = 0;
  return render(
    <MockedProvider
      mocks={[
        {
          request: { query: commonQueryCurrentUserQuery },
          result: () => {
            const user = requests++ === 0 ? initialUser : { ...refreshedUser, id: initialUser.id };
            return {
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
            };
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
};

beforeEach(() => localStorage.clear());

describe('CompanyHomeRoute', () => {
  it('returns home when a refresh removes the active organization', async () => {
    show(currentUserFactory({ tenants: [one] }), '/pl/one', currentUserFactory({ tenants: [] }));
    await screen.findByText('Tenant dashboard');

    await userEvent.click(screen.getByText('Refresh organizations'));

    await screen.findByText('Dashboard');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/pl\/?$/);
    expect(screen.queryByText('Not found')).not.toBeInTheDocument();
  });

  it('resolves the remaining organization through home after the active one disappears', async () => {
    show(currentUserFactory({ tenants: [one, two] }), '/pl/one', currentUserFactory({ tenants: [two] }));
    await screen.findByText('Tenant dashboard');

    await userEvent.click(screen.getByText('Refresh organizations'));

    await screen.findByText('Tenant dashboard');
    await screen.findByText('/pl/two');
    expect(screen.queryByText('Not found')).not.toBeInTheDocument();
  });

  it('keeps the active page when a different organization disappears', async () => {
    show(currentUserFactory({ tenants: [one, two] }), '/pl/one', currentUserFactory({ tenants: [one] }));
    await screen.findByText('Tenant dashboard');

    await userEvent.click(screen.getByText('Refresh organizations'));

    await screen.findByText('Tenant dashboard');
    expect(screen.getByTestId('location')).toHaveTextContent('/pl/one');
    expect(screen.queryByText('Not found')).not.toBeInTheDocument();
  });

  it('still shows not found for an organization URL that was never accessible', async () => {
    show(currentUserFactory({ tenants: [one] }), '/pl/unknown');
    await screen.findByText('Not found');
  });

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
