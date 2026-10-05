import { MockedProvider } from '@apollo/client/testing/react';
import { CurrentUserType } from '@sb/webapp-api-client';
import { CommonQuery, commonQueryCurrentUserQuery } from '@sb/webapp-api-client/providers';
import { currentUserFactory } from '@sb/webapp-api-client/tests/factories';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { IntlProvider } from 'react-intl';
import { MemoryRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom';

import { CurrentTenantProvider } from '../../../providers';
import { CURRENT_TENANT_STORAGE_KEY } from '../../../providers/currentTenantProvider/currentTenantProvider.types';
import { tenantFactory } from '../../../tests/factories/tenant';
import { CompanyHomeRoute } from '../companyHomeRoute.component';
import { CompanySelection } from '../companySelection.component';
import { setDefaultOrganizationMutation } from '../companySelection.graphql';

const one = tenantFactory({ id: 'one', name: 'Firma Alpha', nip: '1234567890', onboardingRequired: false });
const two = tenantFactory({ id: 'two', name: 'Firma Beta', nip: '9876543210', onboardingRequired: false });
const Location = () => <output data-testid="location">{useLocation().pathname}</output>;
const Providers = () => (
  <CurrentTenantProvider>
    <Outlet />
    <Location />
  </CurrentTenantProvider>
);
const show = (user: CurrentUserType, path = '/pl/companies', extraMocks: any[] = []) =>
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
        ...extraMocks,
      ]}
    >
      <IntlProvider locale="pl" defaultLocale="pl">
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
                <Route path="companies" element={<CompanySelection />} />
                <Route path="add-tenant" element={<span>Dodawanie firmy</span>} />
                <Route path="tenant-invitation/:token" element={<span>Zaproszenie</span>} />
                <Route path="404" element={<span>Brak dostępu</span>} />
                <Route
                  path=":tenantId"
                  element={
                    <CompanyHomeRoute>
                      <span>Dashboard</span>
                    </CompanyHomeRoute>
                  }
                />
                <Route path=":tenantId/tenant/onboarding" element={<span>Onboarding</span>} />
              </Route>
            </Routes>
          </CommonQuery>
        </MemoryRouter>
      </IntlProvider>
    </MockedProvider>
  );

beforeEach(() => localStorage.clear());

it('shows cards, neutral KPI placeholders, search and separate invitations', async () => {
  const invitation = tenantFactory({
    id: 'invite',
    name: 'Firma Zaproszona',
    membership: { invitationAccepted: false, invitationToken: 'invite-token' },
  });
  show(currentUserFactory({ tenants: [one, two, invitation], defaultOrganizationId: 'one' }));
  await screen.findByRole('heading', { name: 'Firma Alpha' });
  expect(screen.getByText('Dostępne firmy: 2')).toBeInTheDocument();
  expect(screen.getByText('Domyślna')).toBeInTheDocument();
  expect(screen.getAllByText('Jeszcze niedostępne')).toHaveLength(4);
  expect(screen.getByRole('link', { name: 'Zobacz zaproszenie' })).toHaveAttribute(
    'href',
    '/pl/tenant-invitation/invite-token'
  );
  fireEvent.change(screen.getByLabelText('Szukaj po nazwie lub NIP-ie'), { target: { value: '987 654' } });
  expect(screen.queryByRole('heading', { name: 'Firma Alpha' })).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Firma Beta' })).toBeInTheDocument();
});

it('saves and removes the default through the cache without switching the company', async () => {
  const mutationResult = jest.fn(() => ({
    data: {
      setDefaultOrganization: { defaultOrganizationId: 'one', __typename: 'SetDefaultOrganizationMutationPayload' },
    },
  }));
  show(currentUserFactory({ tenants: [one, two] }), '/pl/companies', [
    {
      request: { query: setDefaultOrganizationMutation, variables: { organizationId: 'one' } },
      result: mutationResult,
    },
    {
      request: { query: setDefaultOrganizationMutation, variables: { organizationId: null } },
      result: { data: { setDefaultOrganization: { defaultOrganizationId: null } } },
    },
  ]);
  await screen.findByRole('heading', { name: 'Firma Alpha' });
  fireEvent.click(screen.getAllByRole('button', { name: 'Ustaw jako domyślną' })[0]);
  await screen.findByRole('button', { name: 'Usuń domyślną' });
  expect(mutationResult).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId('location')).toHaveTextContent('/pl/companies');
  fireEvent.click(screen.getByRole('button', { name: 'Usuń domyślną' }));
  await waitFor(() => expect(screen.queryByText('Domyślna')).not.toBeInTheDocument());
});

it('keeps the existing default after a failed save', async () => {
  show(currentUserFactory({ tenants: [one, two], defaultOrganizationId: 'one' }), '/pl/companies', [
    {
      request: { query: setDefaultOrganizationMutation, variables: { organizationId: 'two' } },
      error: new Error('Unavailable'),
    },
  ]);
  await screen.findByRole('heading', { name: 'Firma Beta' });
  fireEvent.click(screen.getByRole('button', { name: 'Ustaw jako domyślną' }));
  await screen.findByRole('alert');
  expect(screen.getByText('Domyślna')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Usuń domyślną' })).toBeInTheDocument();
});

it.each([
  [[], null, '/pl/add-tenant'],
  [[one], null, '/pl/one'],
  [[one, two], null, '/pl/companies'],
  [[one, two], 'two', '/pl/two'],
  [[one, two], 'revoked', '/pl/companies'],
])(
  'routes home based on available companies and explicit default',
  async (tenants, defaultOrganizationId, expected) => {
    const user = currentUserFactory({ tenants, defaultOrganizationId });
    localStorage.setItem(CURRENT_TENANT_STORAGE_KEY, JSON.stringify({ [user.id]: 'one' }));
    show(user, '/pl/');
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(expected));
  }
);

it('honors a direct company URL over the default and preserves the stored preference', async () => {
  show(currentUserFactory({ tenants: [one, two], defaultOrganizationId: 'two' }), '/pl/one');
  await screen.findByText('Dashboard');
  expect(screen.getByTestId('location')).toHaveTextContent('/pl/one');
});

it('keeps onboarding and rejects unavailable direct company URLs', async () => {
  const unfinished = tenantFactory({ ...one, onboardingRequired: true, onboardingCompleted: false });
  show(currentUserFactory({ tenants: [unfinished, two], defaultOrganizationId: 'one' }), '/pl/one');
  await screen.findByText('Onboarding');
});

it('never falls back to another company for an inaccessible direct URL', async () => {
  show(currentUserFactory({ tenants: [one], defaultOrganizationId: 'one' }), '/pl/foreign');
  await screen.findByText('Brak dostępu');
});

it('opens the chosen company with the keyboard independently of the default', async () => {
  show(currentUserFactory({ tenants: [one, two], defaultOrganizationId: 'two' }));
  const title = await screen.findByRole('heading', { name: 'Firma Alpha' });
  title.closest('a')!.focus();
  await userEvent.keyboard('{Enter}');
  await screen.findByText('Dashboard');
  expect(screen.getByTestId('location')).toHaveTextContent('/pl/one');
});
