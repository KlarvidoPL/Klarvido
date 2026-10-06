import { nestedPath } from '@sb/webapp-core/utils';

export const RoutesConfig = {
  home: '/',
  organizations: 'organizations',
  legacyCompanies: 'companies',
  tenant: nestedPath('tenant', {
    onboarding: 'onboarding',
    settings: nestedPath('settings', {
      members: 'members',
      general: 'general',
      security: 'security',
      activityLogs: 'activity-logs',
      roles: 'roles',
      backup: 'backup',
    }),
    accessDenied: 'access-denied',
  }),
};
