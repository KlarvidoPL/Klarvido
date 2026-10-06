import { apiURL } from './helpers';

let tokenPromise: Promise<string> | null = null;

export const resetCsrfToken = () => {
  tokenPromise = null;
};

export const getCsrfToken = (): Promise<string> => {
  if (!tokenPromise) {
    tokenPromise = fetch(apiURL('/auth/csrf/'), { credentials: 'include', cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to initialize request security');
        const data = await response.json();
        if (typeof data.csrfToken !== 'string' || !data.csrfToken) throw new Error('Missing request security token');
        return data.csrfToken as string;
      })
      .catch((error) => {
        resetCsrfToken();
        throw error;
      });
  }
  return tokenPromise;
};

export const csrfFetch: typeof fetch = async (input, init) => {
  const request = typeof Request !== 'undefined' && input instanceof Request ? input : null;
  const method = (init?.method || request?.method || 'GET').toUpperCase();
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return fetch(input, init);
  const send = async () => {
    const headers = new Headers(init?.headers || request?.headers);
    headers.set('X-CSRFToken', await getCsrfToken());
    return fetch(request ? request.clone() : input, { ...init, headers });
  };
  const response = await send();
  if (response.status === 403) {
    const error = await response
      .clone()
      .json()
      .catch(() => null);
    if (error?.code === 'csrf_failed') {
      resetCsrfToken();
      return send(); // The server rejected before execution; retry once with a fresh token.
    }
  }
  return response;
};
