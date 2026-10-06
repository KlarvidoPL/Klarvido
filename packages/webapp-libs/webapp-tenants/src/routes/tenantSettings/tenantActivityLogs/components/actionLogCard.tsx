import { useMutation, useQuery } from '@apollo/client/react';
import { getFragmentData } from '@sb/webapp-api-client/graphql';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { DatePicker } from '@sb/webapp-core/components/ui/datePicker';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@sb/webapp-core/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@sb/webapp-core/components/ui/tooltip';
import { cn } from '@sb/webapp-core/lib/utils';
import { useToast } from '@sb/webapp-core/toast';
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronsLeft,
  ChevronsRight,
  Download,
  Edit,
  Filter,
  History,
  Import,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Trash2,
  User,
  Zap,
} from 'lucide-react';
import { Fragment, useEffect, useMemo, useState } from 'react';
import { FormattedMessage, type IntlShape, defineMessages, useIntl } from 'react-intl';

import {
  VatStatus,
  useVatStatusLabels,
} from '../../../../components/companyDetailsFields/companyDetailsFields.component';
import { usePermissionCheck } from '../../../../hooks';
import { useCurrentTenant } from '../../../../providers';
import { getPermissionDisplay } from '../../../../utils/permissionDisplay';
import { actionLogFragment, allActionLogsQuery, exportActionLogsMutation } from '../tenantActivityLogs.graphql';

interface Filters {
  entityType: string;
  actionType: string;
  actorEmail: string;
  fromDatetime: string;
  toDatetime: string;
  search: string;
}

const ACTION_TYPE_ICONS: Record<string, React.ReactNode> = {
  CREATE: <Plus className="h-4 w-4" />,
  UPDATE: <Edit className="h-4 w-4" />,
  DELETE: <Trash2 className="h-4 w-4" />,
  SETTINGS_CHANGE: <Settings className="h-4 w-4" />,
  IMPORT: <Import className="h-4 w-4" />,
  SYNC: <RefreshCw className="h-4 w-4" />,
  BULK_DELETE: <Trash2 className="h-4 w-4" />,
};

const ACTION_TYPE_LABELS = defineMessages({
  CREATE: { id: 'Activity Logs / Action / CREATE', defaultMessage: 'Created' },
  UPDATE: { id: 'Activity Logs / Action / UPDATE', defaultMessage: 'Updated' },
  DELETE: { id: 'Activity Logs / Action / DELETE', defaultMessage: 'Deleted' },
  SETTINGS_CHANGE: { id: 'Activity Logs / Action / SETTINGS_CHANGE', defaultMessage: 'Settings Changed' },
  IMPORT: { id: 'Activity Logs / Action / IMPORT', defaultMessage: 'Imported' },
  SYNC: { id: 'Activity Logs / Action / SYNC', defaultMessage: 'Synced' },
  BULK_DELETE: { id: 'Activity Logs / Action / BULK_DELETE', defaultMessage: 'Bulk Deleted' },
});

const ACTION_TYPE_COLORS: Record<string, string> = {
  CREATE: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  UPDATE: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  DELETE: 'bg-red-500/10 text-red-600 dark:text-red-400',
  SETTINGS_CHANGE: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  IMPORT: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  SYNC: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400',
  BULK_DELETE: 'bg-red-500/10 text-red-600 dark:text-red-400',
};

const ACTION_TYPE_BORDERS: Record<string, string> = {
  CREATE: 'border-l-emerald-500',
  UPDATE: 'border-l-blue-500 dark:border-l-blue-400',
  DELETE: 'border-l-destructive bg-destructive/5 dark:border-l-red-400 dark:bg-red-400/5',
  SETTINGS_CHANGE: 'border-l-purple-500 dark:border-l-purple-400',
  IMPORT: 'border-l-amber-500 dark:border-l-amber-400',
  SYNC: 'border-l-cyan-500 dark:border-l-cyan-400',
  BULK_DELETE: 'border-l-destructive bg-destructive/5 dark:border-l-red-400 dark:bg-red-400/5',
};

const ENTITY_TYPE_LABELS = defineMessages({
  tenant_invitation: { id: 'Activity Logs / Entity / tenant_invitation', defaultMessage: 'Organization invitation' },
  backup_config: { id: 'Activity Logs / Entity / backup_config', defaultMessage: 'Backup settings' },
  backup: { id: 'Activity Logs / Entity / backup', defaultMessage: 'Backup' },
  backup_restore: { id: 'Activity Logs / Entity / backup_restore', defaultMessage: 'Backup restore' },
  activity_log_export: { id: 'Activity Logs / Entity / activity_log_export', defaultMessage: 'Activity log export' },
  crud_item: { id: 'Activity Logs / Entity / crud_item', defaultMessage: 'CRUD item' },
  tenant: { id: 'Activity Logs / Entity / tenant', defaultMessage: 'Organization' },
  organization_role: { id: 'Activity Logs / Entity / organization_role', defaultMessage: 'Organization role' },
  tenant_membership: { id: 'Activity Logs / Entity / tenant_membership', defaultMessage: 'Organization member' },
  sso_connection: { id: 'Activity Logs / Entity / sso_connection', defaultMessage: 'SSO connection' },
  scim_token: { id: 'Activity Logs / Entity / scim_token', defaultMessage: 'SCIM token' },
  subscription: { id: 'Activity Logs / Entity / subscription', defaultMessage: 'Subscription' },
  payment_method: { id: 'Activity Logs / Entity / payment_method', defaultMessage: 'Payment method' },
  client: { id: 'Activity Logs / Entity / client', defaultMessage: 'Client' },
  project: { id: 'Activity Logs / Entity / project', defaultMessage: 'Project' },
  person: { id: 'Activity Logs / Entity / person', defaultMessage: 'Person' },
  role: { id: 'Activity Logs / Entity / role', defaultMessage: 'Role' },
  revenue_line: { id: 'Activity Logs / Entity / revenue_line', defaultMessage: 'Revenue' },
  cost_line: { id: 'Activity Logs / Entity / cost_line', defaultMessage: 'Cost' },
  fx_rate: { id: 'Activity Logs / Entity / fx_rate', defaultMessage: 'FX Rate' },
  assignment: { id: 'Activity Logs / Entity / assignment', defaultMessage: 'Assignment' },
  iteration: { id: 'Activity Logs / Entity / iteration', defaultMessage: 'Iteration' },
  invoice: { id: 'Activity Logs / Entity / invoice', defaultMessage: 'Invoice' },
  deal: { id: 'Activity Logs / Entity / deal', defaultMessage: 'Deal' },
  settings: { id: 'Activity Logs / Entity / settings', defaultMessage: 'Settings' },
  tenant_settings: { id: 'Activity Logs / Entity / tenant_settings', defaultMessage: 'Organization settings' },
  ksef_credential: { id: 'Activity Logs / Entity / ksef_credential', defaultMessage: 'KSeF token' },
});

const FIELD_LABELS = defineMessages({
  actor_email: { id: 'Activity Logs / Filter User', defaultMessage: 'User' },
  entity_type: { id: 'Activity Logs / Filter Entity Type', defaultMessage: 'Entity Type' },
  action_type: { id: 'Activity Logs / Filter Action Type', defaultMessage: 'Action Type' },
  search: { id: 'Activity Logs / Filter Search', defaultMessage: 'Search' },
  from_datetime: { id: 'Activity Logs / Filter From DateTime', defaultMessage: 'From' },
  to_datetime: { id: 'Activity Logs / Filter To DateTime', defaultMessage: 'To' },

  address: { id: 'Tenant form / Field name / Address', defaultMessage: 'Address' },
  company_name: { id: 'Tenant form / Field name / Company name', defaultMessage: 'Company name' },
  vat_status: { id: 'Tenant form / Field name / VAT status', defaultMessage: 'VAT status' },
  nip: { id: 'Tenant form / NIP label', defaultMessage: 'NIP' },
  regon: { id: 'Tenant form / Field name / REGON', defaultMessage: 'REGON' },

  name: { id: 'Activity Logs / Field / name', defaultMessage: 'Name' },
  description: { id: 'Activity Logs / Field / description', defaultMessage: 'Description' },
  color: { id: 'Activity Logs / Field / color', defaultMessage: 'Color' },
  permissions: { id: 'Activity Logs / Field / permissions', defaultMessage: 'Permissions' },
  enabled: { id: 'Activity Logs / Field / enabled', defaultMessage: 'Enabled' },
  backup_interval_hours: {
    id: 'Activity Logs / Field / backup_interval_hours',
    defaultMessage: 'Backup interval (hours)',
  },
  retention_days: { id: 'Activity Logs / Field / retention_days', defaultMessage: 'Retention (days)' },
  email_recipients: { id: 'Activity Logs / Field / email_recipients', defaultMessage: 'Email recipients' },
  selected_modules: { id: 'Activity Logs / Field / selected_modules', defaultMessage: 'Selected modules' },
  selected_models: { id: 'Activity Logs / Field / selected_models', defaultMessage: 'Selected models' },
  excluded_models: { id: 'Activity Logs / Field / excluded_models', defaultMessage: 'Excluded models' },
  action_logging_enabled: { id: 'Activity Logs / Field / action_logging_enabled', defaultMessage: 'Activity logging' },
  default_payment_method: {
    id: 'Activity Logs / Field / default_payment_method',
    defaultMessage: 'Default payment method',
  },
  plan: { id: 'Activity Logs / Field / plan', defaultMessage: 'Subscription plan' },
});

const COLOR_LABELS = defineMessages({
  blue: { id: 'Roles / Color / Blue', defaultMessage: 'Blue' },
  green: { id: 'Roles / Color / Green', defaultMessage: 'Green' },
  red: { id: 'Roles / Color / Red', defaultMessage: 'Red' },
  yellow: { id: 'Roles / Color / Yellow', defaultMessage: 'Yellow' },
  purple: { id: 'Roles / Color / Purple', defaultMessage: 'Purple' },
  orange: { id: 'Roles / Color / Orange', defaultMessage: 'Orange' },
  pink: { id: 'Roles / Color / Pink', defaultMessage: 'Pink' },
  teal: { id: 'Roles / Color / Teal', defaultMessage: 'Teal' },
  gray: { id: 'Roles / Color / Gray', defaultMessage: 'Gray' },
});

const DETAIL_LABELS = defineMessages({
  status: { id: 'Activity Logs / Detail / status', defaultMessage: 'Status' },
  log_count: { id: 'Activity Logs / Detail / log_count', defaultMessage: 'Number of logs' },
  operation: { id: 'Activity Logs / Detail / operation', defaultMessage: 'Operation' },
  filters: { id: 'Activity Logs / Detail / filters', defaultMessage: 'Filters' },
  config_id: { id: 'Activity Logs / Detail / config_id', defaultMessage: 'Configuration ID' },
  backup_id: { id: 'Activity Logs / Detail / backup_id', defaultMessage: 'Backup ID' },
  conflict_strategy: { id: 'Activity Logs / Detail / conflict_strategy', defaultMessage: 'Conflict strategy' },
  model_counts: { id: 'Activity Logs / Detail / model_counts', defaultMessage: 'Record counts' },
  created: { id: 'Activity Logs / Detail / created', defaultMessage: 'Created' },
  updated: { id: 'Activity Logs / Detail / updated', defaultMessage: 'Updated' },
  skipped: { id: 'Activity Logs / Detail / skipped', defaultMessage: 'Skipped' },
  failed: { id: 'Activity Logs / Detail / failed', defaultMessage: 'Failed' },
  reason: { id: 'Activity Logs / Detail / reason', defaultMessage: 'Reason' },
  token_hint: { id: 'Activity Logs / Detail / token_hint', defaultMessage: 'Token ending' },
  token_name: { id: 'Activity Logs / Detail / token_name', defaultMessage: 'Token name' },
  error_code: { id: 'Activity Logs / Detail / error_code', defaultMessage: 'Error code' },
  billing_email: { id: 'Activity Logs / Detail / billing_email', defaultMessage: 'Billing email' },
  slug: { id: 'Activity Logs / Detail / slug', defaultMessage: 'Slug' },
  type: { id: 'Activity Logs / Detail / type', defaultMessage: 'Type' },
  role: { id: 'Activity Logs / Detail / role', defaultMessage: 'Role' },
  roles: { id: 'Activity Logs / Detail / roles', defaultMessage: 'Roles' },
  none: { id: 'Activity Logs / Detail / none', defaultMessage: 'None' },
  pending: { id: 'Activity Logs / Detail / pending', defaultMessage: 'Pending' },
  processing: { id: 'Activity Logs / Detail / processing', defaultMessage: 'Processing' },
  completed: { id: 'Activity Logs / Detail / completed', defaultMessage: 'Completed' },
  partially_completed: { id: 'Activity Logs / Detail / partially_completed', defaultMessage: 'Partially completed' },
  valid: { id: 'Activity Logs / Detail / valid', defaultMessage: 'Valid' },
  invalid: { id: 'Activity Logs / Detail / invalid', defaultMessage: 'Invalid' },
  unverified: { id: 'Activity Logs / Detail / unverified', defaultMessage: 'Unverified' },
  retention: { id: 'Activity Logs / Detail / retention', defaultMessage: 'Retention policy' },
  organization_settings_changed: {
    id: 'Activity Logs / Detail / organization_settings_changed',
    defaultMessage: 'Organization settings changed',
  },
});

const OPERATION_LABELS = defineMessages({
  invitation_sent: { id: 'Activity Logs / Operation / invitation_sent', defaultMessage: 'Invitation sent' },
  invitation_resent: { id: 'Activity Logs / Operation / invitation_resent', defaultMessage: 'Invitation resent' },
  invitation_accepted: { id: 'Activity Logs / Operation / invitation_accepted', defaultMessage: 'Invitation accepted' },
  invitation_declined: { id: 'Activity Logs / Operation / invitation_declined', defaultMessage: 'Invitation declined' },
  backup_settings_changed: {
    id: 'Activity Logs / Operation / backup_settings_changed',
    defaultMessage: 'Backup settings changed',
  },
  backup_requested: { id: 'Activity Logs / Operation / backup_requested', defaultMessage: 'Backup requested' },
  backup_deleted: { id: 'Activity Logs / Operation / backup_deleted', defaultMessage: 'Backup deleted' },
  backup_downloaded: { id: 'Activity Logs / Operation / backup_downloaded', defaultMessage: 'Backup downloaded' },
  backup_completed: { id: 'Activity Logs / Operation / backup_completed', defaultMessage: 'Backup completed' },
  backup_failed: { id: 'Activity Logs / Operation / backup_failed', defaultMessage: 'Backup failed' },
  restore_requested: { id: 'Activity Logs / Operation / restore_requested', defaultMessage: 'Restore requested' },
  restore_completed: { id: 'Activity Logs / Operation / restore_completed', defaultMessage: 'Restore completed' },
  restore_partial: { id: 'Activity Logs / Operation / restore_partial', defaultMessage: 'Restore partially completed' },
  restore_failed: { id: 'Activity Logs / Operation / restore_failed', defaultMessage: 'Restore failed' },
  export_requested: {
    id: 'Activity Logs / Operation / export_requested',
    defaultMessage: 'Activity log export requested',
  },
  export_completed: {
    id: 'Activity Logs / Operation / export_completed',
    defaultMessage: 'Activity log export completed',
  },
  export_failed: { id: 'Activity Logs / Operation / export_failed', defaultMessage: 'Activity log export failed' },
  logging_enabled: { id: 'Activity Logs / Operation / logging_enabled', defaultMessage: 'Activity logging enabled' },
  logging_disabled: { id: 'Activity Logs / Operation / logging_disabled', defaultMessage: 'Activity logging disabled' },
  default_payment_method_changed: {
    id: 'Activity Logs / Operation / default_payment_method_changed',
    defaultMessage: 'Default payment method changed',
  },
  subscription_changed: {
    id: 'Activity Logs / Operation / subscription_changed',
    defaultMessage: 'Subscription plan changed',
  },
});

const ACTOR_LABELS = defineMessages({
  USER: { id: 'Activity Logs / Actor / USER', defaultMessage: 'User' },
  AI_AGENT: { id: 'Activity Logs / Actor / AI_AGENT', defaultMessage: 'AI agent' },
  SUPERUSER: { id: 'Activity Logs / Actor / SUPERUSER', defaultMessage: 'Superuser' },
  'SYSTEM:sync': { id: 'Activity Logs / Actor / SYSTEM:sync', defaultMessage: 'System (sync)' },
  'SYSTEM:import': { id: 'Activity Logs / Actor / SYSTEM:import', defaultMessage: 'System (import)' },
  'SYSTEM:scheduled_task': {
    id: 'Activity Logs / Actor / SYSTEM:scheduled_task',
    defaultMessage: 'System (background task)',
  },
  'SYSTEM:migration': { id: 'Activity Logs / Actor / SYSTEM:migration', defaultMessage: 'System (migration)' },
});

const getActorLabel = (intl: IntlShape, actorType: string): string => {
  const normalized = actorType.startsWith('SYSTEM_') ? `SYSTEM:${actorType.slice(7).toLowerCase()}` : actorType;
  const message = ACTOR_LABELS[normalized as keyof typeof ACTOR_LABELS];
  return message ? intl.formatMessage(message) : actorType;
};

const getOperationLabel = (intl: IntlShape, metadata: unknown): string | undefined => {
  if (!metadata || typeof metadata !== 'object' || !('operation' in metadata)) return undefined;
  const message = OPERATION_LABELS[metadata.operation as keyof typeof OPERATION_LABELS];
  return message ? intl.formatMessage(message) : undefined;
};

const getEntityLabel = (intl: IntlShape, entityType: string): string => {
  const message = ENTITY_TYPE_LABELS[entityType as keyof typeof ENTITY_TYPE_LABELS];
  return message ? intl.formatMessage(message) : entityType;
};

const getActionIcon = (actionType: string) => {
  return ACTION_TYPE_ICONS[actionType] || <Zap className="h-4 w-4" />;
};

const getActionLabel = (intl: IntlShape, actionType: string): string => {
  const message = ACTION_TYPE_LABELS[actionType as keyof typeof ACTION_TYPE_LABELS];
  return message ? intl.formatMessage(message) : actionType;
};

const DEFAULT_PAGE_SIZE = 20;

export const ActionLogCard = () => {
  const intl = useIntl();
  const vatLabels = useVatStatusLabels();
  const { data: currentTenant } = useCurrentTenant();
  const tenantId = currentTenant?.id;
  const isLoggingEnabled = currentTenant?.actionLoggingEnabled ?? false;

  // Permission check for export
  const { hasPermission: canExport } = usePermissionCheck('security.logs.export');

  // State
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  // Filter state
  const [filters, setFilters] = useState<Filters>({
    entityType: '',
    actionType: '',
    actorEmail: '',
    fromDatetime: '',
    toDatetime: '',
    search: '',
  });

  const [appliedFilters, setAppliedFilters] = useState(filters);
  useEffect(() => {
    if (filters === appliedFilters) return;
    const timeout = setTimeout(() => {
      setCurrentPage(1);
      setExpandedLogId(null);
      setAppliedFilters(filters);
    }, 300);
    return () => clearTimeout(timeout);
  }, [filters, appliedFilters]);

  const hasActiveFilters = useMemo(() => {
    return Object.values(filters).some((v) => v !== '');
  }, [filters]);

  // Convert local datetime string to ISO format for GraphQL
  const toISODatetime = (localDatetime: string) => {
    if (!localDatetime) return undefined;
    return new Date(localDatetime).toISOString();
  };

  const { toast } = useToast();
  const [exportLogs, { loading: exportLoading }] = useMutation(exportActionLogsMutation);

  const { data, loading, refetch } = useQuery(allActionLogsQuery, {
    variables: {
      tenantId: tenantId || '',
      first: DEFAULT_PAGE_SIZE,
      after: currentPage === 1 ? null : btoa(`arrayconnection:${(currentPage - 1) * DEFAULT_PAGE_SIZE - 1}`),
      entityType: appliedFilters.entityType || undefined,
      actionType: appliedFilters.actionType || undefined,
      actorEmail: appliedFilters.actorEmail || undefined,
      fromDatetime: toISODatetime(appliedFilters.fromDatetime),
      toDatetime: toISODatetime(appliedFilters.toDatetime),
      search: appliedFilters.search || undefined,
    },
    skip: !tenantId,
    fetchPolicy: 'cache-and-network',
    notifyOnNetworkStatusChange: true,
  });

  const logs =
    data?.allActionLogs?.edges
      ?.map((edge) => (edge?.node ? getFragmentData(actionLogFragment, edge.node) : null))
      .filter((log): log is NonNullable<typeof log> => log !== null) || [];
  const totalCount = data?.allActionLogs?.totalCount || 0;
  const totalPages = Math.ceil(totalCount / DEFAULT_PAGE_SIZE);

  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleApplyFilters = () => {
    setAppliedFilters(filters);
    setExpandedLogId(null);
    setCurrentPage(1);
    refetch({
      tenantId: tenantId || '',
      first: DEFAULT_PAGE_SIZE,
      after: null,
      entityType: filters.entityType || undefined,
      actionType: filters.actionType || undefined,
      actorEmail: filters.actorEmail || undefined,
      fromDatetime: toISODatetime(filters.fromDatetime),
      toDatetime: toISODatetime(filters.toDatetime),
      search: filters.search || undefined,
    });
  };

  const handleClearFilters = () => {
    const clearedFilters = {
      entityType: '',
      actionType: '',
      actorEmail: '',
      fromDatetime: '',
      toDatetime: '',
      search: '',
    };
    setFilters(clearedFilters);
    setAppliedFilters(clearedFilters);
    setExpandedLogId(null);
    setCurrentPage(1);
    refetch({
      tenantId: tenantId || '',
      first: DEFAULT_PAGE_SIZE,
      after: null,
    });
  };

  const handleRefresh = () => {
    refetch();
  };

  const handlePageChange = (page: number) => {
    if (loading || page < 1 || page > totalPages) return;
    setExpandedLogId(null);
    setCurrentPage(page);
  };

  const handleExport = async () => {
    if (!tenantId) return;

    try {
      const result = await exportLogs({
        variables: {
          tenantId,
          entityType: filters.entityType || undefined,
          actionType: filters.actionType || undefined,
          actorEmail: filters.actorEmail || undefined,
          fromDatetime: toISODatetime(filters.fromDatetime),
          toDatetime: toISODatetime(filters.toDatetime),
          search: filters.search || undefined,
        },
      });

      if (result.data?.exportActionLogs?.ok) {
        toast({
          title: intl.formatMessage({
            defaultMessage: 'Export started',
            id: 'Activity Logs / Export Started Title',
          }),
          description: intl.formatMessage({
            defaultMessage: "We're preparing your export. You'll receive a notification when it's ready to download.",
            id: 'Activity Logs / Export Started Description',
          }),
        });
      }
    } catch (error) {
      toast({
        title: intl.formatMessage({
          defaultMessage: 'Export failed',
          id: 'Activity Logs / Export Failed Title',
        }),
        description: intl.formatMessage({
          defaultMessage: 'There was an error starting the export. Please try again.',
          id: 'Activity Logs / Export Failed Description',
        }),
        variant: 'destructive',
      });
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat(intl.locale, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  };

  const toggleLogExpand = (logId: string) => {
    setExpandedLogId(expandedLogId === logId ? null : logId);
  };

  const getFieldLabel = (field: string): string => {
    const message =
      FIELD_LABELS[field as keyof typeof FIELD_LABELS] ?? DETAIL_LABELS[field as keyof typeof DETAIL_LABELS];
    return message ? intl.formatMessage(message) : field;
  };

  const formatChangeValue = (value: unknown, field: string): React.ReactNode => {
    if (value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length)) {
      return intl.formatMessage(DETAIL_LABELS.none);
    }
    if (typeof value === 'boolean') {
      return intl.formatMessage(
        value
          ? { id: 'Tenant Membersip Entry / Yes', defaultMessage: 'Yes' }
          : { id: 'Tenant Membersip Entry / No', defaultMessage: 'No' }
      );
    }
    if (typeof value === 'number') return intl.formatNumber(value);
    if (Array.isArray(value)) {
      return value.map((item, index) => (
        <Fragment key={index}>
          {index > 0 && ', '}
          <span>{formatChangeValue(item, field)}</span>
        </Fragment>
      ));
    }
    if (field === 'roles' && typeof value === 'object' && 'name' in value) {
      const role = value as { name: string; system_role_type?: string };
      return role.system_role_type ? formatChangeValue(role.system_role_type, 'role') : role.name;
    }
    if (typeof value === 'object') return renderDetails(value as Record<string, unknown>);
    const text = String(value);
    if (field === 'permissions') return getPermissionDisplay(intl, text, text).name;
    if (field === 'role' || field === 'roles') {
      const role = {
        OWNER: { id: 'Tenant roles / Owner', defaultMessage: 'Owner' },
        ADMIN: { id: 'Tenant roles / Admin', defaultMessage: 'Admin' },
        MEMBER: { id: 'Tenant roles / Member', defaultMessage: 'Member' },
      }[text.toUpperCase() as 'OWNER' | 'ADMIN' | 'MEMBER'];
      return role ? intl.formatMessage(role) : text;
    }
    if (field === 'vat_status') return vatLabels[text as VatStatus] ?? text;
    if (field === 'color') {
      const color = COLOR_LABELS[text.toLowerCase() as keyof typeof COLOR_LABELS];
      return color ? intl.formatMessage(color) : text;
    }
    if (field === 'operation') return getOperationLabel(intl, { operation: text }) ?? text;
    if (field === 'status') {
      const message = DETAIL_LABELS[text.toLowerCase() as keyof typeof DETAIL_LABELS];
      return message ? intl.formatMessage(message) : text;
    }
    if (field === 'conflict_strategy') {
      const strategy = {
        SKIP: { id: 'Backup Settings / Strategy Skip Label', defaultMessage: 'Skip existing' },
        UPDATE: { id: 'Backup Settings / Strategy Update Label', defaultMessage: 'Update existing' },
        FAIL: { id: 'Backup Settings / Strategy Fail Label', defaultMessage: 'Fail on conflicts' },
      }[text as 'SKIP' | 'UPDATE' | 'FAIL'];
      return strategy ? intl.formatMessage(strategy) : text;
    }
    if (field === 'reason' && text === 'retention') return intl.formatMessage(DETAIL_LABELS.retention);
    if (field === 'entity_type') return getEntityLabel(intl, text);
    if (field === 'action_type') return getActionLabel(intl, text);
    return text;
  };

  const renderDetails = (details: Record<string, unknown>): React.ReactNode => {
    const normalized = { ...details };
    if ('role' in normalized && 'roles' in normalized) {
      if (!Array.isArray(normalized['roles']) || !normalized['roles'].length) {
        normalized['roles'] = [normalized['role']];
      }
      delete normalized['role'];
    }
    const entries = Object.entries(normalized);
    if (!entries.length) return intl.formatMessage(DETAIL_LABELS.none);
    return (
      <dl className="space-y-2">
        {entries.map(([field, value]) => (
          <div key={field} className="flex flex-col gap-1 sm:flex-row sm:gap-3">
            <dt className="min-w-[140px] shrink-0 text-muted-foreground">{getFieldLabel(field)}:</dt>
            <dd className="min-w-0 break-words">{formatChangeValue(value, field)}</dd>
          </div>
        ))}
      </dl>
    );
  };

  const renderChanges = (changes: Record<string, { old: unknown; new: unknown }>) => {
    if (!changes || Object.keys(changes).length === 0) {
      return null;
    }

    return (
      <div className="space-y-2">
        {Object.entries(changes).map(([field, change]) => (
          <div key={field} className="flex flex-col gap-2 text-sm sm:flex-row">
            <span className="font-medium text-muted-foreground min-w-[100px]">{getFieldLabel(field)}:</span>
            <div className="flex min-w-0 flex-wrap items-center gap-2 break-all">
              {change.old !== null && change.old !== undefined && (
                <span className="flex items-center gap-1 text-red-600 dark:text-red-400 line-through">
                  <ArrowDown className="h-3 w-3" />
                  {formatChangeValue(change.old, field)}
                </span>
              )}
              {change.new !== null && change.new !== undefined && (
                <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                  <ArrowUp className="h-3 w-3" />
                  {formatChangeValue(change.new, field)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  if (!isLoggingEnabled) {
    return (
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
              <History className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <CardTitle className="text-lg">
                <FormattedMessage defaultMessage="Activity Log" id="Activity Logs / Card Header" />
              </CardTitle>
              <CardDescription className="mt-0.5">
                <FormattedMessage
                  defaultMessage="View recent activity in your organization"
                  id="Activity Logs / Card Description"
                />
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 p-8 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted mb-4">
              <History className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="text-base font-semibold mb-1">
              <FormattedMessage defaultMessage="Activity logging is disabled" id="Activity Logs / Disabled title" />
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              <FormattedMessage
                defaultMessage="Enable activity logging above to start tracking changes in your organization."
                id="Activity Logs / Disabled description"
              />
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = [];
    const showPages = 5; // Number of page buttons to show

    if (totalPages <= showPages + 2) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage <= 3) {
        // Near the start
        for (let i = 2; i <= Math.min(showPages, totalPages - 1); i++) {
          pages.push(i);
        }
        if (totalPages > showPages) {
          pages.push('ellipsis');
        }
      } else if (currentPage >= totalPages - 2) {
        // Near the end
        pages.push('ellipsis');
        for (let i = totalPages - showPages + 1; i < totalPages; i++) {
          if (i > 1) pages.push(i);
        }
      } else {
        // In the middle
        pages.push('ellipsis');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) {
          pages.push(i);
        }
        pages.push('ellipsis');
      }

      // Always show last page
      if (!pages.includes(totalPages)) {
        pages.push(totalPages);
      }
    }

    return pages;
  };

  return (
    <TooltipProvider>
      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <History className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle className="text-lg">
                  <FormattedMessage defaultMessage="Activity Log" id="Activity Logs / Card Header" />
                </CardTitle>
                <CardDescription className="mt-0.5">
                  <FormattedMessage
                    defaultMessage="View recent activity in your organization"
                    id="Activity Logs / Card Description"
                  />
                </CardDescription>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={showFilters ? 'secondary' : 'outline'}
                    size="sm"
                    onClick={() => setShowFilters(!showFilters)}
                    className={cn('gap-2', hasActiveFilters && 'border-primary/50')}
                  >
                    <Filter className="h-4 w-4" />
                    <FormattedMessage defaultMessage="Filters" id="Activity Logs / Filters button" />
                    {hasActiveFilters && (
                      <Badge variant="default" className="ml-1 h-5 px-1.5 text-xs">
                        {Object.values(filters).filter((v) => v !== '').length}
                      </Badge>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <FormattedMessage defaultMessage="Filter activity logs" id="Activity Logs / Filters Tooltip" />
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" onClick={handleRefresh} disabled={loading} className="h-9 w-9">
                    <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <FormattedMessage defaultMessage="Refresh" id="Activity Logs / Refresh Tooltip" />
                </TooltipContent>
              </Tooltip>
              {canExport && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleExport}
                      disabled={loading || exportLoading || totalCount === 0}
                      className="gap-2"
                    >
                      {exportLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                      <FormattedMessage defaultMessage="Export" id="Activity Logs / Export button" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <FormattedMessage
                      defaultMessage="Export logs matching current filters"
                      id="Activity Logs / Export Tooltip"
                    />
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="mt-4 rounded-lg border bg-muted/10 p-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {/* Search */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Search" id="Activity Logs / Filter Search" />
                  </label>
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={intl.formatMessage({
                        defaultMessage: 'Search logs...',
                        id: 'Activity Logs / Search placeholder',
                      })}
                      value={filters.search}
                      onChange={(e) => handleFilterChange('search', e.target.value)}
                      className="pl-8"
                    />
                  </div>
                </div>

                {/* Action Type */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Action Type" id="Activity Logs / Filter Action Type" />
                  </label>
                  <Select
                    value={filters.actionType}
                    onValueChange={(value) => handleFilterChange('actionType', value === 'all' ? '' : value)}
                  >
                    <SelectTrigger
                      aria-label={intl.formatMessage({
                        id: 'Activity Logs / Filter Action Type',
                        defaultMessage: 'Action Type',
                      })}
                    >
                      <SelectValue
                        placeholder={intl.formatMessage({
                          defaultMessage: 'All actions',
                          id: 'Activity Logs / All actions placeholder',
                        })}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        <FormattedMessage defaultMessage="All actions" id="Activity Logs / All actions" />
                      </SelectItem>
                      {Object.entries(ACTION_TYPE_LABELS).map(([type, label]) => (
                        <SelectItem key={type} value={type}>
                          {intl.formatMessage(label)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Entity Type */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Entity Type" id="Activity Logs / Filter Entity Type" />
                  </label>
                  <Select
                    value={filters.entityType}
                    onValueChange={(value) => handleFilterChange('entityType', value === 'all' ? '' : value)}
                  >
                    <SelectTrigger
                      aria-label={intl.formatMessage({
                        id: 'Activity Logs / Filter Entity Type',
                        defaultMessage: 'Entity Type',
                      })}
                    >
                      <SelectValue
                        placeholder={intl.formatMessage({
                          defaultMessage: 'All entities',
                          id: 'Activity Logs / All entities placeholder',
                        })}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        <FormattedMessage defaultMessage="All entities" id="Activity Logs / All entities" />
                      </SelectItem>
                      {Object.entries(ENTITY_TYPE_LABELS).map(([type, label]) => (
                        <SelectItem key={type} value={type}>
                          {intl.formatMessage(label)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Actor Email */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="User" id="Activity Logs / Filter User" />
                  </label>
                  <Input
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Filter by email...',
                      id: 'Activity Logs / User email placeholder',
                    })}
                    value={filters.actorEmail}
                    onChange={(e) => handleFilterChange('actorEmail', e.target.value)}
                  />
                </div>

                {/* From Date/Time */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="From" id="Activity Logs / Filter From DateTime" />
                  </label>
                  <DatePicker
                    value={filters.fromDatetime}
                    onChange={(value) => handleFilterChange('fromDatetime', value || '')}
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Select start date and time',
                      id: 'Activity Logs / From Placeholder',
                    })}
                    showTime
                  />
                </div>

                {/* To Date/Time */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="To" id="Activity Logs / Filter To DateTime" />
                  </label>
                  <DatePicker
                    value={filters.toDatetime}
                    onChange={(value) => handleFilterChange('toDatetime', value || '')}
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Select end date and time',
                      id: 'Activity Logs / To Placeholder',
                    })}
                    showTime
                  />
                </div>
              </div>

              {/* Filter Actions */}
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <p className="text-sm text-muted-foreground">
                  <FormattedMessage
                    defaultMessage="{count, plural, =0 {No logs found} one {# log found} other {# logs found}}"
                    id="Activity Logs / Results count"
                    values={{ count: totalCount }}
                  />
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearFilters}
                    disabled={!hasActiveFilters || loading}
                  >
                    <FormattedMessage defaultMessage="Clear filters" id="Activity Logs / Clear filters" />
                  </Button>
                  <Button size="sm" onClick={handleApplyFilters} disabled={loading}>
                    {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    <FormattedMessage defaultMessage="Apply filters" id="Activity Logs / Apply filters" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardHeader>

        <CardContent>
          {loading && logs.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 p-8 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted mb-4">
                <History className="h-7 w-7 text-muted-foreground" />
              </div>
              <h3 className="text-base font-semibold mb-1">
                {hasActiveFilters ? (
                  <FormattedMessage defaultMessage="No logs match your filters" id="Activity Logs / No Filtered Logs" />
                ) : (
                  <FormattedMessage defaultMessage="No activity yet" id="Activity Logs / No Logs" />
                )}
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-4">
                {hasActiveFilters ? (
                  <FormattedMessage
                    defaultMessage="Try adjusting your filters or clearing them to see all logs."
                    id="Activity Logs / No Filtered Logs Hint"
                  />
                ) : (
                  <FormattedMessage
                    defaultMessage="Activity logs will appear here when users make changes to your organization's data."
                    id="Activity Logs / No Logs Hint"
                  />
                )}
              </p>
              {hasActiveFilters && (
                <Button variant="outline" size="sm" onClick={handleClearFilters}>
                  <FormattedMessage defaultMessage="Clear filters" id="Activity Logs / Clear filters link" />
                </Button>
              )}
            </div>
          ) : (
            <div className="relative space-y-4">
              {/* Logs List */}
              <div className={cn('space-y-2', loading && 'opacity-60')}>
                {logs.map((log) => {
                  if (!log) return null;
                  const operation = (log.metadata as { operation?: string } | null)?.operation;
                  const failed = operation?.endsWith('_failed');
                  const actionColor = failed
                    ? ACTION_TYPE_COLORS['DELETE']
                    : ACTION_TYPE_COLORS[log.actionType] || 'bg-muted text-muted-foreground';
                  const isSystemAction = log.actorType !== 'USER';

                  return (
                    <div
                      key={log.id}
                      className={cn(
                        'group rounded-lg border transition-all',
                        'hover:shadow-sm hover:border-t-primary/20 hover:border-r-primary/20 hover:border-b-primary/20',
                        'border-l-2',
                        failed
                          ? ACTION_TYPE_BORDERS['DELETE']
                          : ACTION_TYPE_BORDERS[log.actionType] || 'border-l-border'
                      )}
                    >
                      <button
                        type="button"
                        className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg p-4 text-left"
                        onClick={() => toggleLogExpand(log.id)}
                        aria-expanded={expandedLogId === log.id}
                      >
                        <div className="flex min-w-0 items-start gap-3 sm:items-center sm:gap-4">
                          <div
                            className={cn(
                              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors',
                              actionColor
                            )}
                          >
                            {getActionIcon(log.actionType)}
                          </div>
                          <div className="min-w-0 space-y-1">
                            <div className="flex flex-wrap items-center gap-2 break-words">
                              <span className="font-medium text-sm">
                                {(log.entityType === 'tenant_settings' &&
                                log.changes &&
                                'action_logging_enabled' in log.changes &&
                                !getOperationLabel(intl, log.metadata)
                                  ? intl.formatMessage(DETAIL_LABELS.organization_settings_changed)
                                  : getOperationLabel(intl, log.metadata)) ??
                                  `${getActionLabel(intl, log.actionType)} ${getEntityLabel(intl, log.entityType)}`}
                              </span>
                              {log.entityName && !['tenant_settings', 'settings'].includes(log.entityType) && (
                                <span className="text-muted-foreground">
                                  "
                                  {['Action Logging', 'Subscription Plan', 'Subscription', 'KSeF token'].includes(
                                    log.entityName
                                  )
                                    ? getEntityLabel(intl, log.entityType)
                                    : log.entityName}
                                  "
                                </span>
                              )}
                            </div>
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 break-all text-xs text-muted-foreground">
                              <span>{formatDate(log.createdAt)}</span>
                              <span className="text-muted-foreground/50">•</span>
                              <span className="flex items-center gap-1">
                                {isSystemAction ? (
                                  <>
                                    <Zap className="h-3 w-3" />
                                    {getActorLabel(intl, log.actorType)}
                                    {log.actorEmail && ` · ${log.actorEmail}`}
                                  </>
                                ) : (
                                  <>
                                    <User className="h-3 w-3" />
                                    {log.actorEmail || 'Unknown user'}
                                  </>
                                )}
                              </span>
                            </div>
                          </div>
                        </div>
                        <span
                          className="flex h-8 w-8 shrink-0 items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                          aria-hidden
                        >
                          {expandedLogId === log.id ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </span>
                      </button>

                      {expandedLogId === log.id && (
                        <div className="mx-4 mb-4 border-t pt-4">
                          <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                            <div>
                              <dt className="text-xs font-medium text-muted-foreground mb-1">
                                <FormattedMessage defaultMessage="Entity ID" id="Activity Logs / Entity ID" />
                              </dt>
                              <dd className="break-all font-mono text-xs">{log.entityId}</dd>
                            </div>
                            <div>
                              <dt className="text-xs font-medium text-muted-foreground mb-1">
                                <FormattedMessage defaultMessage="Actor" id="Activity Logs / Actor" />
                              </dt>
                              <dd>
                                {isSystemAction ? (
                                  <Badge variant="secondary" className="text-xs">
                                    {getActorLabel(intl, log.actorType)}
                                  </Badge>
                                ) : (
                                  log.actorEmail
                                )}
                              </dd>
                            </div>
                            {log.changes && Object.keys(log.changes).length > 0 && (
                              <div className="sm:col-span-2">
                                <dt className="text-xs font-medium text-muted-foreground mb-2">
                                  <FormattedMessage defaultMessage="Changes" id="Activity Logs / Changes" />
                                </dt>
                                <dd className="rounded-lg bg-muted/50 p-3">
                                  {renderChanges(log.changes as Record<string, { old: unknown; new: unknown }>)}
                                </dd>
                              </div>
                            )}
                            {log.metadata && Object.keys(log.metadata).length > 0 && (
                              <div className="sm:col-span-2">
                                <dt className="text-xs font-medium text-muted-foreground mb-1">
                                  <FormattedMessage defaultMessage="Additional Details" id="Activity Logs / Details" />
                                </dt>
                                <dd className="rounded-lg bg-muted/50 p-3 text-sm">
                                  {renderDetails(log.metadata as Record<string, unknown>)}
                                </dd>
                              </div>
                            )}
                          </dl>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div
                  className={cn(
                    'flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between',
                    loading && 'opacity-60'
                  )}
                >
                  <p className="text-sm text-muted-foreground">
                    <FormattedMessage
                      defaultMessage="Showing {start}-{end} of {total} events"
                      id="Audit / Pagination summary"
                      values={{
                        start: intl.formatNumber((currentPage - 1) * DEFAULT_PAGE_SIZE + 1),
                        end: intl.formatNumber(
                          Math.min((currentPage - 1) * DEFAULT_PAGE_SIZE + logs.length, totalCount)
                        ),
                        total: intl.formatNumber(totalCount),
                      }}
                    />
                  </p>
                  <div className="flex items-center gap-1">
                    {/* First page */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          aria-label={intl.formatMessage({ defaultMessage: 'First page', id: 'Audit / First page' })}
                          onClick={() => handlePageChange(1)}
                          disabled={currentPage === 1 || loading}
                        >
                          <ChevronsLeft className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <FormattedMessage defaultMessage="First page" id="Audit / First page" />
                      </TooltipContent>
                    </Tooltip>

                    {/* Previous page */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          aria-label={intl.formatMessage({
                            defaultMessage: 'Previous page',
                            id: 'Audit / Previous page',
                          })}
                          onClick={() => handlePageChange(currentPage - 1)}
                          disabled={currentPage === 1 || loading}
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <FormattedMessage defaultMessage="Previous page" id="Audit / Previous page" />
                      </TooltipContent>
                    </Tooltip>

                    {/* Page numbers */}
                    <div className="flex items-center gap-1">
                      {getPageNumbers().map((page, index) =>
                        page === 'ellipsis' ? (
                          <span key={`ellipsis-${index}`} className="px-2 text-muted-foreground">
                            ...
                          </span>
                        ) : (
                          <Button
                            key={page}
                            variant={currentPage === page ? 'default' : 'ghost'}
                            size="icon"
                            className="h-8 w-8"
                            aria-current={currentPage === page ? 'page' : undefined}
                            onClick={() => handlePageChange(page)}
                            disabled={loading}
                          >
                            {page}
                          </Button>
                        )
                      )}
                    </div>

                    {/* Next page */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          aria-label={intl.formatMessage({ defaultMessage: 'Next page', id: 'Audit / Next page' })}
                          onClick={() => handlePageChange(currentPage + 1)}
                          disabled={currentPage === totalPages || loading}
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <FormattedMessage defaultMessage="Next page" id="Audit / Next page" />
                      </TooltipContent>
                    </Tooltip>

                    {/* Last page */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          aria-label={intl.formatMessage({ defaultMessage: 'Last page', id: 'Audit / Last page' })}
                          onClick={() => handlePageChange(totalPages)}
                          disabled={currentPage === totalPages || loading}
                        >
                          <ChevronsRight className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <FormattedMessage defaultMessage="Last page" id="Audit / Last page" />
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};
