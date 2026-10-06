import { useMutation } from '@apollo/client/react';
import { getFragmentData } from '@sb/webapp-api-client';
import { commonQueryMembershipFragment } from '@sb/webapp-api-client/providers';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent } from '@sb/webapp-core/components/ui/card';
import { Input } from '@sb/webapp-core/components/ui/input';
import { RoutesConfig as CoreRoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { cn } from '@sb/webapp-core/lib/utils';
import { useToast } from '@sb/webapp-core/toast';
import { ArrowRight, Building2, Loader2, Plus, Search, X } from 'lucide-react';
import { useId, useRef, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { FormattedMessage, FormattedNumber, useIntl } from 'react-intl';
import { Link } from 'react-router-dom';

import { useGenerateTenantPath, useTenants } from '../../hooks';
import { useCurrentTenant } from '../../providers';
import { setDefaultOrganizationMutation } from './companySelection.graphql';
import { companyGroups, matchesCompany } from './companySelection.utils';
import { useCompanyUser } from './companyUser.hook';

export const CompanySelection = () => {
  const intl = useIntl();
  const { toast } = useToast();
  const { user, loading: userLoading, error: loadError } = useCompanyUser();
  const tenants = useTenants();
  const { data: currentTenant } = useCurrentTenant();
  const localePath = useGenerateLocalePath();
  const tenantPath = useGenerateTenantPath();
  const [search, setSearch] = useState('');
  const searchId = useId();
  const searchInput = useRef<HTMLInputElement>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [failedId, setFailedId] = useState<string | null>(null);
  const { organizations, invitations } = companyGroups(tenants, !!user?.isSuperuser);
  const filtered = organizations.filter((company) => matchesCompany(company, search));
  const [setDefault, { loading: saving }] = useMutation(setDefaultOrganizationMutation, {
    update(cache, { data: result }) {
      if (!user || !result?.setDefaultOrganization) return;
      const id = cache.identify({ __typename: 'CurrentUserType', id: user.id });
      if (id)
        cache.modify({
          id,
          fields: { defaultOrganizationId: () => result.setDefaultOrganization?.defaultOrganizationId ?? null },
        });
    },
  });
  const changeDefault = async (companyId: string) => {
    setSavingId(companyId);
    setFailedId(null);
    const removing = user?.defaultOrganizationId === companyId;
    try {
      await setDefault({ variables: { organizationId: removing ? null : companyId } });
      toast({
        variant: 'success',
        description: removing
          ? intl.formatMessage({
              id: 'Companies / Default removed',
              defaultMessage: 'Default organization removed.',
            })
          : intl.formatMessage({
              id: 'Companies / Default saved',
              defaultMessage: 'Default organization saved. It will open automatically after you sign in.',
            }),
      });
    } catch {
      setFailedId(companyId);
    } finally {
      setSavingId(null);
    }
  };
  return (
    <PageLayout>
      <div className="mx-auto w-full max-w-5xl space-y-8">
        <Helmet title={intl.formatMessage({ id: 'Companies / Title', defaultMessage: 'Organizations' })} />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Building2 className="h-6 w-6 shrink-0 text-primary" aria-hidden="true" />
              <h1 className="text-3xl font-bold tracking-tight">
                <FormattedMessage id="Companies / Title" defaultMessage="Organizations" />
              </h1>
            </div>
            <p className="text-lg text-muted-foreground">
              <FormattedMessage
                id="Companies / Description"
                defaultMessage="Choose the organization you want to work in"
              />
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="w-full max-w-md space-y-2 text-sm">
            <label htmlFor={searchId} className="block">
              <FormattedMessage id="Companies / Search" defaultMessage="Search by name or NIP" />
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <Input
                id={searchId}
                ref={searchInput}
                className="pl-9 pr-10"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              {search && (
                <button
                  type="button"
                  aria-label={intl.formatMessage({ id: 'Companies / Clear search', defaultMessage: 'Clear search' })}
                  className="absolute right-1 top-1 flex h-8 w-8 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => {
                    setSearch('');
                    searchInput.current?.focus();
                  }}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
            </div>
          </div>
          <Button variant="outline" className="shrink-0 self-start sm:self-auto" asChild>
            <Link to={localePath(CoreRoutesConfig.addOrganization)}>
              <Plus className="mr-2 h-4 w-4" />
              <FormattedMessage id="Companies / Add" defaultMessage="Add organization" />
            </Link>
          </Button>
        </div>
        {userLoading && !user && (
          <p role="status">
            <FormattedMessage id="Companies / Loading" defaultMessage="Loading organizations…" />
          </p>
        )}
        {loadError && (
          <p role="alert">
            <FormattedMessage
              id="Companies / Load error"
              defaultMessage="Could not load organizations. Refresh the page and try again."
            />
          </p>
        )}
        {user && !loadError && (
          <>
            <p className="text-sm text-muted-foreground">
              <FormattedMessage
                id="Companies / Count"
                defaultMessage="Available organizations: {count}"
                values={{ count: organizations.length }}
              />
            </p>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {!organizations.length && (
                <Card className="group relative col-span-full flex min-h-64 flex-col overflow-hidden">
                  <div
                    aria-hidden="true"
                    className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-[#42F272] opacity-15 blur-2xl transition-opacity group-hover:opacity-25"
                  />
                  <CardContent
                    className="relative flex flex-1 flex-col items-center justify-center gap-4 px-5 py-10 text-center text-muted-foreground"
                    role="status"
                  >
                    <Building2 className="h-10 w-10 opacity-50" aria-hidden="true" />
                    <h2 className="text-xl font-semibold text-foreground">
                      <FormattedMessage
                        id="Companies / Empty title"
                        defaultMessage="You don't have any organizations yet"
                      />
                    </h2>
                    <p className="max-w-lg text-sm">
                      <FormattedMessage
                        id="Companies / Empty"
                        defaultMessage="Add your first organization to start working in Klarvido."
                      />
                    </p>
                    <Button variant="outline" asChild>
                      <Link to={localePath(CoreRoutesConfig.addOrganization)}>
                        <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                        <FormattedMessage id="Companies / Add" defaultMessage="Add organization" />
                      </Link>
                    </Button>
                  </CardContent>
                </Card>
              )}
              {organizations.length > 0 && !filtered.length && (
                <Card className="group relative col-span-full flex min-h-64 flex-col overflow-hidden">
                  <div
                    aria-hidden="true"
                    className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-[#42F272] opacity-15 blur-2xl transition-opacity group-hover:opacity-25"
                  />
                  <CardContent
                    className="relative flex flex-1 flex-col items-center justify-center gap-4 p-5 text-center text-muted-foreground"
                    role="status"
                  >
                    <Search className="h-10 w-10 opacity-50" aria-hidden="true" />
                    <p className="text-sm">
                      <FormattedMessage
                        id="Companies / No matches"
                        defaultMessage="No organizations match your search."
                      />
                    </p>
                    <Button
                      variant="outline"
                      className="cursor-pointer"
                      onClick={() => {
                        setSearch('');
                        searchInput.current?.focus();
                      }}
                    >
                      <FormattedMessage id="Companies / Clear search" defaultMessage="Clear search" />
                    </Button>
                  </CardContent>
                </Card>
              )}
              {filtered.map((company) => {
                const isDefault = user.defaultOrganizationId === company.id;
                return (
                  <Card
                    key={company.id}
                    className="group relative flex min-h-64 cursor-pointer flex-col overflow-hidden shadow-sm transition-all duration-300 hover:shadow-lg"
                  >
                    <div
                      aria-hidden="true"
                      className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-[#42F272] opacity-15 blur-2xl transition-opacity group-hover:opacity-25"
                    />
                    <CardContent className="relative flex flex-1 flex-col p-0">
                      <div className="flex min-h-9 items-center gap-2 px-5 pt-4">
                        <div className="flex flex-1 flex-wrap items-center gap-2">
                          {currentTenant?.id === company.id && (
                            <Badge className="bg-[#42F272] text-black">
                              <FormattedMessage id="Companies / Current" defaultMessage="Currently selected" />
                            </Badge>
                          )}
                          <Button
                            variant="ghost"
                            className={cn(
                              'relative z-10 h-auto cursor-pointer gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                              isDefault
                                ? 'border-border bg-white text-black hover:bg-white hover:text-black dark:border-white'
                                : 'border-border/50 bg-transparent text-muted-foreground/50 hover:border-border hover:bg-transparent hover:text-muted-foreground'
                            )}
                            aria-pressed={isDefault}
                            title={[
                              isDefault
                                ? intl.formatMessage({
                                    id: 'Companies / Remove default',
                                    defaultMessage: 'Remove default',
                                  })
                                : intl.formatMessage({
                                    id: 'Companies / Set default',
                                    defaultMessage: 'Set as default',
                                  }),
                              intl.formatMessage({
                                id: 'Companies / Default hint',
                                defaultMessage: 'Your default organization opens automatically after you sign in.',
                              }),
                            ].join('\n')}
                            disabled={saving}
                            aria-busy={savingId === company.id}
                            aria-label={
                              savingId === company.id
                                ? intl.formatMessage(
                                    {
                                      id: 'Companies / Saving label',
                                      defaultMessage: 'Saving default organization: {company}',
                                    },
                                    { company: company.name }
                                  )
                                : isDefault
                                  ? intl.formatMessage(
                                      {
                                        id: 'Companies / Remove default label',
                                        defaultMessage: 'Remove default organization: {company}',
                                      },
                                      { company: company.name }
                                    )
                                  : intl.formatMessage(
                                      {
                                        id: 'Companies / Set default label',
                                        defaultMessage: 'Set as default organization: {company}',
                                      },
                                      { company: company.name }
                                    )
                            }
                            aria-describedby={failedId === company.id ? `default-error-${company.id}` : undefined}
                            onClick={() => void changeDefault(company.id)}
                          >
                            {savingId === company.id && <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />}
                            <FormattedMessage id="Companies / Default badge" defaultMessage="Default" />
                            {savingId === company.id && (
                              <span role="status" className="sr-only">
                                <FormattedMessage id="Companies / Saving" defaultMessage="Saving…" />
                              </span>
                            )}
                          </Button>
                        </div>
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center">
                          <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                        </div>
                      </div>
                      <div className="flex min-h-14 items-start gap-1 px-5 pt-2">
                        <Link
                          to={tenantPath(CoreRoutesConfig.home, { tenantId: company.id })}
                          className="min-w-0 after:absolute after:inset-0 after:rounded-lg after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-ring"
                        >
                          <h2 title={company.name || undefined} className="break-words text-lg font-semibold">
                            {company.name}
                          </h2>
                        </Link>
                      </div>
                      <div className="flex flex-1 flex-col px-5 pb-5 pt-2">
                        <p className="mt-1 text-sm text-muted-foreground">
                          <FormattedMessage
                            id="Companies / NIP"
                            defaultMessage="NIP: {nip}"
                            values={{ nip: company.nip || '—' }}
                          />
                        </p>
                        <div className="mt-auto grid grid-cols-2 gap-3 pt-4">
                          <div className="min-w-0 rounded-xl bg-muted/40 p-3 text-[10px] text-muted-foreground">
                            <FormattedMessage id="Companies / Sales" defaultMessage="Sales" />
                            <p className="mt-1 break-words text-xl font-bold leading-snug text-foreground sm:text-2xl">
                              {/* Example value until organization metrics are connected. */}
                              <FormattedNumber value={0.1} style="percent" signDisplay="always" />
                            </p>
                          </div>
                          <div className="min-w-0 rounded-xl bg-muted/40 p-3 text-[10px] text-muted-foreground">
                            <FormattedMessage id="Companies / Decisions" defaultMessage="Active decisions" />
                            <p className="mt-1 break-words text-xl font-bold leading-snug text-foreground sm:text-2xl">
                              <FormattedNumber value={0} />
                            </p>
                          </div>
                        </div>
                        <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                          <span
                            className="h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/50"
                            aria-hidden="true"
                          />
                          <FormattedMessage id="Companies / Health" defaultMessage="No organization health data" />
                        </p>
                      </div>

                      {failedId === company.id && (
                        <p
                          id={`default-error-${company.id}`}
                          role="alert"
                          className="px-5 pb-5 text-sm text-destructive"
                        >
                          <FormattedMessage
                            id="Companies / Save error"
                            defaultMessage="Could not save your default organization. Your previous selection is unchanged. Try again."
                          />
                        </p>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
            {invitations.length > 0 && (
              <section className="space-y-3">
                <h2 className="text-xl font-semibold">
                  <FormattedMessage id="Companies / Invitations" defaultMessage="Organization invitations" />
                </h2>
                {invitations.map((company) => (
                  <Card key={company.id}>
                    <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
                      <span className="font-medium">{company.name}</span>
                      <Button variant="outline" asChild>
                        <Link
                          to={localePath(CoreRoutesConfig.tenantInvitation, {
                            token:
                              getFragmentData(commonQueryMembershipFragment, company.membership)?.invitationToken || '',
                          })}
                        >
                          <FormattedMessage id="Companies / View invitation" defaultMessage="View invitation" />
                        </Link>
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
};

export default CompanySelection;
