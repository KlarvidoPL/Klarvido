export type KlarvidoShellUser = {
  avatar?: string | null;
  email: string;
  firstName?: string | null;
  lastName?: string | null;
};

export type KlarvidoShellProps = {
  companyName?: string | null;
  onLogout: () => void;
  tenantId?: string;
  user: KlarvidoShellUser;
};

export type KlarvidoProductRoute =
  | 'today'
  | 'decisions'
  | 'analysis'
  | 'actions'
  | 'invoices'
  | 'sources'
  | 'settings';
