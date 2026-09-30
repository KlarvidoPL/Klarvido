import { auth } from '@sb/webapp-api-client/api';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { RoutesConfig } from '../../../app/config/routes';

/**
 * This page is reachable directly (not gated behind an authenticated-only
 * check - see app.component.tsx for why), so `next` has to be treated as
 * untrusted input: anyone can craft a link to this URL with an arbitrary
 * `next` value, and if the visitor happens to already have a valid session,
 * the refresh below would succeed and this would otherwise navigate them
 * straight to an attacker-chosen destination (a classic open-redirect/
 * phishing setup). The backend only ever generates same-origin values here,
 * so anything else is rejected.
 */
const getSafeNext = (rawNext: string | null): string => {
  if (!rawNext) return '/';
  try {
    const target = new URL(rawNext, window.location.origin);
    return target.origin === window.location.origin ? rawNext : '/';
  } catch {
    return '/';
  }
};

/**
 * OAuth Callback Handler
 *
 * Google (and other social-provider) login is a full backend redirect chain
 * (provider -> API host -> here), so - unlike a client-side login mutation -
 * the frontend is never directly handed the access/refresh tokens. The
 * backend already set them as httpOnly cookies before landing here; this
 * page turns that into a normal token-refresh call (valid via those cookies)
 * to get the tokens into the JSON response body and store them the same way
 * every other login method does, so OAuth sessions get the same localStorage
 * fallback (used when the httpOnly cookie isn't reliably sent - Safari/iOS
 * ITP, third-party-cookie edge cases) that password/passkey/OTP/SSO logins
 * already have. No tokens ever pass through this page's URL.
 */
export const OAuthCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const generateLocalePath = useGenerateLocalePath();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const next = getSafeNext(searchParams.get('next'));

      try {
        // Not coordinatedRefreshToken(): this is a fresh page load, so there's
        // no concurrent refresh in this tab to dedupe against, and that
        // helper's "another tab already refreshed" path resolves with
        // `undefined` even on success - which this page can't tell apart
        // from a real failure.
        const tokens = await auth.refreshToken();

        if (!tokens?.access) {
          setError('Missing authentication tokens. Please try again.');
          return;
        }

        trackEvent('auth', 'log-in-oauth');

        // Force a full page reload to reinitialize Apollo with new tokens
        // This is more reliable than trying to reset the store in-flight
        window.location.href = next;
      } catch (err) {
        console.error('OAuth callback error:', err);
        setError('Failed to complete authentication. Please try again.');
      }
    };

    handleCallback();
  }, [searchParams]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="rounded-lg bg-destructive/10 p-6 text-center dark:bg-red-950/40">
          <h2 className="mb-2 text-lg font-semibold text-destructive dark:text-red-400">
            <FormattedMessage defaultMessage="Authentication Failed" id="OAuth / Callback / Error title" />
          </h2>
          <p className="text-sm text-muted-foreground">{error}</p>
          <button
            onClick={() => navigate(generateLocalePath(RoutesConfig.login))}
            className="mt-4 text-sm text-primary underline"
          >
            <FormattedMessage defaultMessage="Return to login" id="OAuth / Callback / Return to login" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto" />
        <p className="text-muted-foreground">
          <FormattedMessage defaultMessage="Completing sign in..." id="OAuth / Callback / Loading" />
        </p>
      </div>
    </div>
  );
};
