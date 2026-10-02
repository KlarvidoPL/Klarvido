import { cn } from '@sb/webapp-core/lib/utils';
import { useIntl } from 'react-intl';

import './onboardingProgress.css';

export const OnboardingProgress = ({
  step,
  maxStep = step,
  onStepChange,
}: {
  step: number;
  maxStep?: number;
  onStepChange?: (step: number) => void;
}) => {
  const intl = useIntl();
  const steps = [
    intl.formatMessage({ defaultMessage: 'Organization', id: 'Tenant form / AddTenant / Step basics' }),
    intl.formatMessage({ defaultMessage: 'Company details', id: 'Tenant form / AddTenant / Step company details' }),
    intl.formatMessage({ defaultMessage: 'Customers', id: 'Onboarding / Step customers' }),
    intl.formatMessage({ defaultMessage: 'Revenue', id: 'Onboarding / Step revenue' }),
    intl.formatMessage({ defaultMessage: 'Costs', id: 'Onboarding / Step costs' }),
    intl.formatMessage({ defaultMessage: 'Pricing & goal', id: 'Onboarding / Step pricing goal' }),
    intl.formatMessage({ defaultMessage: 'KSeF', id: 'Onboarding / KSeF title' }),
    intl.formatMessage({ defaultMessage: 'Summary', id: 'Onboarding / Step summary' }),
  ];

  return (
    <div className="onboarding-progress">
      <ol
        className="onboarding-progress__grid grid auto-rows-fr gap-2 pt-4"
        aria-label={intl.formatMessage({ defaultMessage: 'Onboarding steps', id: 'Onboarding / Steps label' })}
      >
        {steps.map((label, index) => {
          const number = index + 1;
          return (
            <li
              key={number}
              aria-current={number === step ? 'step' : undefined}
              className={cn(
                'h-12 min-w-0 rounded-lg border text-center text-sm',
                number === step
                  ? 'border-primary bg-primary text-primary-foreground'
                  : number < step
                    ? 'border-primary/30 text-foreground'
                    : 'text-muted-foreground'
              )}
            >
              <button
                type="button"
                disabled={!onStepChange || number > maxStep || number === step}
                onClick={() => onStepChange?.(number)}
                className="flex h-full w-full items-center justify-center gap-2 whitespace-nowrap px-2 disabled:cursor-default"
              >
                <span className="shrink-0 font-semibold">{number}.</span>
                <span className="whitespace-nowrap [hyphens:none]">{label}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
};
