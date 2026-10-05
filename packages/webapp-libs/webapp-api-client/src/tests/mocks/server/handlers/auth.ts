import { DefaultBodyType, PathParams, rest } from 'msw';

import { AUTH_URL } from '../../../../api/auth';
import { apiURL } from '../../../../api/helpers';

export const mockRefreshToken = (status = 200) =>
  rest.post<DefaultBodyType, PathParams, DefaultBodyType>(AUTH_URL.REFRESH_TOKEN, (req, res, ctx) => {
    return res(ctx.status(status));
  });

export const mockLogout = (status = 200) =>
  rest.post<never, PathParams, any>(AUTH_URL.LOGOUT, (req, res, ctx) => {
    return res(ctx.status(status));
  });

export const mockCsrfToken = (token = 'test-csrf-token') =>
  rest.get(apiURL('/auth/csrf/'), (req, res, ctx) => res(ctx.json({ csrfToken: token })));
