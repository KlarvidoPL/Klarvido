import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { render } from '@sb/webapp-api-client/tests/utils/rendering';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { useTenantKsef } from '../../../../../hooks/useTenantKsef';
import { useCurrentTenant } from '../../../../../providers';
import { membershipFactory, tenantFactory } from '../../../../../tests/factories/tenant';
import { KsefTokenCard } from '../ksefTokenCard';

jest.mock('../../../../../hooks/useTenantKsef', () => ({
  useTenantKsef: jest.fn(),
}));

jest.mock('../../../../../providers', () => ({
  ...jest.requireActual('../../../../../providers'),
  useCurrentTenant: jest.fn(),
}));

const mockedUseTenantKsef = useTenantKsef as jest.Mock;
const mockedUseCurrentTenant = useCurrentTenant as jest.Mock;

type MockCredential = {
  status: string;
  tokenName: string;
  tokenHint: string;
  lastVerifiedAt: string | null;
  lastErrorCode: string;
  updatedAt: string;
};

const credential = (overrides: Partial<MockCredential> = {}): MockCredential => ({
  status: 'VALID',
  tokenName: 'KlarvidoTest',
  tokenHint: 'debb',
  lastVerifiedAt: '2026-10-03T19:56:00Z',
  lastErrorCode: '',
  updatedAt: '2026-10-03T19:56:00Z',
  ...overrides,
});

const tenant = tenantFactory({
  id: 'tenant-1',
  country: 'PL',
  membership: membershipFactory({ role: 'OWNER' as never }),
});

const setup = ({ credential: cred, loading = false }: { credential: MockCredential | null; loading?: boolean }) => {
  const testToken = jest.fn().mockResolvedValue({ data: { testKsefToken: { ok: true, errorCode: '' } } });
  mockedUseTenantKsef.mockReturnValue({
    credential: cred,
    loading,
    refetch: jest.fn(),
    testToken,
    testing: false,
    deleteToken: jest.fn(),
    deleting: false,
  });
  mockedUseCurrentTenant.mockReturnValue({ data: { id: 'tenant-1', country: 'PL' } });
  return { testToken, commonQueryMock: fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })) };
};

describe('KsefTokenCard: Component', () => {
  describe('when no token is connected', () => {
    it('shows the connect button to users who can manage KSeF', async () => {
      const { commonQueryMock } = setup({ credential: null });

      const { waitForApolloMocks } = render(<KsefTokenCard canManageKsef />, { apolloMocks: [commonQueryMock] });
      await waitForApolloMocks();

      expect(screen.getByText('No KSeF token connected')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /connect ksef token/i })).toBeInTheDocument();
    });

    it('hides the connect button from users who can only view KSeF', async () => {
      const { commonQueryMock } = setup({ credential: null });

      const { waitForApolloMocks } = render(<KsefTokenCard canManageKsef={false} />, { apolloMocks: [commonQueryMock] });
      await waitForApolloMocks();

      expect(screen.getByText('No KSeF token connected')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /connect ksef token/i })).not.toBeInTheDocument();
    });
  });

  describe('when a token is connected', () => {
    it('shows the token name and the test, replace and remove actions to managers', async () => {
      const { commonQueryMock } = setup({ credential: credential() });

      const { waitForApolloMocks } = render(<KsefTokenCard canManageKsef />, { apolloMocks: [commonQueryMock] });
      await waitForApolloMocks();

      expect(screen.getByText('KlarvidoTest')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /test connection/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /replace token/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument();
    });

    it('shows status only to users who cannot manage KSeF', async () => {
      const { commonQueryMock } = setup({ credential: credential() });

      const { waitForApolloMocks } = render(<KsefTokenCard canManageKsef={false} />, { apolloMocks: [commonQueryMock] });
      await waitForApolloMocks();

      expect(screen.getByText('KlarvidoTest')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /test connection/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /replace token/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /remove/i })).not.toBeInTheDocument();
    });

    it('falls back to the masked hint when KSeF did not return a token name', async () => {
      const { commonQueryMock } = setup({ credential: credential({ tokenName: '' }) });

      const { waitForApolloMocks } = render(<KsefTokenCard canManageKsef={false} />, { apolloMocks: [commonQueryMock] });
      await waitForApolloMocks();

      expect(screen.getByText('••••debb')).toBeInTheDocument();
    });

    it('runs the connection test for the current tenant', async () => {
      const { testToken, commonQueryMock } = setup({ credential: credential() });

      const { waitForApolloMocks } = render(<KsefTokenCard canManageKsef />, { apolloMocks: [commonQueryMock] });
      await waitForApolloMocks();
      await userEvent.click(screen.getByRole('button', { name: /test connection/i }));

      expect(testToken).toHaveBeenCalledWith({ variables: { tenantId: 'tenant-1' } });
    });
  });
});
