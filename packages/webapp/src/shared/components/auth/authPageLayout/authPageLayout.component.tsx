import { Switch } from '@sb/webapp-core/components/ui/switch';
import { cn } from '@sb/webapp-core/lib/utils';
import { ReactNode, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

import { BRAND_COLORS } from '../../../constants';
import { Prism } from '../../backgrounds/prism';
import { Topography } from '../../backgrounds/topography';
import { FloatingThemeToggle } from '../floatingThemeToggle';

export const AUTH_GLASS_CARD_CLASS =
  'border-white/45 !bg-transparent bg-gradient-to-br from-background/30 via-background/20 to-background/10 shadow-2xl shadow-slate-950/20 ring-1 ring-white/30 backdrop-blur-sm backdrop-saturate-125 dark:border-white/20 dark:from-background/50 dark:via-background/35 dark:to-background/20 dark:ring-white/15';

export type AuthPageLayoutProps = {
  children: ReactNode;
};

export const AuthPageLayout = ({ children }: AuthPageLayoutProps) => {
  const intl = useIntl();
  const [showPrism, setShowPrism] = useState(false);

  return (
    <div
      className={cn(
        'relative isolate min-h-screen overflow-x-hidden',
        showPrism ? 'bg-slate-950' : 'bg-slate-50 dark:bg-slate-950'
      )}
    >
      <div className="fixed inset-0 z-0" aria-hidden="true">
        {showPrism ? (
          <Prism
            animationType="hover"
            timeScale={0.5}
            height={3.5}
            baseWidth={5.5}
            scale={3.6}
            hueShift={0}
            colorFrequency={1}
            noise={0.5}
            glow={1}
            hoverStrength={2}
            inertia={0.05}
          />
        ) : (
          <Topography
            lowColor={BRAND_COLORS.navy}
            midColor={BRAND_COLORS.amber}
            highColor={BRAND_COLORS.white}
            speed={0.35}
            morphAmount={3}
            morphSpeed={0.05}
            bands={2}
            thickness={0.01}
            scale={1}
            pixelSize={1}
            glow={0.5}
            colorMode="elevation"
            contrast={3}
            brightness={1}
            fillBands={false}
            opacity={1}
            grain
            grainIntensity={0.05}
            mouseInteraction
            mouseRadius={0.3}
            mouseStrength={0.4}
          />
        )}
      </div>

      <div
        className={cn(
          'pointer-events-none fixed inset-0 z-[1]',
          showPrism ? 'bg-black/10' : 'bg-gradient-to-b from-background/5 via-background/10 to-background/45'
        )}
      />

      <div className="fixed right-4 top-4 z-50 flex items-center gap-3 rounded-full border border-white/30 bg-background/60 px-3 py-2 text-sm shadow-lg ring-1 ring-black/5 backdrop-blur-2xl sm:right-6 sm:top-6 sm:px-4">
        <span className={cn('hidden sm:inline', showPrism ? 'text-muted-foreground' : 'font-medium')}>
          <FormattedMessage defaultMessage="Topography" id="Auth / Background topography" />
        </span>
        <Switch
          checked={showPrism}
          onCheckedChange={setShowPrism}
          aria-label={intl.formatMessage({
            defaultMessage: 'Switch authentication background',
            id: 'Auth / Background switch aria label',
          })}
        />
        <span className={cn('hidden sm:inline', showPrism ? 'font-medium' : 'text-muted-foreground')}>
          <FormattedMessage defaultMessage="Prism" id="Auth / Background prism" />
        </span>
      </div>

      <FloatingThemeToggle />
      <main className="container relative z-10 flex min-h-screen items-center justify-center px-4 py-20">
        {children}
      </main>
    </div>
  );
};
