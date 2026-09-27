import { CrudItemCreated, CrudItemUpdated } from '@sb/webapp-crud-demo/notifications';

import { NotificationTypes } from '@sb/webapp-notifications';
import { backupNotificationTemplates } from '@sb/webapp-backup';
import {
  ActionLogExportFailed,
  ActionLogExportReady,
  PasskeyRegistered,
  SSOConnectionActivated,
  SSOConnectionDeactivated,
  TenantInvitationAccepted,
  TenantInvitationCreated,
  TenantInvitationDeclined,
} from '@sb/webapp-tenants/notifications';
import { ElementType } from 'react';

const templates: Record<NotificationTypes, ElementType> = {
  [NotificationTypes.CRUD_ITEM_CREATED]: CrudItemCreated,
  [NotificationTypes.CRUD_ITEM_UPDATED]: CrudItemUpdated,
  [NotificationTypes.TENANT_INVITATION_CREATED]: TenantInvitationCreated,
  [NotificationTypes.TENANT_INVITATION_ACCEPTED]: TenantInvitationAccepted,
  [NotificationTypes.TENANT_INVITATION_DECLINED]: TenantInvitationDeclined,
  [NotificationTypes.ACTION_LOG_EXPORT_READY]: ActionLogExportReady,
  [NotificationTypes.ACTION_LOG_EXPORT_FAILED]: ActionLogExportFailed,
  [NotificationTypes.SSO_CONNECTION_ACTIVATED]: SSOConnectionActivated,
  [NotificationTypes.SSO_CONNECTION_DEACTIVATED]: SSOConnectionDeactivated,
  [NotificationTypes.PASSKEY_REGISTERED]: PasskeyRegistered,
  // Backup notifications
  ...backupNotificationTemplates,
};
export default templates;
