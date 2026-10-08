import { clearLegacyAuthTokens } from './auth.utils';

it('removes legacy credentials without removing user preferences', () => {
  localStorage.setItem('token', 'legacy-access');
  localStorage.setItem('refresh_token', 'legacy-refresh');
  localStorage.setItem('theme', 'dark');
  clearLegacyAuthTokens();
  expect(localStorage.getItem('token')).toBeNull();
  expect(localStorage.getItem('refresh_token')).toBeNull();
  expect(localStorage.getItem('theme')).toBe('dark');
  localStorage.removeItem('theme');
});
