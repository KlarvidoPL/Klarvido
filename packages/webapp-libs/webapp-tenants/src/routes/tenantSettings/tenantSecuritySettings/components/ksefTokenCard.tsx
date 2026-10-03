import { Button, ButtonVariant } from '@sb/webapp-core/components/buttons';
import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button as ShadcnButton } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@sb/webapp-core/components/ui/dialog';
import { useOpenState } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { AlertTriangle, CheckCircle2, KeyRound, Loader2, RefreshCw, Trash2, XCircle } from 'lucide-react';
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
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5" />
              <FormattedMessage id="KSeF / Card title" defaultMessage="KSeF connection" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                id="KSeF / Card description"
                defaultMessage="The KSeF token lets Klarvido read your company invoices from KSeF."
              />
            </CardDescription>
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
              <div className="flex flex-wrap gap-2">
                <Button variant={ButtonVariant.SECONDARY} onClick={handleTest} disabled={busy}>
                  {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                  <FormattedMessage id="KSeF / Test connection button" defaultMessage="Test connection" />
                </Button>
                <Button variant={ButtonVariant.SECONDARY} onClick={() => setIsModalOpen(true)} disabled={busy}>
                  <FormattedMessage id="KSeF / Replace token button" defaultMessage="Replace token" />
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
                  <ShadcnButton variant="destructive" disabled={busy}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    <FormattedMessage id="KSeF / Remove token button" defaultMessage="Remove" />
                  </ShadcnButton>
                </ConfirmDialog>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-start gap-4 rounded-lg border border-dashed p-6">
            <p className="text-sm text-muted-foreground">
              <FormattedMessage
                id="KSeF / Empty state"
                defaultMessage="No KSeF token is connected. Connect one to start reading company invoices from KSeF."
              />
            </p>
            {canManageKsef && (
              <Button onClick={() => setIsModalOpen(true)}>
                <KeyRound className="mr-2 h-4 w-4" />
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
