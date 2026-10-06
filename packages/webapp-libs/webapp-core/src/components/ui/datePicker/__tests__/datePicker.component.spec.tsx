import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { Locale, formatTranslationMessages } from '../../../../config/i18n';
import { render } from '../../../../tests/utils/rendering';
import plMessages from '../../../../translations/pl.json';
import { DatePicker, parseTimeInput } from '../datePicker.component';

it.each(['en', 'pl', 'de', 'fr', 'es', 'zh', 'hi', 'ar'])(
  'accepts localized and 24-hour pasted times in %s',
  (locale) => {
    for (const hours of [0, 9, 12, 17, 23]) {
      const value = new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit' }).format(
        new Date(2026, 0, 1, hours, 37)
      );
      expect(parseTimeInput(value, locale)).toEqual({ hours, minutes: 37 });
    }
    expect(parseTimeInput('17:37', locale)).toEqual({ hours: 17, minutes: 37 });
  }
);

it.each(['24:00', '17:60', '0:30 PM', '13:00 AM', 'invalid'])('rejects invalid pasted time %s', (value) => {
  expect(parseTimeInput(value, 'en')).toBeUndefined();
});

it('shows Polish 24-hour presets and commits a pasted time without rounding minutes', async () => {
  const onChange = jest.fn();
  render(<DatePicker value="2026-10-06T09:00" showTime onChange={onChange} />, {
    intlLocale: Locale.POLISH,
    intlMessages: formatTranslationMessages(Locale.POLISH, plMessages),
  });
  await userEvent.click(screen.getByRole('combobox'));
  expect(screen.getByRole('button', { name: '17:00' })).toBeInTheDocument();
  const input = screen.getByRole('textbox', { name: 'Godzina' });
  await userEvent.click(input);
  await userEvent.clear(input);
  await userEvent.paste('17:37');
  await userEvent.click(screen.getByRole('button', { name: 'Gotowe' }));
  expect(onChange).toHaveBeenCalledWith('2026-10-06T17:37');
});

it('opens the time selector with other hours and preserves exact minutes', async () => {
  const onChange = jest.fn();
  render(<DatePicker value="2026-10-06T09:37" showTime onChange={onChange} />, {
    intlLocale: Locale.POLISH,
    intlMessages: formatTranslationMessages(Locale.POLISH, plMessages),
  });
  await userEvent.click(screen.getByRole('combobox'));
  await userEvent.click(screen.getByRole('combobox', { name: 'Godzina' }));
  await userEvent.click(screen.getByRole('option', { name: '17:37' }));
  expect(onChange).toHaveBeenCalledWith('2026-10-06T17:37');
});
