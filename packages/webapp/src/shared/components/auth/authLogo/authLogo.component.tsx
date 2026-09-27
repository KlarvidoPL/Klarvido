import { useTheme } from '@sb/webapp-core/hooks/useTheme/useTheme';
import { Themes } from '@sb/webapp-core/providers/themeProvider';

import { SignetIcon } from '../../../../images/icons';

export const AuthLogo = () => {
  const { theme } = useTheme();
  const logoColor = theme === Themes.DARK ? 'white' : 'black';

  return (
    <div className="my-4 flex items-center gap-2">
      <SignetIcon color={logoColor} size={36} />
      <span className="text-2xl font-bold tracking-tight" style={{ color: logoColor }}>
        klarvido
      </span>
    </div>
  );
};
