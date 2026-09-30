import { InputHTMLAttributes, ReactNode, forwardRef } from 'react';

import { cn } from '../../../lib/utils';

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: string;
  label?: ReactNode;
  /** Non-editable content shown inside the input before the value, e.g. a country prefix like "PL" */
  startAdornment?: ReactNode;
};

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, required, type, startAdornment, ...props }: InputProps, ref) => {
    const input = (
      <input
        type={type}
        className={cn(
          `border-input text-primary ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring h-10 w-full rounded-md border
          bg-transparent px-3 py-2 text-sm transition-all duration-200 ease-in file:border-0
          file:bg-transparent file:text-sm file:font-medium focus-visible:outline-none
          focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50`,
          { 'pl-12': !!startAdornment }
        )}
        ref={ref}
        {...props}
      />
    );

    return (
      <div className={cn(`w-full`, className)}>
        <label className="flex flex-col items-start">
          {label && (
            <p
              className={cn(`order-first mb-1.5 text-sm font-medium`, {
                'text-destructive dark:text-red-400': !!error,
                'text-foreground': !error,
              })}
            >
              {label}
            </p>
          )}
          {startAdornment ? (
            <div className="relative w-full">
              <span
                className="border-input text-muted-foreground pointer-events-none absolute inset-y-0 left-0 flex w-10 items-center justify-center border-r text-sm font-medium"
                aria-hidden="true"
              >
                {startAdornment}
              </span>
              {input}
            </div>
          ) : (
            input
          )}
        </label>
        {error && <p className="text-destructive mt-1.5 text-sm leading-tight dark:text-red-400">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';

export { Input };
