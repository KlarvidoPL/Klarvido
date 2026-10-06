'use client';

import { format, getHours, getMinutes, isValid, parse, parseISO, setHours, setMinutes, startOfDay } from 'date-fns';
import { CalendarIcon, Clock, X } from 'lucide-react';
import * as React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

import { useDateFnsLocale } from '../../../lib/dateFnsLocale';
import { cn } from '../../../lib/utils';
import { Button } from '../../buttons';
import { Calendar } from '../calendar';
import { Input } from '../input';
import { Popover, PopoverContent, PopoverTrigger } from '../popover';
import { Select, SelectContent, SelectItem, SelectTrigger } from '../select';

export interface DatePickerProps {
  /** The selected date as ISO string (YYYY-MM-DD or YYYY-MM-DDTHH:mm) or Date object */
  value?: string | Date;
  /** Callback when date changes - returns ISO string or undefined if cleared */
  onChange?: (value: string | undefined) => void;
  /** Placeholder text when no date selected */
  placeholder?: string;
  /** Additional class name for the trigger button */
  className?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Align popover */
  align?: 'start' | 'center' | 'end';
  /** Whether to show the clear button */
  clearable?: boolean;
  /** Optional date-fns display format. Defaults to localized date and time formatting. */
  displayFormat?: string;
  /** Minimum selectable date */
  minDate?: Date;
  /** Maximum selectable date */
  maxDate?: Date;
  /** Name attribute for form integration */
  name?: string;
  /** ID attribute */
  id?: string;
  /** Whether to include time picker (default: false) */
  showTime?: boolean;
  /** Spacing between suggested minutes (default: 5). Typed times keep their exact minutes. */
  timeStep?: number;
}

/**
 * Parse a value (string or Date) into a Date object.
 * Uses parseISO for ISO strings to avoid timezone issues.
 */
function parseValue(value: string | Date | undefined): Date | undefined {
  if (!value) return undefined;
  if (value instanceof Date) return isValid(value) ? value : undefined;

  // Use parseISO for ISO format strings (handles YYYY-MM-DD and YYYY-MM-DDTHH:mm correctly)
  // parseISO treats date-only strings as local time, not UTC
  const parsed = parseISO(value);
  if (isValid(parsed)) return parsed;

  // Fallback: try parsing with date-fns parse
  const fallbackParsed = parse(value, 'yyyy-MM-dd', new Date());
  if (isValid(fallbackParsed)) return fallbackParsed;

  return undefined;
}

/**
 * Format a date to the appropriate output string
 */
function formatOutput(date: Date, showTime: boolean): string {
  if (showTime) {
    return format(date, "yyyy-MM-dd'T'HH:mm");
  }
  return format(date, 'yyyy-MM-dd');
}

/** Parse pasted 24-hour times or the locale's 12-hour time, including localized digits. */
export function parseTimeInput(value: string, locale: string): { hours: number; minutes: number } | undefined {
  let text = value.trim().replace(/[\u200e\u200f\u061c]/g, '');
  const numberFormat = new Intl.NumberFormat(locale, { useGrouping: false });
  for (let digit = 0; digit < 10; digit++) {
    text = text.split(numberFormat.format(digit)).join(String(digit));
  }
  text = text.replace(/[٠-٩۰-۹०-९]/g, (digit) => {
    const code = digit.charCodeAt(0);
    return String(code - (code >= 0x0966 ? 0x0966 : code >= 0x06f0 ? 0x06f0 : 0x0660));
  });
  let period: 'am' | 'pm' | undefined;
  for (const [hour, marker] of [
    [9, 'am'],
    [17, 'pm'],
  ] as const) {
    const date = new Date(2026, 0, 1, hour);
    const localized = new Intl.DateTimeFormat(locale, { hour: 'numeric', hour12: true })
      .formatToParts(date)
      .find((part) => part.type === 'dayPeriod')?.value;
    for (const label of [marker, localized].filter((item): item is string => !!item)) {
      if (text.toLowerCase().includes(label.toLowerCase())) {
        if (period) return undefined;
        period = marker;
        text = text.toLowerCase().replace(label.toLowerCase(), '').trim();
        break;
      }
    }
  }
  const match = /^(\d{1,2})[:：.](\d{2})$/.exec(text);
  if (!match) return undefined;
  let hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (minutes > 59 || hours > 23 || (period && (hours < 1 || hours > 12))) return undefined;
  if (period) hours = (hours % 12) + (period === 'pm' ? 12 : 0);
  return { hours, minutes };
}

interface TimePickerProps {
  hours: number;
  minutes: number;
  onTimeChange: (hours: number, minutes: number) => void;
  minuteStep: number;
  disabled?: boolean;
}

function TimePicker({ hours, minutes, onTimeChange, minuteStep, disabled }: TimePickerProps) {
  const intl = useIntl();
  const formatTime = (hour: number, minute: number) =>
    intl.formatTime(new Date(2026, 0, 1, hour, minute), { hour: 'numeric', minute: '2-digit' });
  const formatted = formatTime(hours, minutes);
  const [text, setText] = useState(formatted);
  useEffect(() => setText(formatted), [formatted]);
  const commitTime = () => {
    const parsed = parseTimeInput(text, intl.locale);
    if (parsed) onTimeChange(parsed.hours, parsed.minutes);
    else setText(formatted);
  };
  const step = Number.isFinite(minuteStep) ? Math.max(1, Math.min(60, Math.floor(minuteStep))) : 5;

  return (
    <div className="border-border flex flex-wrap items-center gap-2 border-t px-3 py-2">
      <Clock className="text-muted-foreground h-4 w-4 shrink-0" aria-hidden="true" />
      <Input
        type="text"
        value={text}
        disabled={disabled}
        aria-label={intl.formatMessage({ id: 'Calendar / Time label', defaultMessage: 'Time' })}
        className="h-8 w-32 text-sm"
        onChange={(event) => setText(event.target.value)}
        onBlur={commitTime}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            commitTime();
          }
        }}
      />
      <Select
        value={`${hours}:${minutes}`}
        disabled={disabled}
        onValueChange={(value) => {
          const [hour, minute] = value.split(':').map(Number);
          setText(formatTime(hour, minute));
          onTimeChange(hour, minute);
        }}
      >
        <SelectTrigger
          className="h-8 w-9 justify-center px-2"
          aria-label={intl.formatMessage({ id: 'Calendar / Time label', defaultMessage: 'Time' })}
        />
        <SelectContent>
          {Array.from({ length: 24 }, (_, hour) =>
            Array.from(new Set([minutes, ...Array.from({ length: Math.ceil(60 / step) }, (_, index) => index * step)]))
              .sort((a, b) => a - b)
              .map((minute) => (
                <SelectItem key={`${hour}:${minute}`} value={`${hour}:${minute}`}>
                  {formatTime(hour, minute)}
                </SelectItem>
              ))
          )}
        </SelectContent>
      </Select>
      <div className="ml-auto flex flex-wrap items-center gap-1">
        {[9, 12, 17].map((hour) => (
          <button
            key={hour}
            type="button"
            disabled={disabled}
            onClick={() => onTimeChange(hour, 0)}
            className={cn(
              'rounded px-2 py-1 text-xs transition-colors disabled:opacity-50',
              hours === hour && minutes === 0
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            {formatTime(hour, 0)}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * DatePicker - A single date picker component that wraps Calendar in a Popover.
 * Supports both date-only and datetime modes.
 */
export function DatePicker({
  value,
  onChange,
  placeholder,
  className,
  disabled = false,
  align = 'start',
  clearable = true,
  displayFormat,
  minDate,
  maxDate,
  name,
  id,
  showTime = false,
  timeStep = 5,
}: DatePickerProps) {
  const intl = useIntl();
  const dateLocale = useDateFnsLocale();
  const [open, setOpen] = useState(false);

  // Parse the value into a Date - memoized to prevent infinite loops
  const selectedDate = useMemo(() => parseValue(value), [value]);

  // Track the month shown in the calendar - initialize once, update only when popover opens
  const [month, setMonth] = useState<Date>(() => selectedDate ?? new Date());

  // Track if we need to sync month on open
  const lastSelectedDateRef = useRef<Date | undefined>(selectedDate);

  // Derived default display format

  // Derived placeholder
  const actualPlaceholder =
    placeholder ??
    (showTime
      ? intl.formatMessage({ id: 'Calendar / Select date and time', defaultMessage: 'Select date and time' })
      : intl.formatMessage({ id: 'Calendar / Select date', defaultMessage: 'Select date' }));

  // Sync month when popover opens (not on every selectedDate change)
  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      if (isOpen && selectedDate) {
        // Only update month if the date actually changed
        if (!lastSelectedDateRef.current || lastSelectedDateRef.current.getTime() !== selectedDate.getTime()) {
          setMonth(selectedDate);
          lastSelectedDateRef.current = selectedDate;
        }
      }
      setOpen(isOpen);
    },
    [selectedDate]
  );

  const handleSelect = useCallback(
    (date: Date | undefined) => {
      if (date) {
        // Preserve time if in showTime mode and we have an existing selection
        let finalDate = date;
        if (showTime && selectedDate) {
          finalDate = setHours(setMinutes(date, getMinutes(selectedDate)), getHours(selectedDate));
        } else if (showTime) {
          // Default to 9:00 AM for new selections in datetime mode
          finalDate = setHours(setMinutes(date, 0), 9);
        }

        const outputValue = formatOutput(finalDate, showTime);
        onChange?.(outputValue);

        // Only close if not showing time (user might want to adjust time)
        if (!showTime) {
          setOpen(false);
        }
      }
    },
    [onChange, showTime, selectedDate]
  );

  const handleTimeChange = useCallback(
    (hours: number, minutes: number) => {
      // Use selectedDate if exists, otherwise use today
      const baseDate = selectedDate ?? new Date();
      const newDate = setHours(setMinutes(baseDate, minutes), hours);
      const outputValue = formatOutput(newDate, true);
      onChange?.(outputValue);
    },
    [onChange, selectedDate]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange?.(undefined);
    },
    [onChange]
  );

  const handleTodayClick = useCallback(() => {
    const today = new Date();
    handleSelect(today);
  }, [handleSelect]);

  const handleNowClick = useCallback(() => {
    const now = new Date();
    const outputValue = formatOutput(now, showTime);
    onChange?.(outputValue);
  }, [onChange, showTime]);

  const displayText = selectedDate
    ? displayFormat
      ? format(selectedDate, displayFormat, { locale: dateLocale })
      : intl.formatDate(selectedDate, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          ...(showTime ? ({ hour: 'numeric', minute: '2-digit' } as const) : {}),
        })
    : actualPlaceholder;

  const currentHours = selectedDate ? getHours(selectedDate) : 9;
  const currentMinutes = selectedDate ? getMinutes(selectedDate) : 0;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          role="combobox"
          aria-expanded={open}
          aria-haspopup="dialog"
          className={cn(
            'group w-full justify-between gap-2 text-left font-normal transition-colors duration-150',
            'hover:bg-neutral-100 dark:hover:bg-neutral-800',
            'focus-visible:ring-offset-0',
            !selectedDate && 'text-muted-foreground',
            className
          )}
        >
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <CalendarIcon className="text-muted-foreground h-4 w-4 shrink-0" />
            <span className="truncate">{displayText}</span>
          </div>
          {clearable && selectedDate && !disabled && (
            <span
              role="button"
              tabIndex={0}
              onClick={handleClear}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleClear(e as unknown as React.MouseEvent);
                }
              }}
              className="hover:bg-muted cursor-pointer rounded-sm p-0.5 opacity-0 transition-opacity group-hover:opacity-100"
              aria-label={intl.formatMessage({ id: 'Calendar / Clear date', defaultMessage: 'Clear date' })}
            >
              <X className="text-muted-foreground hover:text-foreground h-3.5 w-3.5" />
            </span>
          )}
          {/* Hidden input for form submission */}
          <input type="hidden" name={name} value={selectedDate ? formatOutput(selectedDate, showTime) : ''} />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="border-border/80 w-auto p-0 shadow-lg" align={align} sideOffset={4}>
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={handleSelect}
          month={month}
          onMonthChange={setMonth}
          disabled={(date) => {
            // Use startOfDay for date-only comparisons to avoid timezone issues
            const dateOnly = startOfDay(date);
            if (minDate && dateOnly < startOfDay(minDate)) return true;
            if (maxDate && dateOnly > startOfDay(maxDate)) return true;
            return false;
          }}
          showYearNavigation
        />

        {/* Compact Time Picker */}
        {showTime && (
          <TimePicker
            hours={currentHours}
            minutes={currentMinutes}
            onTimeChange={handleTimeChange}
            minuteStep={timeStep}
            disabled={!selectedDate}
          />
        )}

        {/* Footer with Today/Now button */}
        <div className="border-border flex items-center justify-between gap-2 border-t bg-neutral-50 px-3 py-2 dark:bg-neutral-900">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={showTime ? handleNowClick : handleTodayClick}
            className="h-7 text-xs"
          >
            {showTime
              ? intl.formatMessage({ id: 'Calendar / Now button', defaultMessage: 'Now' })
              : intl.formatMessage({ id: 'Calendar / Today button', defaultMessage: 'Today' })}
          </Button>
          <div className="flex items-center gap-2">
            {clearable && selectedDate && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  onChange?.(undefined);
                  setOpen(false);
                }}
                className="text-muted-foreground h-7 text-xs"
              >
                {intl.formatMessage({ id: 'Calendar / Clear button', defaultMessage: 'Clear' })}
              </Button>
            )}
            {showTime && (
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={() => setOpen(false)}
                className="h-7 text-xs"
                disabled={!selectedDate}
              >
                {intl.formatMessage({ id: 'Calendar / Done button', defaultMessage: 'Done' })}
              </Button>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

DatePicker.displayName = 'DatePicker';
