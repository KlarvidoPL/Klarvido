export type KlarvidoShellUser = {
  avatar?: string | null;
  email: string;
  firstName?: string | null;
  lastName?: string | null;
};

export type KlarvidoShellProps = {
  companyName?: string | null;
  contentUrl?: string;
  onLogout: () => void;
  user: KlarvidoShellUser;
};
