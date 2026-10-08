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
