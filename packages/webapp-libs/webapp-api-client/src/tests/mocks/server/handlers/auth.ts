import { DefaultBodyType, PathParams, rest } from 'msw';

import { AUTH_URL } from '../../../../api/auth';

export const mockRefreshToken = (status = 401) =>
  rest.post<DefaultBodyType, PathParams, DefaultBodyType>(AUTH_URL.REFRESH_TOKEN, (req, res, ctx) => {
    return res(ctx.status(status), ctx.json({ success: status === 200 }));
  });

export const mockLogout = (status = 200) =>
  rest.post<never, PathParams, any>(AUTH_URL.LOGOUT, (req, res, ctx) => {
    return res(ctx.status(status));
  });

export const csrfTokenHandler = () =>
  rest.get('/api/auth/csrf/', (req, res, ctx) => res(ctx.json({ csrfToken: 'test-csrf-proof' })));
