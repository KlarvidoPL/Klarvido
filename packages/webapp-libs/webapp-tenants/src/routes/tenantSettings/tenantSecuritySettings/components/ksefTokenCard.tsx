import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button as ShadcnButton } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@sb/webapp-core/components/ui/dialog';
import { useOpenState } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { AlertTriangle, CheckCircle2, KeyRound, Loader2, Plus, RefreshCw, Trash2, XCircle } from 'lucide-react';
import { FormattedDate, FormattedMessage, useIntl } from 'react-intl';

import { useTenantKsef } from '../../../../hooks/useTenantKsef';
import { useCurrentTenant } from '../../../../providers';
import { AddKsefTokenModal } from './addKsefTokenModal';
import { getKsefErrorMessage } from './ksefErrors';

export type KsefTokenCardProps = {
  canManageKsef?: boolean;
};

const STATUS_BADGE_CLASSES: Record<string, string> = {
  VALID: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  UNVERIFIED: 'bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20',
  INVALID: 'bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20',
};
const UNVERIFIED_BADGE_CLASSES = STATUS_BADGE_CLASSES['UNVERIFIED'];

export const KsefTokenCard = ({ canManageKsef = false }: KsefTokenCardProps) => {
  const intl = useIntl();
  const { toast } = useToast();
  const { data: currentTenant } = useCurrentTenant();
  const tenantId = currentTenant?.id;
  const { isOpen: isModalOpen, setIsOpen: setIsModalOpen } = useOpenState(false);

  const { credential, loading, refetch, testToken, testing, deleteToken, deleting } = useTenantKsef(tenantId, true);

  const handleTest = async () => {
    if (!tenantId) return;
    const { data } = await testToken({ variables: { tenantId } });
    const result = data?.testKsefToken;
    if (result?.ok) {
      toast({
        description: intl.formatMessage({ id: 'KSeF / Test passed toast', defaultMessage: 'KSeF token is valid.' }),
        variant: 'success',
      });
    } else {
      toast({ description: getKsefErrorMessage(intl, result?.errorCode), variant: 'destructive' });
    }
  };

  const handleDelete = async () => {
    if (!tenantId) return;
    const { data } = await deleteToken({ variables: { tenantId } });
    if (data?.deleteKsefToken?.ok) {
      toast({
        description: intl.formatMessage({ id: 'KSeF / Removed toast', defaultMessage: 'KSeF token removed.' }),
        variant: 'info',
      });
    } else {
      toast({ description: getKsefErrorMessage(intl, data?.deleteKsefToken?.errorCode), variant: 'destructive' });
    }
  };

  const statusLabel = (status: string | null | undefined) => {
    switch (status) {
      case 'VALID':
        return intl.formatMessage({ id: 'KSeF / Status valid', defaultMessage: 'Connected' });
      case 'INVALID':
        return intl.formatMessage({ id: 'KSeF / Status invalid', defaultMessage: 'Token rejected' });
      default:
        return intl.formatMessage({ id: 'KSeF / Status unverified', defaultMessage: 'Not verified' });
    }
  };

  const busy = testing || deleting;

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <KeyRound className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">
                <FormattedMessage id="KSeF / Card title" defaultMessage="KSeF connection" />
              </CardTitle>
              <CardDescription className="mt-0.5">
                <FormattedMessage
                  id="KSeF / Card description"
                  defaultMessage="The KSeF token lets Klarvido read your company invoices from KSeF."
                />
              </CardDescription>
            </div>
          </div>
          {credential && (
            <Badge className={STATUS_BADGE_CLASSES[credential.status ?? ''] ?? UNVERIFIED_BADGE_CLASSES}>
              {credential.status === 'VALID' && <CheckCircle2 className="mr-1 h-3 w-3" />}
              {credential.status === 'INVALID' && <XCircle className="mr-1 h-3 w-3" />}
              {credential.status !== 'VALID' && credential.status !== 'INVALID' && (
                <AlertTriangle className="mr-1 h-3 w-3" />
              )}
              {statusLabel(credential.status)}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {loading && !credential ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <FormattedMessage id="KSeF / Loading" defaultMessage="Loading KSeF connection..." />
          </div>
        ) : credential ? (
          <>
            <div className="grid gap-3 rounded-lg border p-4 text-sm sm:grid-cols-2">
              <div>
                <p className="text-muted-foreground">
                  <FormattedMessage id="KSeF / Token name label" defaultMessage="Token name in KSeF" />
                </p>
                {credential.tokenName ? (
                  <p className="break-all">{credential.tokenName}</p>
                ) : (
                  <p className="font-mono">••••{credential.tokenHint}</p>
                )}
              </div>
              <div>
                <p className="text-muted-foreground">
                  <FormattedMessage id="KSeF / Last verified label" defaultMessage="Last verified" />
                </p>
                <p>
                  {credential.lastVerifiedAt ? (
                    <FormattedDate value={credential.lastVerifiedAt} dateStyle="medium" timeStyle="short" />
                  ) : (
                    <FormattedMessage id="KSeF / Never verified" defaultMessage="Never" />
                  )}
                </p>
              </div>
            </div>

            {credential.status === 'UNVERIFIED' && (
              <p className="text-sm text-amber-700 dark:text-amber-400">
                <FormattedMessage
                  id="KSeF / Unverified hint"
                  defaultMessage="KSeF could not be reached when the token was saved. Test the connection to verify it."
                />
              </p>
            )}
            {credential.status === 'INVALID' && (
              <p className="text-sm text-red-700 dark:text-red-400">
                <FormattedMessage
                  id="KSeF / Invalid hint"
                  defaultMessage="KSeF no longer accepts this token. Replace it with a new one."
                />
              </p>
            )}

            {canManageKsef && (
              <div className="flex flex-nowrap gap-2">
                <Button variant={ButtonVariant.SECONDARY} onClick={handleTest} disabled={busy} className="px-3 sm:px-4">
                  {testing ? <Loader2 className="h-4 w-4 animate-spin sm:mr-2" /> : <RefreshCw className="h-4 w-4 sm:mr-2" />}
                  <span className="sr-only sm:not-sr-only">
                    <FormattedMessage id="KSeF / Test connection button" defaultMessage="Test connection" />
                  </span>
                </Button>
                <Button
                  variant={ButtonVariant.SECONDARY}
                  onClick={() => setIsModalOpen(true)}
                  disabled={busy}
                  className="px-3 sm:px-4"
                >
                  <KeyRound className="h-4 w-4 sm:mr-2" />
                  <span className="sr-only sm:not-sr-only">
                    <FormattedMessage id="KSeF / Replace token button" defaultMessage="Replace token" />
                  </span>
                </Button>
                <ConfirmDialog
                  onContinue={handleDelete}
                  variant="destructive"
                  title={<FormattedMessage id="KSeF / Remove dialog title" defaultMessage="Remove KSeF token" />}
                  description={
                    <FormattedMessage
                      id="KSeF / Remove dialog description"
                      defaultMessage="Klarvido will stop reading invoices from KSeF until a new token is connected."
                    />
                  }
                >
                  <ShadcnButton variant="destructive" disabled={busy} className="px-3 sm:px-4">
                    <Trash2 className="h-4 w-4 sm:mr-2" />
                    <span className="sr-only sm:not-sr-only">
                      <FormattedMessage id="KSeF / Remove token button" defaultMessage="Remove" />
                    </span>
                  </ShadcnButton>
                </ConfirmDialog>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 p-8 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
              <KeyRound className="h-7 w-7 text-primary" />
            </div>
            <h3 className="mb-1 text-base font-semibold">
              <FormattedMessage id="KSeF / Empty title" defaultMessage="No KSeF token connected" />
            </h3>
            <p className="mb-4 max-w-sm text-sm text-muted-foreground">
              <FormattedMessage
                id="KSeF / Empty state"
                defaultMessage="Connect a token to start reading your company invoices from KSeF."
              />
            </p>
            {canManageKsef && (
              <Button onClick={() => setIsModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                <FormattedMessage id="KSeF / Connect token button" defaultMessage="Connect KSeF token" />
              </Button>
            )}
          </div>
        )}
      </CardContent>

      {tenantId && (
        <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
          <DialogContent>
            <DialogTitle className="sr-only">
              <FormattedMessage id="KSeF / Modal title sr" defaultMessage="Connect KSeF" />
            </DialogTitle>
            <DialogDescription className="sr-only">
              <FormattedMessage
                id="KSeF / Modal description sr"
                defaultMessage="Instructions for generating and pasting a KSeF token"
              />
            </DialogDescription>
            <AddKsefTokenModal tenantId={tenantId} closeModal={() => setIsModalOpen(false)} onSaved={() => refetch()} />
          </DialogContent>
        </Dialog>
      )}
    </Card>
  );
};
