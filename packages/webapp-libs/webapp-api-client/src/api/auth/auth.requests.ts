import { client } from '../client';
import { apiURLs } from '../helpers';
import { LogoutApiResponseData } from './auth.types';
import { storeAuthTokens } from './auth.utils';

export const AUTH_URL = apiURLs('/auth/', {
  REFRESH_TOKEN: '/token-refresh/',
  LOGOUT: '/logout/',
  ME: '/me/',
  UPDATE_PROFILE: '/me/',
  UPDATE_AVATAR: '/me/',
});

export interface RefreshTokenResponse {
  access?: string;
  refresh?: string;
}

export const refreshToken = async () => {
  // For Safari/mobile: pass refresh token from localStorage in request body
  // because Safari blocks third-party cookies (ITP)
  // Backend accepts refresh token from either cookie or request body
  let refreshTokenValue: string | null = null;
  try {
    refreshTokenValue = localStorage.getItem('refresh_token');
  } catch {
    // Ignore storage errors
  }

  const res = await client.post<RefreshTokenResponse>(
    AUTH_URL.REFRESH_TOKEN,
    refreshTokenValue ? { refresh: refreshTokenValue } : undefined
  );

  if (res.data?.access) {
    storeAuthTokens(res.data.access, res.data.refresh);
  }

  return res.data;
};

// Refresh tokens rotate on every use (backend blacklists the old refresh
// token immediately - see CookieTokenRefreshSerializer), so two concurrent
// refresh calls sharing the same pre-rotation token can't both succeed: the
// second is rejected and forces a logout. The GraphQL link and the axios
// interceptor each 401 independently on their own in-flight requests, so a
// per-module "already refreshing" flag isn't enough - both call this shared
// coordinator instead, which also dedupes across browser tabs (they share
// the same cookies/localStorage refresh token and would otherwise race it
// the same way).
const CROSS_TAB_LOCK_KEY = 'auth_refresh_lock';
const CROSS_TAB_LOCK_TTL_MS = 15000;

let inFlightRefresh: Promise<RefreshTokenResponse | undefined> | null = null;

const acquireCrossTabLock = (): boolean => {
  try {
    const existing = localStorage.getItem(CROSS_TAB_LOCK_KEY);
    if (existing && Date.now() - Number(existing) < CROSS_TAB_LOCK_TTL_MS) {
      return false;
    }
    localStorage.setItem(CROSS_TAB_LOCK_KEY, String(Date.now()));
    return true;
  } catch {
    // No localStorage access (e.g. private browsing) - can't coordinate
    // across tabs, but this tab's own in-flight dedup above still applies.
    return true;
  }
};

const releaseCrossTabLock = () => {
  try {
    localStorage.removeItem(CROSS_TAB_LOCK_KEY);
  } catch {
    // Ignore storage errors
  }
};

// Waits until another tab's refresh finishes (lock cleared) or its TTL
// expires, so this tab can safely retry the original request with the
// tokens that tab already stored.
const waitForOtherTabRefresh = (): Promise<void> =>
  new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      window.removeEventListener('storage', onStorage);
      clearInterval(pollId);
      clearTimeout(cap);
      resolve();
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === CROSS_TAB_LOCK_KEY && !event.newValue) {
        finish();
      }
    };
    window.addEventListener('storage', onStorage);
    const pollId = setInterval(() => {
      try {
        const existing = localStorage.getItem(CROSS_TAB_LOCK_KEY);
        if (!existing || Date.now() - Number(existing) >= CROSS_TAB_LOCK_TTL_MS) {
          finish();
        }
      } catch {
        finish();
      }
    }, 250);
    const cap = setTimeout(finish, CROSS_TAB_LOCK_TTL_MS);
  });

export const coordinatedRefreshToken = async (): Promise<RefreshTokenResponse | undefined> => {
  if (inFlightRefresh) {
    return inFlightRefresh;
  }

  inFlightRefresh = (async () => {
    if (!acquireCrossTabLock()) {
      await waitForOtherTabRefresh();
      // Another tab already refreshed - tokens are already updated in the
      // shared cookies/localStorage, nothing more to do here.
      return undefined;
    }

    try {
      return await refreshToken();
    } finally {
      releaseCrossTabLock();
    }
  })();

  try {
    return await inFlightRefresh;
  } finally {
    inFlightRefresh = null;
  }
};

export const logout = async () => {
  // For Safari/mobile: pass refresh token from localStorage in request body
  // because Safari blocks third-party cookies (ITP)
  // Backend accepts refresh token from either cookie or request body
  let refreshTokenValue: string | null = null;
  try {
    refreshTokenValue = localStorage.getItem('refresh_token');
  } catch {
    // Ignore storage errors
  }
  
  const res = await client.post<LogoutApiResponseData>(
    AUTH_URL.LOGOUT,
    refreshTokenValue ? { refresh: refreshTokenValue } : undefined
  );
  return res.data;
};
