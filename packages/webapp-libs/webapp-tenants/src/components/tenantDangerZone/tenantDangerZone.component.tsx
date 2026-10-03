import { ConfirmDialog } from '@sb/webapp-core/components/confirmDialog';
import { Paragraph } from '@sb/webapp-core/components/typography';
import { Button, buttonVariants } from '@sb/webapp-core/components/ui/button';
import { AlertTriangle } from 'lucide-react';
import { FormattedMessage, useIntl } from 'react-intl';

import { usePermissionCheck } from '../../hooks';
import { useCurrentTenant } from '../../providers';
import { useTenantDelete } from './tenantDangerZone.hook';

export const TenantDangerZone = () => {
  const intl = useIntl();
  // Permission check for delete organization
  const { hasPermission: canDelete, loading: permLoading } = usePermissionCheck('org.delete');

  const { deleteTenant, loading } = useTenantDelete();
  const { data: currentTenant } = useCurrentTenant();

  const deleteConfirmationKeyword = intl.formatMessage({
    defaultMessage: 'DELETE',
    id: 'Tenant General Settings / Danger Zone / Confirm Dialog / Delete keyword',
  });
  const deleteConfirmationText = currentTenant?.name
    ? `${deleteConfirmationKeyword} ${currentTenant.name}`
    : undefined;

  // If user cannot delete, show a message explaining why
  const cannotDeleteMessage = !canDelete && !permLoading;

  return (
    <div className="space-y-6">
      <div className="flex gap-2 items-center">
        <AlertTriangle className="h-5 w-5 text-destructive dark:text-red-400" />
        <h3 className="text-lg font-semibold text-destructive dark:text-red-400">
          <FormattedMessage defaultMessage="Danger Zone" id="Tenant General Settings / Danger Zone / Header" />
        </h3>
      </div>

      <div className="rounded-lg border-2 border-destructive/50 bg-destructive/5 p-6 dark:border-red-400/50">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <div className="font-semibold text-foreground">
              <FormattedMessage
                defaultMessage="Delete this organization"
                id="Tenant General Settings / Danger Zone / Delete title"
              />
            </div>
            {cannotDeleteMessage ? (
              <Paragraph className="text-sm text-muted-foreground">
                <FormattedMessage
                  defaultMessage="You don't have permission to delete this organization"
                  id="Tenant General Settings / Danger Zone / Delete no permission"
                />
              </Paragraph>
            ) : (
              <Paragraph className="text-sm text-muted-foreground">
                <FormattedMessage
                  defaultMessage="Once you delete an organization, there is no going back. Please be certain."
                  id="Tenant General Settings / Danger Zone / Delete warning"
                />
              </Paragraph>
            )}
          </div>

          <ConfirmDialog
            onContinue={deleteTenant}
            variant="destructive"
            title={
              <FormattedMessage
                defaultMessage="Are you absolutely sure?"
                id="Tenant General Settings / Danger Zone / Confirm Dialog / Tenant Delete Button"
              />
            }
            description={
              <FormattedMessage
                defaultMessage="This action cannot be undone. This will permanently delete your organization from our servers."
                id="Tenant Danger Settings / Danger Zone / Confirm Dialog / Tenant Delete Description"
              />
            }
            confirmationText={deleteConfirmationText}
          >
            <Button disabled={!canDelete || loading || permLoading} className={buttonVariants({ variant: 'destructive' })}>
              <FormattedMessage
                defaultMessage="Delete organization"
                id="Tenant General Settings / Danger Zone / Tenant Delete Button"
              />
            </Button>
          </ConfirmDialog>
        </div>
      </div>
    </div>
  );
};
