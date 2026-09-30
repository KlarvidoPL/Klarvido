import { cn } from '@sb/webapp-core/lib/utils';
import { useIntl } from 'react-intl';

export const OnboardingProgress = ({ step }: { step: number }) => {
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
    <ol
      className="grid auto-rows-fr grid-cols-2 gap-2 pt-4 md:grid-cols-4 xl:grid-cols-8"
      aria-label={intl.formatMessage({ defaultMessage: 'Onboarding steps', id: 'Onboarding / Steps label' })}
    >
      {steps.map((label, index) => {
        const number = index + 1;
        return (
          <li
            key={number}
            aria-current={number === step ? 'step' : undefined}
            className={cn(
              'flex h-12 min-w-0 items-center justify-center gap-2 overflow-hidden rounded-lg border px-2 text-center text-sm',
              number === step
                ? 'border-primary bg-primary text-primary-foreground'
                : number < step
                  ? 'border-primary/30 text-foreground'
                  : 'text-muted-foreground'
            )}
          >
            <span className="shrink-0 font-semibold">{number}.</span>
            <span className="whitespace-nowrap">{label}</span>
          </li>
        );
      })}
    </ol>
  );
};
