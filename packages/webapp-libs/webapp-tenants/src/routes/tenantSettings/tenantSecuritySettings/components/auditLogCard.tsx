import { apiClient, apiURL } from '@sb/webapp-api-client/api';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { DatePicker } from '@sb/webapp-core/components/ui/datePicker';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@sb/webapp-core/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@sb/webapp-core/components/ui/tooltip';
import { cn } from '@sb/webapp-core/lib/utils';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronsLeft,
  ChevronsRight,
  Clock,
  Filter,
  Fingerprint,
  KeyRound,
  Loader2,
  LogIn,
  LogOut,
  Monitor,
  RefreshCw,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  Smartphone,
  User,
  Users,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FormattedMessage, type IntlShape, defineMessages, useIntl } from 'react-intl';

import { useCurrentTenant } from '../../../../providers';

interface AuditLog {
  id: string;
  eventType: string;
  eventTypeLabel?: string;
  eventDescription: string;
  userEmail: string | null;
  connectionName: string | null;
  ipAddress: string | null;
  userAgent: string;
  success: boolean;
  errorMessage: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}

interface EventTypeOption {
  value: string;
  label: string;
}

interface AuditLogResponse {
  logs: AuditLog[];
  totalCount: number;
  totalPages: number;
  currentPage: number;
  pageSize: number;
  hasMore: boolean;
  hasPrevious: boolean;
  eventTypeOptions?: EventTypeOption[];
  userEmails?: string[];
}

interface Filters {
  eventType: string;
  userEmail: string;
  success: string;
  startDate: string;
  endDate: string;
  search: string;
}

const FILTER_DEBOUNCE_MS = 300;

const EVENT_ICONS: Record<string, React.ReactNode> = {
  // SSO events
  sso_login_initiated: <LogIn className="h-4 w-4" />,
  sso_login_success: <LogIn className="h-4 w-4" />,
  sso_login_failed: <X className="h-4 w-4" />,
  sso_logout: <LogOut className="h-4 w-4" />,

  // Config events
  idp_config_created: <Settings className="h-4 w-4" />,
  idp_config_updated: <Settings className="h-4 w-4" />,
  idp_config_deleted: <Settings className="h-4 w-4" />,
  idp_config_activated: <Check className="h-4 w-4" />,
  idp_config_deactivated: <X className="h-4 w-4" />,

  // Provisioning events
  user_provisioned: <User className="h-4 w-4" />,
  user_updated: <User className="h-4 w-4" />,
  group_mapping_applied: <Users className="h-4 w-4" />,

  // SCIM events
  scim_user_created: <User className="h-4 w-4" />,
  scim_user_updated: <User className="h-4 w-4" />,
  scim_user_deleted: <User className="h-4 w-4" />,
  scim_group_created: <Users className="h-4 w-4" />,
  scim_group_updated: <Users className="h-4 w-4" />,
  scim_group_deleted: <Users className="h-4 w-4" />,

  // Session events
  session_created: <Monitor className="h-4 w-4" />,
  session_revoked: <LogOut className="h-4 w-4" />,

  // Device events
  device_registered: <Smartphone className="h-4 w-4" />,
  device_removed: <Smartphone className="h-4 w-4" />,

  // Passkey events
  ksef_token_saved: <KeyRound className="h-4 w-4" />,
  ksef_token_tested: <KeyRound className="h-4 w-4" />,
  ksef_token_deleted: <KeyRound className="h-4 w-4" />,
  passkey_registered: <Fingerprint className="h-4 w-4" />,
  passkey_removed: <Fingerprint className="h-4 w-4" />,
  passkey_auth_success: <Fingerprint className="h-4 w-4" />,
  passkey_auth_failed: <Fingerprint className="h-4 w-4" />,
  passkey_reauth_success: <Fingerprint className="h-4 w-4" />,
  passkey_reauth_failed: <Fingerprint className="h-4 w-4" />,

  // Enforcement events
  sso_enforce_bypass: <Shield className="h-4 w-4" />,
};

const getEventIcon = (eventType: string) => {
  return EVENT_ICONS[eventType] || <Shield className="h-4 w-4" />;
};

// Labels for event types that are translated in the frontend. Other types fall back to the label sent by the backend.
const EVENT_TYPE_MESSAGES = defineMessages({
  auth_account_deletion: { id: 'Audit / Event / Account deletion', defaultMessage: 'Account deletion' },
  auth_signup: { id: 'Audit / Event / auth_signup', defaultMessage: 'Registration request' },
  auth_email_confirmation: { id: 'Audit / Event / auth_email_confirmation', defaultMessage: 'Email confirmation' },
  auth_password_login: { id: 'Audit / Event / auth_password_login', defaultMessage: 'Password login' },
  auth_otp_challenge: { id: 'Audit / Event / auth_otp_challenge', defaultMessage: 'Two-factor login challenge' },
  auth_otp_verification: { id: 'Audit / Event / auth_otp_verification', defaultMessage: 'Two-factor verification' },
  auth_password_reset_request: {
    id: 'Audit / Event / auth_password_reset_request',
    defaultMessage: 'Password reset request',
  },
  auth_password_reset: { id: 'Audit / Event / auth_password_reset', defaultMessage: 'Password reset' },
  auth_password_change: { id: 'Audit / Event / auth_password_change', defaultMessage: 'Password change' },
  auth_otp_management: {
    id: 'Audit / Event / auth_otp_management',
    defaultMessage: 'Two-factor authentication change',
  },

  passkey_reauth_success: {
    id: 'Audit / Event / Passkey reauthentication succeeded',
    defaultMessage: 'Passkey management verification succeeded',
  },
  passkey_reauth_failed: {
    id: 'Audit / Event / Passkey reauthentication failed',
    defaultMessage: 'Passkey management verification failed',
  },
  ksef_token_saved: { id: 'Audit / Event / KSeF token saved', defaultMessage: 'KSeF token saved' },
  ksef_token_tested: { id: 'Audit / Event / KSeF token tested', defaultMessage: 'KSeF token tested' },
  ksef_token_deleted: { id: 'Audit / Event / KSeF token removed', defaultMessage: 'KSeF token removed' },
  idp_config_created: { id: 'Audit / Event / IdP Configuration Created', defaultMessage: 'IdP Configuration Created' },
  idp_config_updated: { id: 'Audit / Event / IdP Configuration Updated', defaultMessage: 'IdP Configuration Updated' },
  idp_config_deleted: { id: 'Audit / Event / IdP Configuration Deleted', defaultMessage: 'IdP Configuration Deleted' },
  idp_config_activated: {
    id: 'Audit / Event / IdP Configuration Activated',
    defaultMessage: 'IdP Configuration Activated',
  },
  idp_config_deactivated: {
    id: 'Audit / Event / IdP Configuration Deactivated',
    defaultMessage: 'IdP Configuration Deactivated',
  },
  sso_login_initiated: { id: 'Audit / Event / SSO Login Initiated', defaultMessage: 'SSO Login Initiated' },
  sso_login_success: { id: 'Audit / Event / SSO Login Success', defaultMessage: 'SSO Login Success' },
  sso_login_failed: { id: 'Audit / Event / SSO Login Failed', defaultMessage: 'SSO Login Failed' },
  sso_logout: { id: 'Audit / Event / SSO Logout', defaultMessage: 'SSO Logout' },
  user_provisioned: { id: 'Audit / Event / User Provisioned via JIT', defaultMessage: 'User Provisioned via JIT' },
  user_updated: { id: 'Audit / Event / User Updated via SSO', defaultMessage: 'User Updated via SSO' },
  group_mapping_applied: { id: 'Audit / Event / Group Mapping Applied', defaultMessage: 'Group Mapping Applied' },
  scim_user_created: { id: 'Audit / Event / SCIM User Created', defaultMessage: 'SCIM User Created' },
  scim_user_updated: { id: 'Audit / Event / SCIM User Updated', defaultMessage: 'SCIM User Updated' },
  scim_user_deleted: { id: 'Audit / Event / SCIM User Deleted', defaultMessage: 'SCIM User Deleted' },
  scim_group_created: { id: 'Audit / Event / SCIM Group Created', defaultMessage: 'SCIM Group Created' },
  scim_group_updated: { id: 'Audit / Event / SCIM Group Updated', defaultMessage: 'SCIM Group Updated' },
  scim_group_deleted: { id: 'Audit / Event / SCIM Group Deleted', defaultMessage: 'SCIM Group Deleted' },
  sso_enforce_bypass: { id: 'Audit / Event / SSO Enforce Bypass Login', defaultMessage: 'SSO Enforce Bypass Login' },
});

const KSEF_STATUS_MESSAGES = defineMessages({
  VALID: { id: 'Audit / KSeF status verified', defaultMessage: 'Verified' },
  UNVERIFIED: { id: 'Audit / KSeF status unverified', defaultMessage: 'Not verified yet' },
  INVALID: { id: 'Audit / KSeF status rejected', defaultMessage: 'Rejected by KSeF' },
});

const getEventTypeLabel = (intl: IntlShape, eventType: string, fallback?: string): string => {
  const message = EVENT_TYPE_MESSAGES[eventType as keyof typeof EVENT_TYPE_MESSAGES];
  return message ? intl.formatMessage(message) : fallback || eventType;
};

const DEFAULT_PAGE_SIZE = 20;

export const AuditLogCard = () => {
  const intl = useIntl();
  const { data: currentTenant } = useCurrentTenant();
  const tenantId = currentTenant?.id;

  // State
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const hasLoadedOnce = useRef(false);

  // Filter state
  const [filters, setFilters] = useState<Filters>({
    eventType: '',
    userEmail: '',
    success: '',
    startDate: '',
    endDate: '',
    search: '',
  });

  // Available filter options
  const [filterOptions, setFilterOptions] = useState<{
    eventTypes: string[];
    eventTypeLabels: Record<string, string>;
    userEmails: string[];
  }>({
    eventTypes: [],
    eventTypeLabels: {},
    userEmails: [],
  });

  const hasActiveFilters = useMemo(() => {
    return Object.values(filters).some((v) => v !== '');
  }, [filters]);

  // Read the latest filters from a ref, so fetching does not change identity on every keystroke
  const filtersRef = useRef(filters);
  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  // Only the most recent request may update the list, so slow responses cannot overwrite newer results
  const latestRequestId = useRef(0);

  const buildQueryParams = useCallback((page: number, includeFilterOptions = false) => {
    const currentFilters = filtersRef.current;
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('limit', String(DEFAULT_PAGE_SIZE));

    if (currentFilters.eventType) params.set('event_type', currentFilters.eventType);
    if (currentFilters.userEmail) params.set('user_email', currentFilters.userEmail);
    if (currentFilters.success) params.set('success', currentFilters.success);
    if (currentFilters.startDate) params.set('start_date', currentFilters.startDate);
    if (currentFilters.endDate) params.set('end_date', currentFilters.endDate);
    if (currentFilters.search) params.set('search', currentFilters.search);
    if (includeFilterOptions) params.set('include_filter_options', 'true');

    return params.toString();
  }, []);

  const fetchLogs = useCallback(
    async (page = 1, fetchFilterOptions = false) => {
      if (!tenantId) {
        setInitialLoading(false);
        return;
      }

      // Only show initial loading spinner on first load
      if (!hasLoadedOnce.current) {
        setInitialLoading(true);
      } else {
        setIsFetching(true);
      }

      const requestId = ++latestRequestId.current;
      const isLatestRequest = () => requestId === latestRequestId.current;

      try {
        const queryParams = buildQueryParams(page, fetchFilterOptions);
        const response = await apiClient.get<AuditLogResponse>(
          apiURL(`/sso/tenant/${tenantId}/audit-logs/?${queryParams}`)
        );
        if (!isLatestRequest()) return;
        setLogs(response.data.logs || []);
        setTotalCount(response.data.totalCount || 0);
        setTotalPages(response.data.totalPages || 0);
        setCurrentPage(response.data.currentPage || 1);
        hasLoadedOnce.current = true;

        if (fetchFilterOptions) {
          const options = response.data.eventTypeOptions || [];
          const eventTypes = options.map((opt: EventTypeOption) => opt.value);
          const eventTypeLabels: Record<string, string> = {};
          options.forEach((opt: EventTypeOption) => {
            eventTypeLabels[opt.value] = opt.label;
          });

          setFilterOptions((prev) => ({
            ...prev,
            eventTypes: eventTypes.length > 0 ? eventTypes : prev.eventTypes,
            eventTypeLabels: Object.keys(eventTypeLabels).length > 0 ? eventTypeLabels : prev.eventTypeLabels,
            userEmails: response.data.userEmails || prev.userEmails,
          }));
        }
      } catch (error) {
        // Silently handle errors - audit logs may not be accessible due to permissions
        if (process.env['NODE_ENV'] === 'development') {
          console.warn('Failed to fetch audit logs (this is expected if user lacks permissions):', error);
        }
      } finally {
        if (isLatestRequest()) {
          setInitialLoading(false);
          setIsFetching(false);
        }
      }
    },
    [tenantId, buildQueryParams]
  );

  // Load the list and filter options once per organization
  useEffect(() => {
    fetchLogs(1, true);
  }, [fetchLogs]);

  // Filter changes (including search typing) refresh the list after a short pause
  const lastRequestedFilters = useRef(filters);
  useEffect(() => {
    if (lastRequestedFilters.current === filters) return;
    lastRequestedFilters.current = filters;
    const timeout = setTimeout(() => fetchLogs(1), FILTER_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [filters, fetchLogs]);

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
      fetchLogs(page);
    }
  };

  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const handleApplyFilters = () => {
    fetchLogs(1);
  };

  const handleClearFilters = () => {
    const clearedFilters = {
      eventType: '',
      userEmail: '',
      success: '',
      startDate: '',
      endDate: '',
      search: '',
    };
    setFilters(clearedFilters);
  };

  const handleRefresh = () => {
    fetchLogs(currentPage);
  };

  // Only curated, translated fields are shown. Raw metadata (JSON payloads, internal ids) is never displayed.
  const hasLogDetails = (log: AuditLog) =>
    Boolean(log.connectionName || log.ipAddress || log.errorMessage || log.eventType.startsWith('ksef_'));

  const renderKsefDetails = (log: AuditLog) => {
    if (!log.eventType.startsWith('ksef_')) return null;
    // The API returns metadata keys in camelCase
    const { tokenHint, tokenName, status, created } = log.metadata as {
      tokenHint?: unknown;
      tokenName?: unknown;
      status?: unknown;
      created?: unknown;
    };
    const isRemoval = log.eventType === 'ksef_token_deleted';
    const statusMessage =
      typeof status === 'string' && status in KSEF_STATUS_MESSAGES
        ? intl.formatMessage(KSEF_STATUS_MESSAGES[status as keyof typeof KSEF_STATUS_MESSAGES])
        : null;

    return (
      <>
        {typeof tokenName === 'string' && tokenName && (
          <div className="col-span-2">
            <dt className="text-xs font-medium text-muted-foreground mb-1">
              <FormattedMessage defaultMessage="Token name in KSeF" id="Audit / Token name in KSeF" />
            </dt>
            <dd className="break-all">{tokenName}</dd>
          </div>
        )}
        {typeof tokenHint === 'string' && (
          <div>
            <dt className="text-xs font-medium text-muted-foreground mb-1">
              <FormattedMessage defaultMessage="Token ending in" id="Audit / Token ending in" />
            </dt>
            <dd className="font-mono">••••{tokenHint}</dd>
          </div>
        )}
        {(typeof created === 'boolean' || isRemoval) && (
          <div>
            <dt className="text-xs font-medium text-muted-foreground mb-1">
              <FormattedMessage defaultMessage="Action" id="Audit / Token action" />
            </dt>
            <dd>
              {isRemoval ? (
                <FormattedMessage defaultMessage="Token removed" id="Audit / Token action removed" />
              ) : created ? (
                <FormattedMessage defaultMessage="New token saved" id="Audit / Token action created" />
              ) : (
                <FormattedMessage defaultMessage="Replaced existing token" id="Audit / Token action replaced" />
              )}
            </dd>
          </div>
        )}
        {statusMessage && (
          <div>
            <dt className="text-xs font-medium text-muted-foreground mb-1">
              <FormattedMessage defaultMessage="Status" id="Audit / Status" />
            </dt>
            <dd>{statusMessage}</dd>
          </div>
        )}
      </>
    );
  };

  const formatDate = (dateStr: string) =>
    intl.formatDate(dateStr, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

  const toggleLogExpand = (logId: string) => {
    setExpandedLogId(expandedLogId === logId ? null : logId);
  };

  // Generate page numbers for pagination
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
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <Clock className="h-5 w-5 text-primary" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-lg">
                  <FormattedMessage defaultMessage="Security Audit Log" id="Tenant Security Settings / Audit Header" />
                </CardTitle>
                <CardDescription className="mt-0.5">
                  <FormattedMessage
                    defaultMessage="View recent SSO, SCIM and KSeF events for your organization"
                    id="Tenant Security Settings / Audit Description"
                  />
                </CardDescription>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant={showFilters ? 'secondary' : 'outline'}
                    size="sm"
                    onClick={() => setShowFilters(!showFilters)}
                    className={cn('gap-2', hasActiveFilters && 'border-primary/50')}
                  >
                    <Filter className="h-4 w-4" />
                    <FormattedMessage defaultMessage="Filters" id="Audit / Filters button" />
                    {hasActiveFilters && (
                      <Badge variant="default" className="ml-1 h-5 px-1.5 text-xs">
                        {Object.values(filters).filter((v) => v !== '').length}
                      </Badge>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <FormattedMessage defaultMessage="Filter audit log events" id="Audit / Filters Tooltip" />
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" onClick={handleRefresh} disabled={isFetching} className="h-9 w-9">
                    <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <FormattedMessage defaultMessage="Refresh" id="Audit / Refresh Tooltip" />
                </TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="mt-4 rounded-lg border bg-muted/10 p-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {/* Search */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Search" id="Audit / Filter Search" />
                  </label>
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={intl.formatMessage({
                        defaultMessage: 'Search logs...',
                        id: 'Audit / Search placeholder',
                      })}
                      value={filters.search}
                      onChange={(e) => handleFilterChange('search', e.target.value)}
                      className="pl-8"
                    />
                  </div>
                </div>

                {/* Event Type */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Event Type" id="Audit / Filter Event Type" />
                  </label>
                  <Select
                    value={filters.eventType}
                    onValueChange={(value) => handleFilterChange('eventType', value === 'all' ? '' : value)}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={intl.formatMessage({
                          defaultMessage: 'All events',
                          id: 'Audit / All events placeholder',
                        })}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        <FormattedMessage defaultMessage="All events" id="Audit / All events" />
                      </SelectItem>
                      {filterOptions.eventTypes.map((type) => (
                        <SelectItem key={type} value={type}>
                          {getEventTypeLabel(intl, type, filterOptions.eventTypeLabels[type])}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* User Email */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="User" id="Audit / Filter User" />
                  </label>
                  <Input
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Filter by email...',
                      id: 'Audit / User email placeholder',
                    })}
                    value={filters.userEmail}
                    onChange={(e) => handleFilterChange('userEmail', e.target.value)}
                  />
                </div>

                {/* Status */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Status" id="Audit / Filter Status" />
                  </label>
                  <Select
                    value={filters.success}
                    onValueChange={(value) => handleFilterChange('success', value === 'all' ? '' : value)}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={intl.formatMessage({
                          defaultMessage: 'All statuses',
                          id: 'Audit / All statuses placeholder',
                        })}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        <FormattedMessage defaultMessage="All statuses" id="Audit / All statuses" />
                      </SelectItem>
                      <SelectItem value="true">
                        <div className="flex items-center gap-2">
                          <Check className="h-4 w-4 text-emerald-600" />
                          <FormattedMessage defaultMessage="Success" id="Audit / Status Success" />
                        </div>
                      </SelectItem>
                      <SelectItem value="false">
                        <div className="flex items-center gap-2">
                          <X className="h-4 w-4 text-destructive" />
                          <FormattedMessage defaultMessage="Failed" id="Audit / Status Failed" />
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Start Date */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="From Date" id="Audit / Filter Start Date" />
                  </label>
                  <DatePicker
                    value={filters.startDate}
                    onChange={(value) => handleFilterChange('startDate', value || '')}
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Select start date',
                      id: 'Audit / Start Date Placeholder',
                    })}
                  />
                </div>

                {/* End Date */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="To Date" id="Audit / Filter End Date" />
                  </label>
                  <DatePicker
                    value={filters.endDate}
                    onChange={(value) => handleFilterChange('endDate', value || '')}
                    placeholder={intl.formatMessage({
                      defaultMessage: 'Select end date',
                      id: 'Audit / End Date Placeholder',
                    })}
                  />
                </div>
              </div>

              {/* Filter Actions */}
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <p className="text-sm text-muted-foreground">
                  <FormattedMessage
                    defaultMessage="{count, plural, =0 {No events found} one {# event found} other {# events found}}"
                    id="Audit / Results count"
                    values={{ count: totalCount }}
                  />
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearFilters}
                    disabled={!hasActiveFilters || isFetching}
                  >
                    <FormattedMessage defaultMessage="Clear filters" id="Audit / Clear filters" />
                  </Button>
                  <Button size="sm" onClick={handleApplyFilters} disabled={isFetching}>
                    {isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    <FormattedMessage defaultMessage="Apply filters" id="Audit / Apply filters" />
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardHeader>

        <CardContent>
          {initialLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 p-8 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted mb-4">
                <ShieldCheck className="h-7 w-7 text-muted-foreground" />
              </div>
              <h3 className="text-base font-semibold mb-1">
                {hasActiveFilters ? (
                  <FormattedMessage
                    defaultMessage="No events match your filters"
                    id="Tenant Security Settings / No Filtered Audit Events"
                  />
                ) : (
                  <FormattedMessage
                    defaultMessage="No security events yet"
                    id="Tenant Security Settings / No Audit Events"
                  />
                )}
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-4">
                {hasActiveFilters ? (
                  <FormattedMessage
                    defaultMessage="Try adjusting your filters or clearing them to see all events."
                    id="Tenant Security Settings / No Filtered Audit Events Hint"
                  />
                ) : (
                  <FormattedMessage
                    defaultMessage="SSO and SCIM events, such as SSO logins, user provisioning and configuration changes, and KSeF token changes, will appear here."
                    id="Tenant Security Settings / No Audit Events Hint"
                  />
                )}
              </p>
              {hasActiveFilters && (
                <Button variant="outline" size="sm" onClick={handleClearFilters}>
                  <FormattedMessage defaultMessage="Clear filters" id="Audit / Clear filters link" />
                </Button>
              )}
            </div>
          ) : (
            <div className="relative space-y-4">
              {/* Subtle loading overlay for fetching */}
              {isFetching && (
                <div className="pointer-events-none absolute inset-0 z-10 flex items-start justify-center bg-background/50 pt-8">
                  <div className="flex items-center gap-2 rounded-full bg-background px-3 py-1.5 shadow-md border">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <span className="text-sm text-muted-foreground">
                      <FormattedMessage defaultMessage="Loading..." id="Audit / Loading indicator" />
                    </span>
                  </div>
                </div>
              )}

              {/* Logs List */}
              <div className={cn('space-y-2', isFetching && 'opacity-60')}>
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className={cn(
                      'group rounded-lg border transition-all',
                      'hover:shadow-sm hover:border-t-primary/20 hover:border-r-primary/20 hover:border-b-primary/20',
                      log.success
                        ? 'border-l-2 border-l-emerald-500'
                        : 'border-l-2 border-l-destructive bg-destructive/5 dark:border-l-red-400 dark:bg-red-400/5'
                    )}
                  >
                    <button
                      type="button"
                      className="flex w-full cursor-pointer items-center justify-between rounded-lg p-4 text-left disabled:cursor-default"
                      onClick={hasLogDetails(log) ? () => toggleLogExpand(log.id) : undefined}
                      aria-expanded={hasLogDetails(log) ? expandedLogId === log.id : undefined}
                      disabled={!hasLogDetails(log)}
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={cn(
                            'flex h-10 w-10 items-center justify-center rounded-lg transition-colors',
                            log.success
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'bg-destructive/10 text-destructive dark:bg-red-400/10 dark:text-red-400'
                          )}
                        >
                          {log.success ? getEventIcon(log.eventType) : <AlertTriangle className="h-4 w-4" />}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">
                              {getEventTypeLabel(intl, log.eventType, log.eventTypeLabel)}
                            </span>
                            {!log.success && (
                              <Badge variant="destructive" className="text-xs dark:bg-red-400">
                                <FormattedMessage defaultMessage="Failed" id="Audit / Failed badge" />
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span>{formatDate(log.createdAt)}</span>
                            {log.userEmail && (
                              <>
                                <span className="text-muted-foreground/50">•</span>
                                <span>{log.userEmail}</span>
                              </>
                            )}
                            {log.ipAddress && (
                              <>
                                <span className="text-muted-foreground/50">•</span>
                                <span className="font-mono">{log.ipAddress}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <span
                        className="flex h-8 w-8 shrink-0 items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                        aria-hidden
                      >
                        {!hasLogDetails(log) ? null : expandedLogId === log.id ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </span>
                    </button>

                    {hasLogDetails(log) && expandedLogId === log.id && (
                      <div className="mx-4 mb-4 border-t pt-4">
                        <dl className="grid grid-cols-2 gap-3 text-sm">
                          {log.connectionName && (
                            <div>
                              <dt className="text-xs font-medium text-muted-foreground mb-1">
                                <FormattedMessage defaultMessage="SSO Connection" id="Audit / Connection" />
                              </dt>
                              <dd>{log.connectionName}</dd>
                            </div>
                          )}
                          {log.ipAddress && (
                            <div>
                              <dt className="text-xs font-medium text-muted-foreground mb-1">
                                <FormattedMessage defaultMessage="IP Address" id="Audit / IP Address" />
                              </dt>
                              <dd className="font-mono">{log.ipAddress}</dd>
                            </div>
                          )}
                          {log.errorMessage && (
                            <div className="col-span-2">
                              <dt className="text-xs font-medium text-destructive mb-1 dark:text-red-400">
                                <FormattedMessage defaultMessage="Error" id="Audit / Error" />
                              </dt>
                              <dd className="text-destructive dark:text-red-400">{log.errorMessage}</dd>
                            </div>
                          )}
                          {renderKsefDetails(log)}
                        </dl>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className={cn('flex items-center justify-between border-t pt-4', isFetching && 'opacity-60')}>
                  <p className="text-sm text-muted-foreground">
                    <FormattedMessage
                      defaultMessage="Showing {start}-{end} of {total} events"
                      id="Audit / Pagination summary"
                      values={{
                        start: ((currentPage - 1) * DEFAULT_PAGE_SIZE + 1).toLocaleString(),
                        end: Math.min(currentPage * DEFAULT_PAGE_SIZE, totalCount).toLocaleString(),
                        total: totalCount.toLocaleString(),
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
                          onClick={() => handlePageChange(1)}
                          disabled={currentPage === 1 || isFetching}
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
                          onClick={() => handlePageChange(currentPage - 1)}
                          disabled={currentPage === 1 || isFetching}
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
                            onClick={() => handlePageChange(page)}
                            disabled={isFetching}
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
                          onClick={() => handlePageChange(currentPage + 1)}
                          disabled={currentPage === totalPages || isFetching}
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
                          onClick={() => handlePageChange(totalPages)}
                          disabled={currentPage === totalPages || isFetching}
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
