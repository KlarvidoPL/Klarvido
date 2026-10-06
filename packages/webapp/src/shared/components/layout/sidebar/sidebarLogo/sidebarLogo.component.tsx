import { Link } from '@sb/webapp-core/components/buttons';
import { Tooltip, TooltipContent, TooltipTrigger } from '@sb/webapp-core/components/ui/tooltip';
import { cn } from '@sb/webapp-core/lib/utils';
import { useIntl } from 'react-intl';

import { SignetIcon, WordmarkIcon } from '../../../../../images/icons';

export type SidebarLogoProps = {
  isCollapsed: boolean;
  logoColor: string;
  to: string;
  onLogoClick?: () => void;
};
export const SidebarLogo = ({ isCollapsed, logoColor, to, onLogoClick }: SidebarLogoProps) => {
  const intl = useIntl();

  const ariaLabel = intl.formatMessage({
    id: 'Sidebar / Logo link aria label',
    defaultMessage: 'Go back home',
  });

  const tooltipLabel = intl.formatMessage({
    id: 'Sidebar / Logo tooltip',
    defaultMessage: 'Go to dashboard',
  });

  if (isCollapsed) {
    return (
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>
          <Link
            to={to}
            onClick={onLogoClick}
            className="group flex items-center justify-center"
            aria-label={ariaLabel}
          >
            <div
              className={cn(
                'flex h-9 w-9 items-center justify-center rounded-lg',
                'border border-border bg-background',
                'transition-all duration-200',
                'group-hover:border-muted-foreground/30 group-hover:bg-accent group-hover:shadow-sm',
                'group-active:scale-95'
              )}
            >
              <SignetIcon
                color={logoColor}
                className="h-5 w-5 transition-transform duration-200 group-hover:scale-105"
              />
            </div>
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right">{tooltipLabel}</TooltipContent>
      </Tooltip>
    );
  }

  return (
    <Link
      to={to}
      onClick={onLogoClick}
      className="group flex items-center justify-center"
      aria-label={ariaLabel}
    >
      <div
        className={cn(
          'flex items-center gap-2',
          'transition-opacity duration-200',
          'group-hover:opacity-80'
        )}
      >
        <SignetIcon color={logoColor} className="h-7 w-7 shrink-0" />
        <WordmarkIcon color={logoColor} className="h-5 w-24" />
      </div>
    </Link>
  );
};
