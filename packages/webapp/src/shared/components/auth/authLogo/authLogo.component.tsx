import { useTheme } from '@sb/webapp-core/hooks/useTheme/useTheme';
import { Themes } from '@sb/webapp-core/providers/themeProvider';

import { SignetIcon, WordmarkIcon } from '../../../../images/icons';
import { BRAND_COLORS } from '../../../constants';

export const AuthLogo = () => {
  const { theme } = useTheme();
  const logoColor = theme === Themes.DARK ? BRAND_COLORS.white : BRAND_COLORS.navy;

  return (
    <div className="my-4 flex items-center gap-3" role="img" aria-label="Klarvido">
      <SignetIcon color={logoColor} className="h-10 w-10 shrink-0" />
      <WordmarkIcon color={logoColor} className="h-7 w-32" />
    </div>
  );
};
