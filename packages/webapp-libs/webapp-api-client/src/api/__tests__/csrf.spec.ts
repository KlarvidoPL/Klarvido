import { CSRF_HEADER_NAME, ensureCsrfToken, resetCsrfToken } from '../csrf';

describe('csrf token', () => {
  const fetchMock = jest.fn();
  const originalFetch = global.fetch;

  const respondWith = (body: unknown, ok = true) => {
    fetchMock.mockResolvedValueOnce({ ok, json: async () => body });
  };

  beforeEach(() => {
    fetchMock.mockReset();
    global.fetch = fetchMock as unknown as typeof fetch;
    resetCsrfToken();
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it('uses the X-CSRFToken header', () => {
    expect(CSRF_HEADER_NAME).toBe('X-CSRFToken');
  });

  it('fetches the token from the bootstrap endpoint with the cookie included', async () => {
    respondWith({ csrfToken: 'token-1' });

    await expect(ensureCsrfToken()).resolves.toBe('token-1');
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/auth/csrf/'), { credentials: 'include' });
  });

  it('reuses the cached token', async () => {
    respondWith({ csrfToken: 'token-1' });

    await ensureCsrfToken();
    await expect(ensureCsrfToken()).resolves.toBe('token-1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('fetches a new token after a reset', async () => {
    respondWith({ csrfToken: 'token-1' });
    respondWith({ csrfToken: 'token-2' });

    await ensureCsrfToken();
    resetCsrfToken();

    await expect(ensureCsrfToken()).resolves.toBe('token-2');
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not cache a failed bootstrap, so the next call tries again', async () => {
    respondWith({}, false);
    respondWith({ csrfToken: 'token-3' });

    await expect(ensureCsrfToken()).resolves.toBeNull();
    await expect(ensureCsrfToken()).resolves.toBe('token-3');
  });

  it('returns null when the request itself fails', async () => {
    fetchMock.mockRejectedValueOnce(new Error('offline'));

    await expect(ensureCsrfToken()).resolves.toBeNull();
  });
});
