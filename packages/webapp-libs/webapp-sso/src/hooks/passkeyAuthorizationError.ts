export const getPasskeyAuthorizationErrorMessage = (error: unknown) => {
  const code =
    error && typeof error === 'object' && 'code' in error
      ? error.code
      : undefined;
  switch (code) {
    case 'incorrect_password':
      return {
        id: 'Passkeys / Incorrect password',
        defaultMessage: 'The account password is incorrect.',
      };
    case 'incorrect_otp':
      return {
        id: 'Auth / OTP / Invalid code',
        defaultMessage: 'The verification code is invalid.',
      };
    case 'otp_locked':
      return {
        id: 'Auth / OTP / Attempt limit',
        defaultMessage: 'Too many incorrect codes. Try again in 15 minutes.',
      };
    case 'password_locked':
      // Reuses the id already extracted/translated from changePasswordForm's identical
      // "too many attempts" copy, rather than introducing a new id that nothing else statically
      // references (this helper returns a plain object, which the FormatJS extractor cannot
      // see through to find a `formatMessage` call site for).
      return {
        id: 'Auth / Change password / Too many attempts',
        defaultMessage: 'Too many attempts. Try again later.',
      };
    case 'rate_limited':
      return {
        id: 'Passkeys / Verification rate limit',
        defaultMessage:
          'Too many verification attempts. Please wait a moment and try again.',
      };
    default:
      return {
        id: 'Passkeys / Reauthentication failed',
        defaultMessage:
          'Verification failed. Check your password and two-factor code, or try your existing passkey again.',
      };
  }
};
