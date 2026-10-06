import { client } from '../client';
import { csrfFetch, getCsrfToken, resetCsrfToken } from '../csrf';

const jsonResponse = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('CSRF request protection', () => {
  let fetchMock: jest.SpyInstance;
  beforeEach(() => {
    resetCsrfToken();
    fetchMock = jest.spyOn(global, 'fetch');
  });
  afterEach(() => fetchMock.mockRestore());

  it('shares concurrent bootstraps and includes API cookies', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ csrfToken: 'token-one' }));
    expect(await Promise.all([getCsrfToken(), getCsrfToken()])).toEqual(['token-one', 'token-one']);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/auth/csrf/'), {
      credentials: 'include',
      cache: 'no-store',
    });
  });

  it('adds CSRF proof without removing bearer auth or multipart bodies', async () => {
    const body = new FormData();
    body.append('operations', '{}');
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'proof' }))
      .mockResolvedValueOnce(jsonResponse({ data: {} }));
    await csrfFetch('/api/graphql/', {
      method: 'POST',
      headers: { Authorization: 'Bearer access' },
      body,
      credentials: 'include',
    });
    const options = fetchMock.mock.calls[1][1];
    expect(options.headers.get('X-CSRFToken')).toBe('proof');
    expect(options.headers.get('Authorization')).toBe('Bearer access');
    expect(options.body).toBe(body);
    expect(options.credentials).toBe('include');
  });

  it('adds CSRF and bearer headers to REST refresh/logout requests', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ csrfToken: 'rest-proof' }));
    localStorage.setItem('token', 'explicit-access');
    const adapter = jest.fn(async (config) => ({ data: {}, status: 200, statusText: 'OK', headers: {}, config }));
    try {
      await client.post('/api/auth/logout/', {}, { adapter });
      const headers = adapter.mock.calls[0][0].headers;
      const findHeader = (name: string) => Object.entries(headers).find(([key]) => key.toLowerCase() === name)?.[1];
      expect(findHeader('x-csrftoken')).toBe('rest-proof');
      expect(findHeader('authorization')).toBe('Bearer explicit-access');
    } finally {
      localStorage.removeItem('token');
    }
  });

  it('does not bootstrap safe requests', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await csrfFetch('/api/translations/', { method: 'GET' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('recovers from rejected bootstrap requests', async () => {
    fetchMock
      .mockRejectedValueOnce(new Error('Network unavailable'))
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'fresh' }));
    await expect(getCsrfToken()).rejects.toThrow('Network unavailable');
    expect(await getCsrfToken()).toBe('fresh');
  });

  it('retries a CSRF rejection once after refreshing proof', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'old' }))
      .mockResolvedValueOnce(jsonResponse({ code: 'csrf_failed' }, 403))
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'new' }))
      .mockResolvedValueOnce(jsonResponse({ code: 'csrf_failed' }, 403));
    expect((await csrfFetch('/api/graphql/', { method: 'POST', body: '{}' })).status).toBe(403);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[3][1].headers.get('X-CSRFToken')).toBe('new');
  });

  it('never retries a permission denial', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'proof' }))
      .mockResolvedValueOnce(jsonResponse({ code: 'permission_denied' }, 403));
    expect((await csrfFetch('/api/graphql/', { method: 'POST' })).status).toBe(403);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
