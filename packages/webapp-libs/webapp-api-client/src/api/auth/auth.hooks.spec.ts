import { getOauthUrl, startOAuthLogin } from './auth.hooks';
import { OAuthProvider } from './auth.types';

const mockGetCsrfToken = jest.fn();
const mockResetCsrfToken = jest.fn();
jest.mock('../csrf', () => ({
  getCsrfToken: () => mockGetCsrfToken(),
  resetCsrfToken: () => mockResetCsrfToken(),
}));
jest.mock('../helpers', () => ({ apiURL: (path: string) => `https://api.example.com/api${path}` }));

describe('Google sign-in initiation', () => {
  beforeEach(() => jest.clearAllMocks());

  it('submits a top-level POST with CSRF, locale and the current return address', async () => {
    mockGetCsrfToken.mockResolvedValue('masked-csrf-proof');
    let submitted: HTMLFormElement | undefined;
    const submit = jest.spyOn(HTMLFormElement.prototype, 'submit').mockImplementation(function (this: HTMLFormElement) {
      submitted = this;
    });
    await startOAuthLogin(OAuthProvider.Google, 'pl');
    expect(mockResetCsrfToken).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submitted?.method).toBe('post');
    expect(submitted?.action).toBe('https://api.example.com/api/auth/social/login/google-oauth2/');
    const values = new FormData(submitted);
    expect(values.get('csrfmiddlewaretoken')).toBe('masked-csrf-proof');
    expect(values.get('locale')).toBe('pl');
    expect(values.get('next')).toBe(window.location.href);
    expect(document.querySelector('form')).toBeNull();
    submit.mockRestore();
  });

  it('does not start authentication when CSRF initialization fails', async () => {
    mockGetCsrfToken.mockRejectedValue(new Error('network unavailable'));
    const submit = jest.spyOn(HTMLFormElement.prototype, 'submit').mockImplementation(() => undefined);
    await expect(startOAuthLogin(OAuthProvider.Google)).rejects.toThrow('network unavailable');
    expect(submit).not.toHaveBeenCalled();
    submit.mockRestore();
  });

  it('uses the slash-terminated login endpoint and encoded return address', () => {
    const url = new URL(getOauthUrl(OAuthProvider.Google, 'de'));
    expect(url.pathname).toBe('/api/auth/social/login/google-oauth2/');
    expect(url.searchParams.get('next')).toBe(window.location.href);
    expect(url.searchParams.get('locale')).toBe('de');
  });
});
