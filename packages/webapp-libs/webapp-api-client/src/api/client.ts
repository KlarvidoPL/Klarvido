import axios from 'axios';
import applyCaseMiddleware from 'axios-case-converter';

import { Emitter } from '../utils/eventEmitter';
import { clearLegacyAuthTokens } from './auth/auth.utils';
import { getCsrfToken, resetCsrfToken } from './csrf';
import { validateStatus } from './helpers';
import { createRefreshTokenInterceptor } from './interceptors';

clearLegacyAuthTokens();

export const emitter = new Emitter();

export const client = applyCaseMiddleware(
  axios.create({
    withCredentials: true,
    validateStatus,
  }),
  { preservedKeys: ['X-CSRFToken'] }
);

client.interceptors.request.use(
  async (config) => {
    config.headers = config.headers || {};
    if (!['get', 'head', 'options'].includes((config.method || 'get').toLowerCase())) {
      config.headers['X-CSRFToken'] = await getCsrfToken();
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export const setupStoreInterceptors = () => {
  const refreshTokenInterceptor = createRefreshTokenInterceptor({ emitter });
  client.interceptors.response.use(refreshTokenInterceptor.onFulfilled, refreshTokenInterceptor.onRejected);
};

// A stale CSRF cookie must not poison subsequent REST requests.
client.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 403 && error.response?.data?.code === 'csrf_failed') resetCsrfToken();
  return Promise.reject(error);
});
