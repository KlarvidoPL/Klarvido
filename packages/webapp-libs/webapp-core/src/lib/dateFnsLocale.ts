import { useIntl } from 'react-intl';
import { ar, de, enUS, es, fr, hi, pl, zhCN, type Locale as DateFnsLocale } from 'date-fns/locale';

// Maps the app's UI locales to date-fns locales, so calendars and formatted dates follow the selected language.
const DATE_FNS_LOCALES: Record<string, DateFnsLocale> = {
  ar,
  de,
  en: enUS,
  es,
  fr,
  hi,
  pl,
  zh: zhCN,
};

export const getDateFnsLocale = (locale: string): DateFnsLocale => {
  const language = locale.split('-')[0];
  return DATE_FNS_LOCALES[language] ?? enUS;
};

export const useDateFnsLocale = (): DateFnsLocale => {
  const { locale } = useIntl();
  return getDateFnsLocale(locale);
};
