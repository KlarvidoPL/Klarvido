import { storeAuthTokens } from '@sb/webapp-api-client/api';
import { csrfFetch } from '@sb/webapp-api-client/api/csrf';
import { Button } from '@sb/webapp-core/components/ui/button';
import { ENV } from '@sb/webapp-core/config/env';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { Fingerprint } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useLocation } from 'react-router-dom';

// Carries a stable error code through the catch block instead of a raw English
// message, so the UI can always show a translated string - the backend's own
// exception text (via PASSKEY_AUTH_ERROR_CODES) is for logs/debugging only.
class PasskeyLoginError extends Error {
  code: string;

  constructor(code: string) {
    super(code);
    this.code = code;
  }
}

// Helper to decode base64url to Uint8Array
const base64UrlToUint8Array = (base64url: string): Uint8Array => {
  // Convert base64url to base64
  const base64 = base64url
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(base64url.length + ((4 - (base64url.length % 4)) % 4), '=');

  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
};

// Helper to encode Uint8Array to base64url
const uint8ArrayToBase64Url = (bytes: Uint8Array): string => {
  const binaryString = String.fromCharCode(...bytes);
  const base64 = btoa(binaryString);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
};

/**
 * Passkey Login Button
 *
 * Allows users to authenticate using WebAuthn passkeys (biometrics, security keys).
 * Only shown if ENABLE_PASSKEYS feature flag is enabled.
 */
export const PasskeyLoginButton = () => {
  const intl = useIntl();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { search } = useLocation();

  // Keyed by the backend's PASSKEY_AUTH_ERROR_CODES codes, plus a few
  // frontend-only cases (options request failing, no credential returned, the
  // browser's own cancellation, and a generic fallback for anything unmapped).
  const errorMessages: Record<string, string> = {
    options_failed: intl.formatMessage({
      defaultMessage: 'Failed to start passkey sign-in. Please try again.',
      id: 'Auth / Passkey / error options failed',
    }),
    no_credential: intl.formatMessage({
      defaultMessage: 'No passkey was selected.',
      id: 'Auth / Passkey / error no credential',
    }),
    cancelled: intl.formatMessage({
      defaultMessage: 'Authentication was cancelled or timed out.',
      id: 'Auth / Passkey / error cancelled',
    }),
    passkey_not_found: intl.formatMessage({
      defaultMessage: 'Passkey not found.',
      id: 'Auth / Passkey / error not found',
    }),
    challenge_not_found: intl.formatMessage({
      defaultMessage: 'This sign-in attempt has expired. Please try again.',
      id: 'Auth / Passkey / error challenge not found',
    }),
    challenge_expired: intl.formatMessage({
      defaultMessage: 'This sign-in attempt has expired. Please try again.',
      id: 'Auth / Passkey / error challenge expired',
    }),
    challenge_mismatch: intl.formatMessage({
      defaultMessage: 'This sign-in attempt has expired. Please try again.',
      id: 'Auth / Passkey / error challenge mismatch',
    }),
    invalid_client_data: intl.formatMessage({
      defaultMessage: 'This sign-in attempt has expired. Please try again.',
      id: 'Auth / Passkey / error invalid client data',
    }),
    verification_failed: intl.formatMessage({
      defaultMessage: 'Failed to authenticate with passkey. Please try again.',
      id: 'Auth / Passkey / error verification failed',
    }),
  };

  // Check if passkeys feature is enabled
  if (!ENV.ENABLE_PASSKEYS) {
    return null;
  }

  // Check if WebAuthn is supported
  if (!window.PublicKeyCredential) {
    return null;
  }

  const handlePasskeyLogin = async () => {
    setLoading(true);
    setError(null);

    try {
      // 1. Get authentication options from backend
      const optionsResponse = await csrfFetch(`${ENV.BASE_API_URL}/sso/passkeys/authenticate/options`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
        credentials: 'include',
      });

      if (!optionsResponse.ok) {
        throw new PasskeyLoginError('options_failed');
      }

      const options = await optionsResponse.json();

      // 2. Create credential request (using base64url decoding)
      const publicKeyOptions: PublicKeyCredentialRequestOptions = {
        challenge: base64UrlToUint8Array(options.challenge) as BufferSource,
        timeout: options.timeout || 60000,
        rpId: options.rpId || window.location.hostname,
        userVerification: options.userVerification || 'preferred',
        allowCredentials: options.allowCredentials?.map(
          (cred: { id: string; type: string; transports?: string[] }) => ({
            id: base64UrlToUint8Array(cred.id),
            type: cred.type,
            transports: cred.transports,
          })
        ),
      };

      // 3. Get credential from browser
      const credential = (await navigator.credentials.get({
        publicKey: publicKeyOptions,
      })) as PublicKeyCredential;

      if (!credential) {
        throw new PasskeyLoginError('no_credential');
      }

      const response = credential.response as AuthenticatorAssertionResponse;

      // 4. Verify with backend (using base64url encoding)
      const verifyResponse = await csrfFetch(`${ENV.BASE_API_URL}/sso/passkeys/authenticate/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge: options.challenge,
          credentialId: uint8ArrayToBase64Url(new Uint8Array(credential.rawId)),
          authenticatorData: uint8ArrayToBase64Url(new Uint8Array(response.authenticatorData)),
          clientDataJSON: uint8ArrayToBase64Url(new Uint8Array(response.clientDataJSON)),
          signature: uint8ArrayToBase64Url(new Uint8Array(response.signature)),
          userHandle: response.userHandle ? uint8ArrayToBase64Url(new Uint8Array(response.userHandle)) : null,
        }),
        credentials: 'include',
      });

      if (!verifyResponse.ok) {
        const errorData = await verifyResponse.json();
        throw new PasskeyLoginError(errorData.code || 'verification_failed');
      }

      const verifyData = await verifyResponse.json();

      // Store tokens in localStorage (same as user/pass login) for Safari/mobile fallback
      if (verifyData?.access) {
        storeAuthTokens(verifyData.access, verifyData.refresh);
      }

      trackEvent('auth', 'passkey-login');

      // Parse the 'redirect' param from search if available (consistent with regular login)
      const params = new URLSearchParams(search);
      const redirect = params.get('redirect');

      // Get locale for default redirect
      const localeMatch = window.location.pathname.match(/^\/([a-z]{2})\//);
      const locale = localeMatch ? localeMatch[1] : 'en';
      const defaultRedirect = `/${locale}/`;

      // Force a full page reload to reinitialize with new auth cookies
      window.location.href = redirect || defaultRedirect;
    } catch (err) {
      console.error('Passkey login error:', err);
      let code = 'verification_failed';
      if (err instanceof PasskeyLoginError) {
        code = err.code;
      } else if (err instanceof Error && err.name === 'NotAllowedError') {
        code = 'cancelled';
      }
      setError(errorMessages[code] ?? errorMessages.verification_failed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <Button variant="outline" size="lg" className="w-full" onClick={handlePasskeyLogin} disabled={loading}>
        <Fingerprint className="mr-2 h-5 w-5" />
        {loading ? (
          <FormattedMessage defaultMessage="Authenticating..." id="Auth / Passkey / loading" />
        ) : (
          <FormattedMessage defaultMessage="Sign in with Passkey" id="Auth / Passkey / button" />
        )}
      </Button>
      {error && <p className="text-center text-sm text-destructive dark:text-red-400">{error}</p>}
    </div>
  );
};
