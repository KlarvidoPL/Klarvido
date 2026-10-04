import { TenantUserRole, apiClient } from '@sb/webapp-api-client';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { RoutesConfig } from '../../../../../config/routes';
import { membershipFactory, tenantFactory } from '../../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../../tests/utils/rendering';
import { AuditLogCard } from '../auditLogCard';

jest.mock('@sb/webapp-api-client/api', () => ({
  apiClient: {
    get: jest.fn().mockResolvedValue({ data: [] }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    delete: jest.fn().mockResolvedValue({ data: {} }),
  },
  apiURL: jest.fn((path: string) => path),
}));

const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

const TENANT_ID = 'tenant-audit-1';

const createMockAuditLog = (overrides = {}) => ({
  id: 'log-1',
  eventType: 'sso_login_success',
  eventTypeLabel: 'SSO login success',
  eventDescription: 'User signed in via SSO',
  userEmail: 'user@example.com',
  connectionName: 'Okta',
  ipAddress: '192.168.1.1',
  userAgent: 'Mozilla/5.0',
  success: true,
  errorMessage: '',
  metadata: {},
  createdAt: '2024-01-15T10:00:00Z',
  ...overrides,
});

describe('AuditLogCard: Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [],
        totalCount: 0,
        totalPages: 0,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });
  });

  const renderComponent = () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] }))];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.security, { tenantId: TENANT_ID });

    return render(<AuditLogCard />, {
      apolloMocks,
      routerProps,
    });
  };

  it('should render card header', async () => {
    renderComponent();

    expect(await screen.findByText(/security audit log/i)).toBeInTheDocument();
    expect(await screen.findByText(/view recent sso, scim and ksef events/i)).toBeInTheDocument();
  });

  it('should show empty state when no logs', async () => {
    renderComponent();

    expect(await screen.findByText(/no security events yet/i)).toBeInTheDocument();
  });

  it('should display audit log entries', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [createMockAuditLog()],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    expect(await screen.findByText(/SSO login success/i)).toBeInTheDocument();
    expect(await screen.findByText('user@example.com')).toBeInTheDocument();
  });

  it('should show translated titles for KSeF token events', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [
          createMockAuditLog({
            eventType: 'ksef_token_saved',
            eventTypeLabel: 'KSeF Token Saved',
            eventDescription: 'KSeF token saved',
          }),
        ],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    expect(await screen.findByText('KSeF token saved', { selector: 'span' })).toBeInTheDocument();
  });

  it('should refresh the list once after typing in the search, not on every keystroke', async () => {
    renderComponent();

    await userEvent.click(await screen.findByRole('button', { name: /filters/i }));
    const search = await screen.findByPlaceholderText(/search logs/i);
    await waitFor(() => expect(mockedApiClient.get).toHaveBeenCalledTimes(1));

    await userEvent.type(search, 'abc');

    await waitFor(() => expect(mockedApiClient.get).toHaveBeenCalledTimes(2));
    expect(mockedApiClient.get).toHaveBeenLastCalledWith(expect.stringContaining('search=abc'));
  });

  it('should show a stored SSO error code as its translated message', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [
          createMockAuditLog({
            eventType: 'sso_login_failed',
            eventTypeLabel: 'SSO login failed',
            eventDescription: 'OIDC login failed',
            success: false,
            errorMessage: 'account_mismatch',
          }),
        ],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    await userEvent.click(await screen.findByText(/SSO login failed/i));

    expect(
      await screen.findByText('You signed in with a different account than the one you entered. Please try again.')
    ).toBeInTheDocument();
    expect(screen.queryByText('account_mismatch')).not.toBeInTheDocument();
  });

  it('should toggle filters panel', async () => {
    renderComponent();

    await userEvent.click(await screen.findByRole('button', { name: /filters/i }));

    expect(await screen.findByPlaceholderText(/search logs/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /apply filters/i })).toBeInTheDocument();
  });

  it('should expand log entry to show details', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [createMockAuditLog({ eventDescription: 'Test description', connectionName: 'Okta Prod' })],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    const logEntry = await screen.findByText(/SSO login success/i);
    await userEvent.click(logEntry);

    expect(await screen.findByText('Okta Prod')).toBeInTheDocument();
    expect(screen.queryByText('Test description')).not.toBeInTheDocument();
  });

  it('should show curated KSeF details instead of raw metadata', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [
          createMockAuditLog({
            eventType: 'ksef_token_saved',
            eventTypeLabel: 'KSeF Token Saved',
            eventDescription: 'KSeF token saved',
            metadata: { tokenHint: 'c4f6', status: 'VALID', created: true },
          }),
        ],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    await userEvent.click(await screen.findByText('KSeF token saved', { selector: 'span' }));

    expect(await screen.findByText('••••c4f6')).toBeInTheDocument();
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.queryByText(/"tokenHint"/)).not.toBeInTheDocument();
  });

  it('should show the token ending and removal action for deleted KSeF tokens', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [
          createMockAuditLog({
            eventType: 'ksef_token_deleted',
            eventTypeLabel: 'KSeF Token Deleted',
            eventDescription: 'KSeF token removed',
            metadata: { tokenHint: 'c4f6' },
          }),
        ],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    await userEvent.click(await screen.findByText('KSeF token removed', { selector: 'span' }));

    expect(await screen.findByText('••••c4f6')).toBeInTheDocument();
    expect(screen.getByText('Token removed')).toBeInTheDocument();
  });

  it('should not make log rows without details expandable', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [createMockAuditLog({ connectionName: null, ipAddress: null, errorMessage: '' })],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    const row = await screen.findByText(/SSO login success/i);
    expect(row.closest('button')).toBeDisabled();
  });

  it('should show failed event with failed styling', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: [createMockAuditLog({ success: false, eventType: 'sso_login_failed', eventTypeLabel: 'SSO login failed' })],
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        pageSize: 20,
        hasMore: false,
        hasPrevious: false,
      },
    });

    renderComponent();

    expect(await screen.findByText(/SSO login failed/i)).toBeInTheDocument();
  });

  it('should show clear filters button when filters panel is open', async () => {
    renderComponent();

    await userEvent.click(await screen.findByRole('button', { name: /filters/i }));

    expect(await screen.findByRole('button', { name: /clear filters/i })).toBeInTheDocument();
  });

  it('should show pagination when multiple pages exist', async () => {
    mockedApiClient.get.mockResolvedValue({
      data: {
        logs: Array(20).fill(null).map((_, i) => createMockAuditLog({ id: `log-${i}` })),
        totalCount: 50,
        totalPages: 3,
        currentPage: 1,
        pageSize: 20,
        hasMore: true,
        hasPrevious: false,
      },
    });

    renderComponent();

    expect(await screen.findByText(/50 events/i)).toBeInTheDocument();
  });
});
