import { IntlShape } from 'react-intl';

// Translated permission name/description, keyed by the stable permission code from
// apps/multitenancy/permissions.py + apps/backup/permissions.py. Any permission code not
// listed here (e.g. a future app-registered one) falls back to the raw API text/code passed
// in, same fallback pattern used for unlisted categories/system roles elsewhere. Shared by
// every place that renders a permission's name (roles settings page, per-member role editor,
// invite-member form, and their respective error-message helpers).
export const getPermissionDisplay = (
  intl: IntlShape,
  code: string,
  fallbackName: string,
  fallbackDescription?: string
): { name: string; description?: string } => {
  // Each case uses literal id/defaultMessage (not a template string) so `extract-intl:master`
  // can statically pick it up - a dynamically-built id would be invisible to that extractor.
  switch (code) {
    case 'org.settings.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Organization Settings', id: 'Roles / Permission / org.settings.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View organization name, billing email, and general settings',
          id: 'Roles / Permission / org.settings.view / Description',
        }),
      };
    case 'org.settings.edit':
      return {
        name: intl.formatMessage({ defaultMessage: 'Edit Organization Settings', id: 'Roles / Permission / org.settings.edit / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Modify organization name, billing email, and general settings',
          id: 'Roles / Permission / org.settings.edit / Description',
        }),
      };
    case 'org.delete':
      return {
        name: intl.formatMessage({ defaultMessage: 'Delete Organization', id: 'Roles / Permission / org.delete / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Permanently delete the organization and all its data',
          id: 'Roles / Permission / org.delete / Description',
        }),
      };
    case 'org.roles.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Organization Roles', id: 'Roles / Permission / org.roles.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View defined roles and their permissions',
          id: 'Roles / Permission / org.roles.view / Description',
        }),
      };
    case 'org.roles.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage Organization Roles', id: 'Roles / Permission / org.roles.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Create, edit, and delete custom roles',
          id: 'Roles / Permission / org.roles.manage / Description',
        }),
      };
    case 'members.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Members', id: 'Roles / Permission / members.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View the list of organization members and their roles',
          id: 'Roles / Permission / members.view / Description',
        }),
      };
    case 'members.invite':
      return {
        name: intl.formatMessage({ defaultMessage: 'Invite Members', id: 'Roles / Permission / members.invite / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Send invitations to new members',
          id: 'Roles / Permission / members.invite / Description',
        }),
      };
    case 'members.roles.edit':
      return {
        name: intl.formatMessage({ defaultMessage: 'Edit Member Roles', id: 'Roles / Permission / members.roles.edit / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Change roles assigned to existing members',
          id: 'Roles / Permission / members.roles.edit / Description',
        }),
      };
    case 'members.remove':
      return {
        name: intl.formatMessage({ defaultMessage: 'Remove Members', id: 'Roles / Permission / members.remove / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Remove members from the organization',
          id: 'Roles / Permission / members.remove / Description',
        }),
      };
    case 'security.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Security Settings', id: 'Roles / Permission / security.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View SSO connections, passkeys, and security configurations',
          id: 'Roles / Permission / security.view / Description',
        }),
      };
    case 'security.sso.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage SSO', id: 'Roles / Permission / security.sso.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Configure Single Sign-On connections and SCIM provisioning',
          id: 'Roles / Permission / security.sso.manage / Description',
        }),
      };
    case 'security.logs.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Activity Logs', id: 'Roles / Permission / security.logs.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View audit logs of actions performed in the organization',
          id: 'Roles / Permission / security.logs.view / Description',
        }),
      };
    case 'security.logs.export':
      return {
        name: intl.formatMessage({ defaultMessage: 'Export Activity Logs', id: 'Roles / Permission / security.logs.export / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Export activity logs to CSV or other formats',
          id: 'Roles / Permission / security.logs.export / Description',
        }),
      };
    case 'billing.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Billing', id: 'Roles / Permission / billing.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View subscription status, invoices, and payment methods',
          id: 'Roles / Permission / billing.view / Description',
        }),
      };
    case 'billing.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage Billing', id: 'Roles / Permission / billing.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Change subscription plan, update payment methods, and manage billing',
          id: 'Roles / Permission / billing.manage / Description',
        }),
      };
    case 'features.ai.use':
      return {
        name: intl.formatMessage({ defaultMessage: 'Use AI Features', id: 'Roles / Permission / features.ai.use / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Access and use OpenAI integration and AI-powered features',
          id: 'Roles / Permission / features.ai.use / Description',
        }),
      };
    case 'features.documents.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Documents', id: 'Roles / Permission / features.documents.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View uploaded documents',
          id: 'Roles / Permission / features.documents.view / Description',
        }),
      };
    case 'features.documents.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage Documents', id: 'Roles / Permission / features.documents.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Upload, edit, and delete documents',
          id: 'Roles / Permission / features.documents.manage / Description',
        }),
      };
    case 'features.content.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Content Items', id: 'Roles / Permission / features.content.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View content items from CMS',
          id: 'Roles / Permission / features.content.view / Description',
        }),
      };
    case 'features.crud.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View CRUD Demo Items', id: 'Roles / Permission / features.crud.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View CRUD demo items',
          id: 'Roles / Permission / features.crud.view / Description',
        }),
      };
    case 'features.crud.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage CRUD Demo Items', id: 'Roles / Permission / features.crud.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Create, edit, and delete CRUD demo items',
          id: 'Roles / Permission / features.crud.manage / Description',
        }),
      };
    case 'backup.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View Backup Settings', id: 'Roles / Permission / backup.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View backup configuration and history',
          id: 'Roles / Permission / backup.view / Description',
        }),
      };
    case 'backup.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage Backups', id: 'Roles / Permission / backup.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Configure backups, trigger manual backups, and manage backup settings',
          id: 'Roles / Permission / backup.manage / Description',
        }),
      };
    case 'security.ksef.view':
      return {
        name: intl.formatMessage({ defaultMessage: 'View KSeF Connection', id: 'Roles / Permission / security.ksef.view / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View whether a KSeF token is connected and when it was last verified',
          id: 'Roles / Permission / security.ksef.view / Description',
        }),
      };
    case 'security.ksef.manage':
      return {
        name: intl.formatMessage({ defaultMessage: 'Manage KSeF Connection', id: 'Roles / Permission / security.ksef.manage / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Add, test, replace or remove the KSeF token',
          id: 'Roles / Permission / security.ksef.manage / Description',
        }),
      };
    default:
      return { name: fallbackName, description: fallbackDescription };
  }
};
