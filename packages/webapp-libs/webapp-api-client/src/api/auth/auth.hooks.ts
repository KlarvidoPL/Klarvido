import { useLocales } from '@sb/webapp-core/hooks';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useCallback } from 'react';

import { getCsrfToken, resetCsrfToken } from '../csrf';
import { apiURL } from '../helpers';
import { OAuthProvider } from './auth.types';

export const getOauthUrl = (provider: OAuthProvider, locale = 'en') =>
  apiURL(`/auth/social/login/${provider}/?next=${encodeURIComponent(window.location.href)}&locale=${locale}`);

export const startOAuthLogin = async (provider: OAuthProvider, locale = 'en') => {
  resetCsrfToken();
  const token = await getCsrfToken();
  // A top-level POST lets the browser follow the provider redirect without CORS.
  const url = new URL(getOauthUrl(provider, locale), window.location.origin);
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = url.origin + url.pathname;
  for (const [name, value] of [...url.searchParams.entries(), ['csrfmiddlewaretoken', token]]) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
  form.remove();
};

export const useOAuthLogin = () => {
  const {
    locales: { language },
  } = useLocales();

  return useCallback(
    async (provider: OAuthProvider) => {
      trackEvent('auth', 'log-in-oauth', provider);
      await startOAuthLogin(provider, language ?? undefined);
    },
    [language]
  );
};
