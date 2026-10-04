import { Button } from '@sb/webapp-core/components/buttons';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@sb/webapp-core/components/ui/dialog';
import { Input } from '@sb/webapp-core/components/ui/input';
import { useOpenState } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { Fingerprint, Key, Loader2, Plus, Search, Smartphone, Trash2, User, X } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

import { useCurrentTenant } from '../../../../providers';
import { useTenantPasskeys } from '../../../../hooks/useTenantPasskeys';
import { AddPasskeyModal } from './addPasskeyModal';

type Passkey = {
  id: string;
  name: string;
  authenticatorType: string;
  createdAt: string;
  lastUsedAt: string | null;
  useCount: number;
  userEmail?: string;
  userName?: string;
};

export type PasskeysCardProps = {
  canManagePasskeys?: boolean;
};

// Mirrors the per-type icon shown in the personal Profile passkeys list
// (packages/webapp/src/shared/components/auth/passkeysForm) for visual consistency.
const getAuthenticatorIcon = (type: string) => {
  switch (type) {
    case 'platform':
      return <Smartphone className="h-4 w-4" />;
    case 'cross-platform':
      return <Key className="h-4 w-4" />;
    default:
      return <Fingerprint className="h-4 w-4" />;
  }
};

export const PasskeysCard = ({ canManagePasskeys = false }: PasskeysCardProps) => {
  const { isOpen: isModalOpen, setIsOpen: setIsModalOpen } = useOpenState(false);
  const { toast } = useToast();
  const intl = useIntl();
  const { data: currentTenant } = useCurrentTenant();
  const tenantId = currentTenant?.id;

  const [searchQuery, setSearchQuery] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { passkeys, loading: isLoading, refetch, deletePasskey, deleteTenantPasskey } = useTenantPasskeys(
    tenantId,
    canManagePasskeys,
    canManagePasskeys ? searchQuery : undefined
  );

  const handleDelete = async (passkeyId: string) => {
    setDeletingId(passkeyId);
    try {
      if (canManagePasskeys) {
        if (!tenantId) {
          toast({
            description: intl.formatMessage({
              defaultMessage: 'Tenant context is required to delete passkeys.',
              id: 'Passkeys Card / Tenant Required',
            }),
            variant: 'destructive',
          });
          return;
        }
        await deleteTenantPasskey({ variables: { id: passkeyId, tenantId } });
      } else {
        await deletePasskey({ variables: { input: { id: passkeyId } } });
      }
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Passkey deleted successfully.',
          id: 'Passkeys Card / Delete Success',
        }),
        variant: 'success',
      });
    } catch {
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Failed to delete passkey. Please try again.',
          id: 'Passkeys Card / Delete Error',
        }),
        variant: 'destructive',
      });
    } finally {
      setDeletingId(null);
    }
  };

  const handleRegistrationSuccess = () => {
    refetch();
  };

  return (
    <>
      <Card>
        <CardHeader className="pb-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Key className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2 text-lg">
                <FormattedMessage
                  defaultMessage="Passkeys (WebAuthn)"
                  id="Tenant Security Settings / Passkeys Header"
                />
                {passkeys.length > 0 && (
                  <Badge variant="secondary">{passkeys.length}</Badge>
                )}
              </CardTitle>
              <CardDescription className="mt-0.5">
                {canManagePasskeys ? (
                  <FormattedMessage
                    defaultMessage="Manage passkeys for all users in your organization"
                    id="Tenant Security Settings / Passkeys Admin Description"
                  />
                ) : (
                  <FormattedMessage
                    defaultMessage="Use biometrics or security keys for passwordless authentication"
                    id="Tenant Security Settings / Passkeys Description"
                  />
                )}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search Input - always visible for admins so a no-match search can be cleared */}
          {canManagePasskeys && (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={intl.formatMessage({
                  defaultMessage: 'Search by user name or email...',
                  id: 'Passkeys Card / Search Placeholder',
                })}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-10"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label={intl.formatMessage({
                    defaultMessage: 'Clear search',
                    id: 'Passkeys Card / Clear Search',
                  })}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          )}

          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : passkeys.length === 0 ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 rounded-lg border bg-card p-4">
                <div className="shrink-0 rounded-full bg-muted p-2">
                  <Key className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium">
                    {searchQuery ? (
                      <FormattedMessage
                        defaultMessage="No passkeys match your search"
                        id="Tenant Security Settings / No Passkeys Match"
                      />
                    ) : (
                      <FormattedMessage
                        defaultMessage="No passkeys registered"
                        id="Tenant Security Settings / No Passkeys"
                      />
                    )}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {searchQuery ? (
                      <FormattedMessage
                        defaultMessage="Try a different search term"
                        id="Tenant Security Settings / No Match Hint"
                      />
                    ) : canManagePasskeys ? (
                      <FormattedMessage
                        defaultMessage="No users in your organization have registered passkeys yet"
                        id="Tenant Security Settings / Passkey Admin Hint"
                      />
                    ) : (
                      <FormattedMessage
                        defaultMessage="Register a passkey for faster, more secure sign-in"
                        id="Tenant Security Settings / Passkey Hint"
                      />
                    )}
                  </p>
                </div>
              </div>
              <Button variant="outline" size="sm" className="w-full" onClick={() => setIsModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {canManagePasskeys ? (
                  <FormattedMessage defaultMessage="Add my passkey" id="Passkeys Card / Add My Passkey Button" />
                ) : (
                  <FormattedMessage
                    defaultMessage="Add Passkey"
                    id="Tenant Security Settings / Add Passkey Button"
                  />
                )}
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {passkeys.map((passkey) => (
                <div
                  key={passkey.id}
                  className="flex items-center justify-between gap-3 rounded-lg border bg-card p-4"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      {getAuthenticatorIcon(passkey.authenticatorType)}
                    </div>
                    <div className="min-w-0">
                      <div className="mb-1.5 flex min-w-0 items-center gap-2">
                        <p className="min-w-0 truncate text-sm font-medium" title={passkey.name}>
                          {passkey.name}
                        </p>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {passkey.authenticatorType === 'platform' ? (
                            <FormattedMessage defaultMessage="This device" id="Passkeys / Platform" />
                          ) : (
                            <FormattedMessage defaultMessage="Security key" id="Passkeys / Cross-platform" />
                          )}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        {/* Show user info for admin view */}
                        {canManagePasskeys && passkey.userEmail != null && (
                          <>
                            <span className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {String(passkey.userName ?? passkey.userEmail ?? '')}
                            </span>
                            <span>•</span>
                          </>
                        )}
                        <span>
                          <FormattedMessage
                            defaultMessage="Created {date}"
                            id="Passkeys / Created date"
                            values={{ date: intl.formatDate(passkey.createdAt as string) }}
                          />
                        </span>
                        <span>•</span>
                        <span>
                          {passkey.lastUsedAt != null ? (
                            <FormattedMessage
                              defaultMessage="Last used {date}"
                              id="Passkeys / Last used date"
                              values={{ date: intl.formatDate(passkey.lastUsedAt as string) }}
                            />
                          ) : (
                            <FormattedMessage defaultMessage="Never used" id="Passkeys / Never used" />
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(passkey.id)}
                    disabled={deletingId === passkey.id}
                    className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive dark:text-red-400"
                  >
                    {deletingId === passkey.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              ))}

              <Button variant="outline" size="sm" className="w-full" onClick={() => setIsModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                {canManagePasskeys ? (
                  <FormattedMessage defaultMessage="Add my passkey" id="Passkeys Card / Add My Passkey Button" />
                ) : (
                  <FormattedMessage
                    defaultMessage="Add another passkey"
                    id="Passkeys Card / Add Another Button"
                  />
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[450px]" aria-describedby="passkey-dialog-description">
          {/* Visually hidden but accessible title and description for screen readers */}
          <DialogTitle className="sr-only">
            <FormattedMessage defaultMessage="Register a Passkey" id="Add Passkey Modal / Title" />
          </DialogTitle>
          <DialogDescription id="passkey-dialog-description" className="sr-only">
            <FormattedMessage
              defaultMessage="Secure, passwordless sign-in"
              id="Add Passkey Modal / Subtitle"
            />
          </DialogDescription>
          <AddPasskeyModal closeModal={() => setIsModalOpen(false)} onSuccess={handleRegistrationSuccess} />
        </DialogContent>
      </Dialog>
    </>
  );
};
