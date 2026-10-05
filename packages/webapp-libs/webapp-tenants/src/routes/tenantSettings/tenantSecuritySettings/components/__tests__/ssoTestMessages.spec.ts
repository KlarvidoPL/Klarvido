import { createIntl } from 'react-intl';

import { translateSsoDetailLabel, translateSsoTestText } from '../ssoTestMessages';

const intlWith = (locale: string, messages: Record<string, string>) => createIntl({ locale, messages });

describe('ssoTestMessages', () => {
  it('translates an exact backend text by its message id', () => {
    const intl = intlWith('pl', { 'SSO Test / Client ID': 'Identyfikator klienta' });

    expect(translateSsoTestText(intl, 'Client ID')).toBe('Identyfikator klienta');
  });

  it('fills placeholders from the backend text', () => {
    const intl = intlWith('pl', { 'SSO Test / Certificate expires in days days': 'Certyfikat wygasa za {days} dni' });

    expect(translateSsoTestText(intl, 'Certificate expires in 5 days')).toBe('Certyfikat wygasa za 5 dni');
  });

  it('keeps unknown text unchanged', () => {
    const intl = intlWith('pl', {});

    expect(translateSsoTestText(intl, 'Some unexpected backend text')).toBe('Some unexpected backend text');
  });

  it('translates detail labels and falls back to the raw key', () => {
    const intl = intlWith('pl', { 'SSO Test / Detail / value': 'Wartość' });

    expect(translateSsoDetailLabel(intl, 'value')).toBe('Wartość');
    expect(translateSsoDetailLabel(intl, 'unknownKey')).toBe('unknownKey');
  });
});
