import axios from 'axios';
import applyCaseMiddleware from 'axios-case-converter';

import { Emitter } from '../utils/eventEmitter';
import { getCsrfToken, resetCsrfToken } from './csrf';
import { validateStatus } from './helpers';
import { createRefreshTokenInterceptor } from './interceptors';

export const emitter = new Emitter();

export const client = applyCaseMiddleware(
  axios.create({
    withCredentials: true,
    validateStatus,
  }),
  { preservedKeys: ['X-CSRFToken'] }
);

/**
 * Request interceptor that adds Authorization header from localStorage.
 *
 * This is essential for Safari and mobile browsers that block third-party cookies
 * due to Intelligent Tracking Prevention (ITP). When cookies are blocked,
 * we fall back to sending the access token via Authorization header.
 */
client.interceptors.request.use(
  async (config) => {
    config.headers = config.headers || {};
    const token = localStorage.getItem('token');
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
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
