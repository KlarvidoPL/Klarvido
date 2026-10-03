import { IntlShape } from 'react-intl';

/**
 * Translated name/description for a system role, keyed by systemRoleType. Custom (non-system)
 * roles always keep their raw freeform name/description - those are user-entered text and must
 * never be auto-translated. Shared by every place that renders an OrganizationRole's name
 * (roles settings page, invite-member form, per-member role editor).
 */
export const getSystemRoleDisplay = (
  intl: IntlShape,
  systemRoleType: string | null | undefined,
  fallbackName: string,
  fallbackDescription?: string
): { name: string; description?: string } => {
  switch (systemRoleType) {
    case 'OWNER':
      return {
        name: intl.formatMessage({ defaultMessage: 'Owner', id: 'Roles / System Role / Owner / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Full access to all organization features',
          id: 'Roles / System Role / Owner / Description',
        }),
      };
    case 'ADMIN':
      return {
        name: intl.formatMessage({ defaultMessage: 'Administrator', id: 'Roles / System Role / Administrator / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'Manage organization settings and members',
          id: 'Roles / System Role / Administrator / Description',
        }),
      };
    case 'MEMBER':
      return {
        name: intl.formatMessage({ defaultMessage: 'Member', id: 'Roles / System Role / Member / Name' }),
        description: intl.formatMessage({
          defaultMessage: 'View access to organization data',
          id: 'Roles / System Role / Member / Description',
        }),
      };
    default:
      return { name: fallbackName, description: fallbackDescription };
  }
};
