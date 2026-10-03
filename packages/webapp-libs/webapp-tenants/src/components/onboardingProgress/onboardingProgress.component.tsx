import { cn } from '@sb/webapp-core/lib/utils';
import { useIntl } from 'react-intl';

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
    intl.formatMessage({ defaultMessage: 'Summary', id: 'Onboarding / Step summary' }),
  ];

  return (
    // Always a single row: connectors shrink to fill whatever width is left, the dots never shrink.
    // Labels appear from 2xl up, where the full row fits; below that they stay screen-reader only.
    <ol
      className="flex items-center pt-4 text-sm"
      aria-label={intl.formatMessage({ defaultMessage: 'Onboarding steps', id: 'Onboarding / Steps label' })}
    >
      {steps.map((label, index) => {
        const number = index + 1;
        const isCurrent = number === step;
        const isDone = number < step;
        return (
          <li
            key={number}
            aria-current={isCurrent ? 'step' : undefined}
            className={cn('flex items-center', index < steps.length - 1 && 'flex-1')}
          >
            <button
              type="button"
              title={label}
              disabled={!onStepChange || number > maxStep || isCurrent}
              onClick={() => onStepChange?.(number)}
              className={cn(
                'flex shrink-0 items-center gap-2 whitespace-nowrap disabled:cursor-default',
                isCurrent || isDone ? 'text-foreground' : 'text-muted-foreground'
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-full border text-xs font-medium',
                  isCurrent
                    ? 'border-primary bg-primary text-primary-foreground'
                    : isDone
                      ? 'border-primary/40'
                      : 'border-border'
                )}
              >
                {number}
              </span>
              <span className="sr-only 2xl:not-sr-only">{label}</span>
            </button>
            {index < steps.length - 1 && <div aria-hidden="true" className="mx-1.5 h-px min-w-2 flex-1 bg-border sm:mx-2" />}
          </li>
        );
      })}
    </ol>
  );
};
