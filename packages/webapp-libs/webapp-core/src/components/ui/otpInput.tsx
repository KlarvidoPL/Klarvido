import { useId, useRef, useState } from 'react';

import { cn } from '../../lib/utils';
import { Label } from './label';

type OtpInputProps = {
  value: string;
  onValueChange: (value: string) => void;
  label: string;
  disabled?: boolean;
};

export function OtpInput({ value, onValueChange, label, disabled }: OtpInputProps) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);
  const [position, setPosition] = useState(0);

  return (
    <div className="space-y-3">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        {/* One real input preserves autofill, paste, keyboard editing and leading zeros. */}
        <input
          ref={input}
          id={id}
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          spellCheck={false}
          disabled={disabled}
          value={value}
          className="absolute inset-0 h-full w-full opacity-0"
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onSelect={(event) => setPosition(Math.min(event.currentTarget.selectionStart ?? 0, 5))}
          onChange={(event) => {
            const digits = event.target.value.replace(/[^0-9]/g, '').slice(0, 6);
            const cursor = event.target.value
              .slice(0, event.target.selectionStart ?? event.target.value.length)
              .replace(/[^0-9]/g, '').length;
            setPosition(Math.min(cursor, 5));
            onValueChange(digits);
          }}
        />
        <div aria-hidden="true" className="grid grid-cols-6 gap-2">
          {Array.from({ length: 6 }, (_, index) => (
            <button
              key={index}
              type="button"
              tabIndex={-1}
              disabled={disabled}
              onClick={() => {
                const cursor = Math.min(index, value.length);
                input.current?.focus();
                input.current?.setSelectionRange(cursor, Math.min(cursor + 1, value.length));
                setPosition(Math.min(cursor, 5));
              }}
              className={cn(
                'border-input bg-background relative flex h-12 min-w-0 items-center justify-center rounded-md border font-mono text-xl disabled:opacity-50',
                focused && position === index && 'ring-ring ring-offset-background ring-2 ring-offset-2'
              )}
            >
              {value[index] || <span className="bg-muted-foreground/40 h-1 w-1 rounded-full" />}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
