import { getSafeAuthRedirect } from '../authRedirect';

const fallback = '/en/';

describe('getSafeAuthRedirect', () => {
  it.each([
    null,
    '',
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    'data:text/html,test',
    'https://evil.example/phish',
    '//evil.example/phish',
    '///evil.example',
    String.raw`/\evil.example`,
    String.raw`https:\evil.example`,
    '/%2fevil.example',
    '/%252fevil.example',
    '/%5cevil.example',
    '/%255cevil.example',
    '/%0a/evil.example',
    '/%250d/evil.example',
    '/a/..//evil.example',
    '/a/%2e%2e//evil.example',
    '\n/en/profile',
    '/en/\tprofile',
    '/%ZZ',
    'profile',
  ])('rejects unsafe destination %p', (input) => {
    expect(getSafeAuthRedirect(input, fallback)).toBe(fallback);
  });

  it.each([
    ['/en/profile', '/en/profile'],
    ['/en/../pl/profile?tab=security#passkeys', '/pl/profile?tab=security#passkeys'],
    ['/en/profile?next=https%3A%2F%2Fexample.com&name=A%20B', '/en/profile?next=https%3A%2F%2Fexample.com&name=A%20B'],
    ['/en/%E2%9C%93', '/en/%E2%9C%93'],
  ])('preserves safe destination %s', (input, expected) => {
    expect(getSafeAuthRedirect(input, fallback)).toBe(expected);
  });

  it('normalizes an absolute same-origin URL into an application path', () => {
    expect(getSafeAuthRedirect(`${window.location.origin}/en/profile?tab=security#passkeys`, fallback)).toBe(
      '/en/profile?tab=security#passkeys'
    );
  });

  it('rejects URLs with embedded credentials', () => {
    const url = new URL('/en/profile', window.location.origin);
    url.username = 'attacker';
    expect(getSafeAuthRedirect(url.href, fallback)).toBe(fallback);
  });
});
