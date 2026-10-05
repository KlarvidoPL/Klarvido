import { Button } from '@sb/webapp-core/components/buttons';
import { Input } from '@sb/webapp-core/components/forms';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { AlertTriangle, Check, Copy, Globe, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

import { useTenantSSODomains } from '../../../../hooks/useTenantSSODomains';
import { useCurrentTenant } from '../../../../providers';
import { getSsoDomainErrorDetail } from './ssoDomainErrors';

interface DomainVerificationCardProps {
  canManageSSO: boolean;
}

interface SSODomain {
  id: string;
  domain: string;
  status: string;
  lastCheckedAt?: string | null;
  consecutiveFailures?: number | null;
  firstFailedAt?: string | null;
  gracePeriodEndsAt?: string | null;
  verificationRecordName?: string | null;
  verificationRecordValue?: string | null;
}

export const DomainVerificationCard = ({ canManageSSO }: DomainVerificationCardProps) => {
  const intl = useIntl();
  const { toast } = useToast();
  const { data: currentTenant } = useCurrentTenant();
  const tenantId = currentTenant?.id;
  const { domains, addDomain, adding, verifyDomain, verifying, deleteDomain, deleting } = useTenantSSODomains(tenantId);
  const [newDomain, setNewDomain] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  const showError = (error: unknown, fallback: string) => {
    toast({
      description: getSsoDomainErrorDetail(intl, error) ?? fallback,
      variant: 'destructive',
    });
  };

  const handleAdd = async () => {
    if (!tenantId || !newDomain.trim()) return;
    try {
      await addDomain({ variables: { tenantId, domain: newDomain.trim() } });
      setNewDomain('');
    } catch (error) {
      showError(
        error,
        intl.formatMessage({ id: 'Domain Verification / Add Error', defaultMessage: 'Failed to add the domain.' })
      );
    }
  };

  const handleVerify = async (domain: SSODomain) => {
    if (!tenantId) return;
    setBusyId(domain.id);
    try {
      await verifyDomain({ variables: { id: domain.id, tenantId } });
      toast({
        description: intl.formatMessage({
          id: 'Domain Verification / Verified',
          defaultMessage: 'Domain verified. SSO connections can now use it.',
        }),
        variant: 'success',
      });
    } catch (error) {
      showError(
        error,
        intl.formatMessage({ id: 'Domain Verification / Verify Error', defaultMessage: 'Failed to verify the domain.' })
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (domain: SSODomain) => {
    if (!tenantId) return;
    setBusyId(domain.id);
    try {
      await deleteDomain({ variables: { id: domain.id, tenantId } });
    } catch (error) {
      showError(
        error,
        intl.formatMessage({ id: 'Domain Verification / Delete Error', defaultMessage: 'Failed to remove the domain.' })
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleCopy = (value: string) => {
    navigator.clipboard.writeText(value);
    toast({
      description: intl.formatMessage({ id: 'Domain Verification / Copied', defaultMessage: 'Copied to clipboard.' }),
      variant: 'success',
    });
  };

  const isBusy = adding || verifying || deleting;

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <Globe className="h-5 w-5 text-primary" />
          </div>
          <div className="min-w-0">
            <CardTitle className="text-lg">
              <FormattedMessage id="Domain Verification / Title" defaultMessage="Domain verification" />
            </CardTitle>
            <CardDescription className="mt-0.5">
              <FormattedMessage
                id="Domain Verification / Description"
                defaultMessage="Prove you own your company's email domain before SSO can use it. Only verified domains take part in sign-in, provisioning and enforcement."
              />
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {canManageSSO && (
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              void handleAdd();
            }}
          >
            <Input
              aria-label={intl.formatMessage({ id: 'Domain Verification / Domain input', defaultMessage: 'Domain' })}
              placeholder={intl.formatMessage({
                id: 'Domain Verification / Domain placeholder',
                defaultMessage: 'example.com',
              })}
              value={newDomain}
              onChange={(event) => setNewDomain(event.target.value)}
              disabled={isBusy}
              className="sm:flex-1"
            />
            <Button type="submit" variant="outline" disabled={!newDomain.trim() || isBusy}>
              <FormattedMessage id="Domain Verification / Add domain" defaultMessage="Add domain" />
            </Button>
          </form>
        )}

        {domains.length === 0 && (
          <p className="text-sm text-muted-foreground">
            <FormattedMessage
              id="Domain Verification / Empty"
              defaultMessage="No domains claimed yet. Add your company domain to start verification."
            />
          </p>
        )}

        {domains.map((domain: SSODomain) => {
          const status = domain.status.toLowerCase();
          const verified = status === 'verified';
          const lapsed = status === 'lapsed';
          return (
            <div key={domain.id} className="space-y-3 rounded-md border p-4">
              <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="min-w-0 break-all font-mono text-sm">{domain.domain}</span>
                  {verified && (
                    <Badge variant="default" className="shrink-0">
                      <Check className="mr-1 h-3 w-3" />
                      <FormattedMessage id="Domain Verification / Status verified" defaultMessage="Verified" />
                    </Badge>
                  )}
                  {lapsed && (
                    <Badge variant="destructive" className="shrink-0 dark:bg-red-400 dark:hover:bg-red-400/90">
                      <FormattedMessage id="Domain Verification / Status lapsed" defaultMessage="Lapsed" />
                    </Badge>
                  )}
                  {!verified && !lapsed && (
                    <Badge variant="outline" className="shrink-0">
                      <FormattedMessage id="Domain Verification / Status pending" defaultMessage="Pending" />
                    </Badge>
                  )}
                </div>
                {canManageSSO && (
                  <div className="flex shrink-0 items-center gap-2">
                    {!verified && (
                      <Button variant="outline" size="sm" onClick={() => void handleVerify(domain)} disabled={isBusy}>
                        <FormattedMessage id="Domain Verification / Verify" defaultMessage="Verify" />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={intl.formatMessage({
                        id: 'Domain Verification / Remove domain',
                        defaultMessage: 'Remove domain',
                      })}
                      onClick={() => void handleDelete(domain)}
                      disabled={isBusy}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>

              {verified && domain.firstFailedAt && domain.gracePeriodEndsAt && (
                <p className="flex items-start gap-2 text-sm text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    <FormattedMessage
                      id="Domain Verification / Record missing"
                      defaultMessage="Verification record missing since {since}. SSO will be deactivated on {deadline} unless it is restored."
                      values={{
                        since: intl.formatDate(domain.firstFailedAt, { dateStyle: 'medium' }),
                        deadline: intl.formatDate(domain.gracePeriodEndsAt, { dateStyle: 'medium' }),
                      }}
                    />
                  </span>
                </p>
              )}

              {verified && domain.lastCheckedAt && (
                <p className="text-xs text-muted-foreground">
                  <FormattedMessage
                    id="Domain Verification / Last checked"
                    defaultMessage="Last checked {date}"
                    values={{
                      date: intl.formatDate(domain.lastCheckedAt, {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                      }),
                    }}
                  />
                </p>
              )}

              {lapsed && (
                <p className="flex items-start gap-2 text-sm text-destructive dark:text-red-400">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    <FormattedMessage
                      id="Domain Verification / Lapsed explanation"
                      defaultMessage="The verification record has been missing for seven days, so this domain no longer works for SSO. Its SSO connections were deactivated. Publish the record again and verify the domain to use it."
                    />
                  </span>
                </p>
              )}

              {!verified && domain.verificationRecordName && domain.verificationRecordValue && (
                <div className="space-y-4 text-sm">
                  <p className="text-muted-foreground">
                    <FormattedMessage
                      id="Domain Verification / DNS instructions"
                      defaultMessage="Add this TXT record to your DNS, then click Verify. Keep the record in place: SSO checks it every day, and removing it lapses the domain."
                    />
                  </p>
                  <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
                    <span className="text-muted-foreground">
                      <FormattedMessage id="Domain Verification / Record type" defaultMessage="Type" />
                    </span>
                    <span className="font-mono">TXT</span>
                    <span />
                    <span className="text-muted-foreground">
                      <FormattedMessage id="Domain Verification / Record name" defaultMessage="Name" />
                    </span>
                    <span className="break-all font-mono">{domain.verificationRecordName}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      aria-label={intl.formatMessage({
                        id: 'Domain Verification / Copy name',
                        defaultMessage: 'Copy record name',
                      })}
                      onClick={() => handleCopy(domain.verificationRecordName ?? '')}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                    <span className="text-muted-foreground">
                      <FormattedMessage id="Domain Verification / Record value" defaultMessage="Value" />
                    </span>
                    <span className="break-all font-mono">{domain.verificationRecordValue}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      aria-label={intl.formatMessage({
                        id: 'Domain Verification / Copy value',
                        defaultMessage: 'Copy record value',
                      })}
                      onClick={() => handleCopy(domain.verificationRecordValue ?? '')}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
};
