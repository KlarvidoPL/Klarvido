/** Remove tokens left by older application versions; browser sessions use HttpOnly cookies. */
export const clearLegacyAuthTokens = () => {
  try {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
  } catch {
    // Cookies remain available when browser storage is disabled.
  }
};
