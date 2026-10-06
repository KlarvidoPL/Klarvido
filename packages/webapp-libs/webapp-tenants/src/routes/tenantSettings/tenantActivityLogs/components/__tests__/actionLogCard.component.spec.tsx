import { TenantUserRole } from '@sb/webapp-api-client';
import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { Locale, formatTranslationMessages } from '@sb/webapp-core/config/i18n';
import arMessages from '@sb/webapp-core/translations/ar.json';
import deMessages from '@sb/webapp-core/translations/de.json';
import enMessages from '@sb/webapp-core/translations/en.json';
import esMessages from '@sb/webapp-core/translations/es.json';
import frMessages from '@sb/webapp-core/translations/fr.json';
import hiMessages from '@sb/webapp-core/translations/hi.json';
import plMessages from '@sb/webapp-core/translations/pl.json';
import zhMessages from '@sb/webapp-core/translations/zh.json';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { RoutesConfig } from '../../../../../config/routes';
import { createPermissionsMock } from '../../../../../tests/factories/tenant';
import { membershipFactory, tenantFactory } from '../../../../../tests/factories/tenant';
import { createMockRouterProps, render } from '../../../../../tests/utils/rendering';
import { allActionLogsQuery } from '../../tenantActivityLogs.graphql';
import { ActionLogCard } from '../actionLogCard';

const TENANT_ID = 'tenant-activity-logs-1';

const createActionLogsMock = (logs: Array<Record<string, unknown>> = [], totalCount = 0) => {
  return composeMockedQueryResult(allActionLogsQuery, {
    variables: {
      tenantId: TENANT_ID,
      first: 20,
      after: null,
    },
    data: {
      allActionLogs: {
        edges: logs.map((log) => ({
          node: {
            __typename: 'ActionLogType',
            id: log.id || 'log-1',
            actionType: log.actionType || 'CREATE',
            entityType: log.entityType || 'client',
            entityId: log.entityId || 'entity-1',
            entityName: log.entityName || null,
            actorType: log.actorType || 'USER',
            actorEmail: log.actorEmail || 'user@example.com',
            changes: log.changes || null,
            metadata: log.metadata || null,
            createdAt: log.createdAt || new Date().toISOString(),
          },
        })),
        pageInfo: { hasNextPage: false, endCursor: null, __typename: 'PageInfo' },
        totalCount,
      },
    },
  });
};

jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  usePermissionCheck: (perm: string) => ({
    hasPermission: perm === 'security.logs.export',
    loading: false,
  }),
}));

describe('ActionLogCard: Component', () => {
  it('should render disabled state when logging is off', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: false,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view', 'security.logs.export']),
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    render(<ActionLogCard />, { apolloMocks, routerProps });

    expect(await screen.findByText(/activity logging is disabled/i)).toBeInTheDocument();
  });

  it('should render empty state when logging is on and no logs', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const actionLogsMock = createActionLogsMock([], 0);
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view']),
      actionLogsMock,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    const { waitForApolloMocks } = render(<ActionLogCard />, { apolloMocks, routerProps });
    await waitForApolloMocks();

    expect(await screen.findByText(/no activity yet/i)).toBeInTheDocument();
  });

  it('should render log entries when logs exist', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const actionLogsMock = createActionLogsMock(
      [
        {
          id: 'log-1',
          actionType: 'CREATE',
          entityType: 'client',
          entityName: 'Acme Corp',
          actorEmail: 'admin@example.com',
        },
      ],
      1
    );
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view']),
      actionLogsMock,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    const { waitForApolloMocks } = render(<ActionLogCard />, { apolloMocks, routerProps });
    await waitForApolloMocks();

    expect(await screen.findByText(/created/i)).toBeInTheDocument();
    expect(await screen.findByText(/client/i)).toBeInTheDocument();
    expect(await screen.findByText(/acme corp/i)).toBeInTheDocument();
  });

  it.each([
    ['tenant', 'Organization'],
    ['organization_role', 'Organization role'],
    ['tenant_membership', 'Organization member'],
  ])('displays a translated label for %s', async (entityType, label) => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const { waitForApolloMocks } = render(<ActionLogCard />, {
      apolloMocks: [
        fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
        createPermissionsMock(TENANT_ID, ['security.logs.view']),
        createActionLogsMock([{ entityType, actionType: 'UPDATE' }], 1),
      ],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID }),
    });
    await waitForApolloMocks();
    expect(await screen.findByText(`Updated ${label}`)).toBeInTheDocument();
  });

  it('translates operation titles and background actors into Polish', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const { waitForApolloMocks } = render(<ActionLogCard />, {
      intlLocale: Locale.POLISH,
      intlMessages: formatTranslationMessages(Locale.POLISH, plMessages),
      apolloMocks: [
        fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
        createPermissionsMock(TENANT_ID, ['security.logs.view']),
        createActionLogsMock(
          [
            {
              entityType: 'backup',
              actionType: 'CREATE',
              actorType: 'SYSTEM:scheduled_task',
              actorEmail: '',
              metadata: { operation: 'backup_failed', status: 'FAILED' },
            },
          ],
          1
        ),
      ],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID }),
    });
    await waitForApolloMocks();
    expect(await screen.findByText('Nie udało się utworzyć kopii zapasowej')).toBeInTheDocument();
    expect(await screen.findByText(/System \(zadanie w tle\)/)).toBeInTheDocument();
  });

  it.each([
    [Locale.ENGLISH, enMessages],
    [Locale.POLISH, plMessages],
    [Locale.GERMAN, deMessages],
    [Locale.FRENCH, frMessages],
    [Locale.SPANISH, esMessages],
    [Locale.CHINESE, zhMessages],
    [Locale.HINDI, hiMessages],
    [Locale.ARABIC, arMessages],
  ])('includes translated new entity filter options in %s', async (locale, messages) => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const { waitForApolloMocks } = render(<ActionLogCard />, {
      intlLocale: locale,
      intlMessages: formatTranslationMessages(locale, messages),
      apolloMocks: [
        fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
        createPermissionsMock(TENANT_ID, ['security.logs.view']),
        createActionLogsMock([], 0),
      ],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID }),
    });
    await waitForApolloMocks();
    await userEvent.click(
      screen.getByRole('button', { name: messages['Activity Logs / Filters button'].defaultMessage })
    );
    await userEvent.click(
      screen.getByRole('combobox', { name: messages['Activity Logs / Filter Entity Type'].defaultMessage })
    );
    for (const entity of [
      'tenant_invitation',
      'backup_config',
      'backup',
      'backup_restore',
      'activity_log_export',
      'crud_item',
      'tenant',
      'organization_role',
      'tenant_membership',
    ]) {
      expect(
        screen.getByRole('option', {
          name: messages[`Activity Logs / Entity / ${entity}` as keyof typeof messages].defaultMessage,
          exact: true,
        })
      ).toBeInTheDocument();
    }
  });

  it.each([
    [Locale.ENGLISH, enMessages],
    [Locale.POLISH, plMessages],
    [Locale.GERMAN, deMessages],
    [Locale.FRENCH, frMessages],
    [Locale.SPANISH, esMessages],
    [Locale.CHINESE, zhMessages],
    [Locale.HINDI, hiMessages],
    [Locale.ARABIC, arMessages],
  ])('translates expanded detail fields and enum values in %s', async (locale, messages) => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const { waitForApolloMocks } = render(<ActionLogCard />, {
      intlLocale: locale,
      intlMessages: formatTranslationMessages(locale, messages),
      apolloMocks: [
        fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
        createPermissionsMock(TENANT_ID, ['security.logs.view']),
        createActionLogsMock(
          [
            {
              id: 'role-details',
              entityType: 'organization_role',
              entityName: 'Role detail sample',
              changes: {
                permissions: { old: [], new: ['org.settings.edit', 'org.delete'] },
                color: { old: null, new: 'blue' },
              },
            },
            {
              id: 'company-details',
              entityType: 'tenant',
              entityName: 'Company detail sample',
              changes: {
                address: { old: 'Original address', new: 'Changed address' },
                vat_status: { old: 'ACTIVE', new: 'NOT_REGISTERED' },
                company_name: { old: 'Acme', new: 'Acme Ltd' },
              },
            },
            {
              id: 'export-details',
              entityType: 'activity_log_export',
              entityName: 'Export detail sample',
              actorType: 'SYSTEM_SCHEDULED_TASK',
              metadata: { operation: 'export_completed', status: 'completed', log_count: 10, filters: {} },
            },
            {
              id: 'settings-details',
              entityType: 'tenant_settings',
              entityName: 'Action Logging',
              actionType: 'SETTINGS_CHANGE',
              changes: { action_logging_enabled: { old: false, new: true } },
            },
          ],
          4
        ),
      ],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID }),
    });
    await waitForApolloMocks();
    await userEvent.click(screen.getByRole('button', { name: /Role detail sample/ }));
    expect(
      screen.getByText(messages['Roles / Permission / org.settings.edit / Name'].defaultMessage)
    ).toBeInTheDocument();
    expect(screen.getByText(messages['Roles / Permission / org.delete / Name'].defaultMessage)).toBeInTheDocument();
    expect(screen.getByText(messages['Roles / Color / Blue'].defaultMessage)).toBeInTheDocument();
    expect(screen.getByText(messages['Activity Logs / Detail / none'].defaultMessage)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Company detail sample/ }));
    expect(screen.getByText(messages['Tenant form / Field name / Address'].defaultMessage + ':')).toBeInTheDocument();
    expect(
      screen.getByText(messages['Tenant form / Field name / Company name'].defaultMessage + ':')
    ).toBeInTheDocument();
    expect(screen.getByText(messages['Tenant form / VAT status active'].defaultMessage)).toBeInTheDocument();
    expect(screen.getByText(messages['Tenant form / VAT status not registered'].defaultMessage)).toBeInTheDocument();
    expect(screen.getByText('Changed address')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Export detail sample/ }));
    expect(screen.getByText(messages['Activity Logs / Detail / completed'].defaultMessage)).toBeInTheDocument();
    expect(screen.getByText(messages['Activity Logs / Detail / log_count'].defaultMessage + ':')).toBeInTheDocument();
    expect(screen.queryByText('SYSTEM_SCHEDULED_TASK')).not.toBeInTheDocument();
    expect(
      screen.getAllByText(
        new RegExp(
          messages['Activity Logs / Actor / SYSTEM:scheduled_task'].defaultMessage.replace(
            /[.*+?^${}()|[\]\\]/g,
            '\\$&'
          )
        )
      ).length
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(messages['Activity Logs / Detail / organization_settings_changed'].defaultMessage)
    ).toBeInTheDocument();
    expect(screen.queryByText('"Action Logging"')).not.toBeInTheDocument();
  });

  it.each([
    [{ role: 'MEMBER', roles: ['Owner', 'Member'] }, ['Właściciel', 'Członek']],
    [{ role: 'MEMBER', roles: [] }, ['Członek']],
    [
      {
        roles: [
          { name: 'Owner', system_role_type: 'OWNER' },
          { name: 'Auditor', system_role_type: '' },
        ],
      },
      ['Właściciel', 'Auditor'],
    ],
    [{ roles: [{ name: 'Owner', system_role_type: '' }] }, ['Owner']],
  ])('shows one accurate invitation roles list for %j', async (metadata, expected) => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const { waitForApolloMocks } = render(<ActionLogCard />, {
      intlLocale: Locale.POLISH,
      intlMessages: formatTranslationMessages(Locale.POLISH, plMessages),
      apolloMocks: [
        fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
        createPermissionsMock(TENANT_ID, ['security.logs.view']),
        createActionLogsMock(
          [
            {
              entityType: 'tenant_invitation',
              entityName: 'invitee@example.com',
              metadata: { ...metadata, operation: 'invitation_sent' },
            },
          ],
          1
        ),
      ],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID }),
    });
    await waitForApolloMocks();
    await userEvent.click(screen.getByRole('button', { name: /invitee@example.com/ }));
    expect(screen.queryByText('Rola:')).not.toBeInTheDocument();
    expect(screen.getByText('Role:')).toBeInTheDocument();
    for (const label of expected) expect(screen.getByText(label)).toBeInTheDocument();
  });

  it.each([
    ['tenant_invitation', 'Organization invitation'],
    ['backup_config', 'Backup settings'],
    ['backup', 'Backup'],
    ['backup_restore', 'Backup restore'],
    ['activity_log_export', 'Activity log export'],
    ['crud_item', 'CRUD item'],
  ])('filters the query when selecting %s', async (entityType, label) => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const filtered = createActionLogsMock([{ entityType, entityName: 'Filtered activity' }], 1);
    filtered.request.variables = { ...filtered.request.variables, entityType };
    render(<ActionLogCard />, {
      apolloMocks: [
        fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
        createPermissionsMock(TENANT_ID, ['security.logs.view']),
        createActionLogsMock([], 0),
        filtered,
      ],
      routerProps: createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID }),
    });
    await userEvent.click(await screen.findByRole('button', { name: /Filters/i }));
    await userEvent.click(screen.getByRole('combobox', { name: 'Entity Type' }));
    await userEvent.click(screen.getByRole('option', { name: label, exact: true }));
    expect(await screen.findByText('"Filtered activity"')).toBeInTheDocument();
  });

  it('should toggle filters panel', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const actionLogsMock = createActionLogsMock([], 0);
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view']),
      actionLogsMock,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    const { waitForApolloMocks } = render(<ActionLogCard />, { apolloMocks, routerProps });
    await waitForApolloMocks();

    await userEvent.click(await screen.findByRole('button', { name: /filters/i }));

    expect(await screen.findByPlaceholderText(/search logs/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /apply filters/i })).toBeInTheDocument();
  });

  it('should expand log entry to show details', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const actionLogsMock = createActionLogsMock(
      [
        {
          id: 'log-1',
          actionType: 'CREATE',
          entityType: 'client',
          entityId: 'entity-123',
          entityName: 'Acme Corp',
          actorEmail: 'admin@example.com',
        },
      ],
      1
    );
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view']),
      actionLogsMock,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    const { waitForApolloMocks } = render(<ActionLogCard />, { apolloMocks, routerProps });
    await waitForApolloMocks();

    const logEntry = await screen.findByText(/created client/i);
    await userEvent.click(logEntry);

    expect(await screen.findByText(/entity id/i)).toBeInTheDocument();
    expect(await screen.findByText(/entity-123/)).toBeInTheDocument();
  });

  it('should show export button when user has export permission', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const actionLogsMock = createActionLogsMock([{ id: 'log-1', actionType: 'CREATE', entityType: 'client' }], 1);
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view', 'security.logs.export']),
      actionLogsMock,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    const { waitForApolloMocks } = render(<ActionLogCard />, { apolloMocks, routerProps });
    await waitForApolloMocks();

    expect(await screen.findByRole('button', { name: /Export/i })).toBeInTheDocument();
  });

  it('replaces the visible page and supports returning to the first page', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const firstPage = createActionLogsMock([{ id: 'log-first', entityName: 'First page entry' }], 21);
    const lastPage = createActionLogsMock([{ id: 'log-last', entityName: 'Last page entry' }], 21);
    lastPage.request.variables = { ...lastPage.request.variables, after: btoa('arrayconnection:19') };
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view']),
      { ...firstPage, maxUsageCount: 2 },
      lastPage,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });
    render(<ActionLogCard />, { apolloMocks, routerProps });
    expect(await screen.findByText(/First page entry/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(await screen.findByText(/Last page entry/)).toBeInTheDocument();
    expect(screen.queryByText(/First page entry/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'First page' }));
    expect(await screen.findByText(/First page entry/)).toBeInTheDocument();
    expect(screen.queryByText(/Last page entry/)).not.toBeInTheDocument();
  });

  it('should show clear filters button when filters panel is open', async () => {
    const tenant = tenantFactory({
      id: TENANT_ID,
      actionLoggingEnabled: true,
      membership: membershipFactory({ role: TenantUserRole.OWNER }),
    });
    const actionLogsMock = createActionLogsMock([], 0);
    const apolloMocks = [
      fillCommonQueryWithUser(currentUserFactory({ tenants: [tenant] })),
      createPermissionsMock(TENANT_ID, ['security.logs.view']),
      actionLogsMock,
    ];
    const routerProps = createMockRouterProps(RoutesConfig.tenant.settings.activityLogs, { tenantId: TENANT_ID });

    const { waitForApolloMocks } = render(<ActionLogCard />, { apolloMocks, routerProps });
    await waitForApolloMocks();

    await userEvent.click(await screen.findByRole('button', { name: /filters/i }));

    expect(await screen.findByRole('button', { name: /clear filters/i })).toBeInTheDocument();
  });
});
