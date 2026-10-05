import { useMutation } from '@apollo/client/react';
import { TenantUserRole, getFragmentData } from '@sb/webapp-api-client';
import { commonQueryMembershipFragment } from '@sb/webapp-api-client/providers';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent } from '@sb/webapp-core/components/ui/card';
import { Input } from '@sb/webapp-core/components/ui/input';
import { RoutesConfig as CoreRoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast';
import { ArrowRight, Building2, Loader2, Plus, Search, Star } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
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
  const [savingId, setSavingId] = useState<string | null>(null);
  const { organizations, invitations } = companyGroups(tenants, !!user?.isSuperuser);
  const filtered = organizations.filter((company) => matchesCompany(company, search));
  const [setDefault, { loading: saving, error: saveError }] = useMutation(setDefaultOrganizationMutation, {
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
    const removing = user?.defaultOrganizationId === companyId;
    try {
      await setDefault({ variables: { organizationId: removing ? null : companyId } });
      toast({
        variant: 'success',
        description: removing
          ? intl.formatMessage({
              id: 'Companies / Default removed',
              defaultMessage: 'Usunięto domyślną firmę. Po zalogowaniu wybierzesz ją na ekranie Firmy.',
            })
          : intl.formatMessage({
              id: 'Companies / Default saved',
              defaultMessage: 'Zapisano domyślną firmę. Otworzy się automatycznie po zalogowaniu.',
            }),
      });
    } catch {
      // Keep the existing preference; the error is shown beside the cards.
    } finally {
      setSavingId(null);
    }
  };
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">
            <FormattedMessage id="Companies / Title" defaultMessage="Firmy" />
          </h1>
          <p className="mt-2 text-muted-foreground">
            <FormattedMessage id="Companies / Description" defaultMessage="Wybierz firmę, w której chcesz pracować" />
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link to={localePath(CoreRoutesConfig.addTenant)}>
            <Plus className="mr-2 h-4 w-4" />
            <FormattedMessage id="Companies / Add" defaultMessage="Dodaj firmę" />
          </Link>
        </Button>
      </div>
      {userLoading && !user && (
        <p role="status">
          <FormattedMessage id="Companies / Loading" defaultMessage="Wczytywanie firm…" />
        </p>
      )}
      {loadError && (
        <p role="alert">
          <FormattedMessage
            id="Companies / Load error"
            defaultMessage="Nie udało się wczytać firm. Odśwież stronę i spróbuj ponownie."
          />
        </p>
      )}
      {user && !loadError && (
        <>
          <Card>
            <CardContent className="flex gap-4 pt-6">
              <Building2 className="h-8 w-8 shrink-0 text-muted-foreground" aria-hidden="true" />
              <div>
                <p className="font-medium">
                  <FormattedMessage
                    id="Companies / Count"
                    defaultMessage="Dostępne firmy: {count}"
                    values={{ count: organizations.length }}
                  />
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  <FormattedMessage
                    id="Companies / Default hint"
                    defaultMessage="Wybierz firmę, aby przełączyć kontekst Klarvido. Ustaw domyślną, jeśli chcesz otwierać ją automatycznie po zalogowaniu."
                  />
                </p>
              </div>
            </CardContent>
          </Card>
          <label className="block max-w-md space-y-2 text-sm">
            <span>
              <FormattedMessage id="Companies / Search" defaultMessage="Szukaj po nazwie lub NIP-ie" />
            </span>
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" aria-hidden="true" />
              <Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} />
            </div>
          </label>
          {saveError && (
            <p role="alert" className="text-sm text-destructive">
              <FormattedMessage
                id="Companies / Save error"
                defaultMessage="Nie udało się zapisać domyślnej firmy. Dotychczasowy wybór pozostaje bez zmian. Spróbuj ponownie."
              />
            </p>
          )}
          {!organizations.length && (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                <FormattedMessage
                  id="Companies / Empty"
                  defaultMessage="Nie masz jeszcze dostępu do żadnej firmy. Dodaj firmę lub zaakceptuj zaproszenie poniżej."
                />
              </CardContent>
            </Card>
          )}
          {organizations.length > 0 && !filtered.length && (
            <p role="status">
              <FormattedMessage
                id="Companies / No matches"
                defaultMessage="Nie znaleziono firm pasujących do wyszukiwania."
              />
            </p>
          )}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((company) => {
              const membership = getFragmentData(commonQueryMembershipFragment, company.membership);
              const role = membership?.role || (user.isSuperuser ? TenantUserRole.OWNER : null);
              const isDefault = user.defaultOrganizationId === company.id;
              return (
                <Card key={company.id} className={isDefault ? 'border-primary' : ''}>
                  <CardContent className="p-0">
                    <Link
                      to={tenantPath(CoreRoutesConfig.home, { tenantId: company.id })}
                      className="block rounded-t-lg p-5 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        {isDefault && (
                          <Badge>
                            <Star className="mr-1 h-3 w-3" aria-hidden="true" />
                            <FormattedMessage id="Companies / Default badge" defaultMessage="Domyślna" />
                          </Badge>
                        )}
                        {currentTenant?.id === company.id && (
                          <Badge variant="secondary">
                            <FormattedMessage id="Companies / Current" defaultMessage="Aktualnie wybrana" />
                          </Badge>
                        )}
                        <ArrowRight className="ml-auto h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      </div>
                      <h2 className="mt-3 break-words text-lg font-semibold">{company.name}</h2>
                      <p className="mt-1 text-sm text-muted-foreground">
                        <FormattedMessage
                          id="Companies / NIP"
                          defaultMessage="NIP: {nip}"
                          values={{ nip: company.nip || '—' }}
                        />
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {role === TenantUserRole.OWNER ? (
                          <FormattedMessage id="Companies / Owner" defaultMessage="Właściciel" />
                        ) : role === TenantUserRole.ADMIN ? (
                          <FormattedMessage id="Companies / Admin" defaultMessage="Administrator" />
                        ) : (
                          <FormattedMessage id="Companies / Member" defaultMessage="Członek" />
                        )}
                      </p>
                      <div className="mt-4 grid grid-cols-2 gap-2">
                        <div className="rounded-md bg-muted p-3 text-xs">
                          <FormattedMessage id="Companies / Sales" defaultMessage="Sprzedaż" />
                          <p className="mt-1 text-sm text-muted-foreground">
                            <FormattedMessage id="Companies / Unavailable" defaultMessage="Jeszcze niedostępne" />
                          </p>
                        </div>
                        <div className="rounded-md bg-muted p-3 text-xs">
                          <FormattedMessage id="Companies / Decisions" defaultMessage="Aktywne decyzje" />
                          <p className="mt-1 text-sm text-muted-foreground">
                            <FormattedMessage id="Companies / Unavailable" defaultMessage="Jeszcze niedostępne" />
                          </p>
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-muted-foreground">
                        <FormattedMessage
                          id="Companies / Health"
                          defaultMessage="Kondycja firmy: jeszcze niedostępna"
                        />
                      </p>
                    </Link>
                    <div className="border-t px-5 py-3">
                      <Button
                        variant="ghost"
                        className="h-auto w-full justify-start whitespace-normal px-0 text-left"
                        disabled={saving}
                        onClick={() => void changeDefault(company.id)}
                      >
                        {savingId === company.id ? (
                          <Loader2 className="mr-2 h-4 w-4 shrink-0 animate-spin" aria-hidden="true" />
                        ) : (
                          <Star className="mr-2 h-4 w-4 shrink-0" aria-hidden="true" />
                        )}
                        {isDefault ? (
                          <FormattedMessage id="Companies / Remove default" defaultMessage="Usuń domyślną" />
                        ) : (
                          <FormattedMessage id="Companies / Set default" defaultMessage="Ustaw jako domyślną" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
          {invitations.length > 0 && (
            <section className="space-y-3">
              <h2 className="text-xl font-semibold">
                <FormattedMessage id="Companies / Invitations" defaultMessage="Zaproszenia do firm" />
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
                        <FormattedMessage id="Companies / View invitation" defaultMessage="Zobacz zaproszenie" />
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
  );
};

export default CompanySelection;
