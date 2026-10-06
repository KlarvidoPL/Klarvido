import { cn } from '@sb/webapp-core/lib/utils';
import { Check } from 'lucide-react';
import type { ReactNode } from 'react';

import type { Option } from './onboardingOptions.hook';

// Below the sm breakpoint tiles stack in one column and span the full width, like the Back/Next buttons.
// Wider screens use at most three columns so longer answers stay readable.
export const ChoiceGroup = ({
  options,
  selected,
  onChange,
  max = 1,
}: {
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
  max?: number;
}) => {
  const nextSelection = (value: string) => {
    if (max === 1) return [value];
    if (selected.includes(value)) return selected.filter((current) => current !== value);
    return selected.length < max ? [...selected, value] : selected;
  };

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {options.map((option) => {
        const active = selected.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            disabled={max > 1 && !active && selected.length >= max}
            onClick={() => onChange(nextSelection(option.value))}
            className={cn(
              'group relative flex min-h-16 flex-col items-center justify-center overflow-hidden rounded-lg border bg-card px-8 py-4 text-center text-sm font-normal transition-colors hover:border-primary disabled:cursor-not-allowed disabled:opacity-50',
              active && 'border-primary bg-primary/5 ring-1 ring-primary'
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                'pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-[#42F272] blur-2xl transition-opacity',
                active ? 'opacity-[0.08]' : 'opacity-0 group-hover:opacity-[0.04] group-disabled:opacity-0'
              )}
            />
            <span className="relative">{option.label}</span>
            {active && <Check className="absolute right-2 top-2 h-3.5 w-3.5 text-primary" aria-hidden="true" />}
          </button>
        );
      })}
    </div>
  );
};

// Keep the heading close to its answers and let the form separate question groups.
export const ChoiceQuestion = ({
  title,
  hint,
  ...groupProps
}: {
  title: ReactNode;
  hint?: ReactNode;
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
  max?: number;
}) => (
  <section className="space-y-3">
    <div>
      <h2 className="text-base font-semibold">{title}</h2>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
    <ChoiceGroup {...groupProps} />
  </section>
);
