import { apiURL } from './helpers';

export const CSRF_HEADER_NAME = 'X-CSRFToken';

let cachedToken: Promise<string | null> | null = null;

const fetchCsrfToken = async (): Promise<string | null> => {
  const response = await fetch(apiURL('/auth/csrf/'), { credentials: 'include' });
  if (!response.ok) {
    return null;
  }
  const body = (await response.json()) as { csrfToken?: string };
  return body.csrfToken ?? null;
};

/**
 * The token for X-CSRFToken. Requests that carry the auth cookie must send it, or the backend refuses them
 * (apps/users/authentication.py). The token is kept in memory and not read from a cookie: when the web app and the
 * API are on different sites (Render), the app cannot read the API's cookies.
 */
export const ensureCsrfToken = (): Promise<string | null> => {
  if (!cachedToken) {
    cachedToken = fetchCsrfToken()
      .then((token) => {
        if (!token) {
          cachedToken = null;
        }
        return token;
      })
      .catch(() => {
        cachedToken = null;
        return null;
      });
  }
  return cachedToken;
};

/** Forget the cached token. Call after login or logout, so the next request fetches a token for the current cookie. */
export const resetCsrfToken = () => {
  cachedToken = null;
};
