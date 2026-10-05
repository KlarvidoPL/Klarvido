import { cn } from '@sb/webapp-core/lib/utils';
import type { ReactNode } from 'react';

import type { Option } from './onboardingOptions.hook';

// Below the sm breakpoint tiles stack in one column and span the full width, like the Back/Next buttons.
// From sm up they share one width per row: the grid stretches to the widest label, capped so long labels wrap instead.
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
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
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
              'flex min-h-10 flex-col items-center justify-center rounded-lg border bg-card px-3 py-2 text-center text-sm font-normal transition-colors hover:border-primary disabled:cursor-not-allowed disabled:opacity-50',
              active && 'border-primary bg-primary/5 ring-1 ring-primary'
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
};

// A question heading with an optional hint, followed by its answer tiles. Returns siblings so the parent's
// spacing (space-y-6 on the form) keeps applying between the heading and the tiles.
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
  <>
    <div>
      <h2 className="text-base font-semibold">{title}</h2>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
    <ChoiceGroup {...groupProps} />
  </>
);
