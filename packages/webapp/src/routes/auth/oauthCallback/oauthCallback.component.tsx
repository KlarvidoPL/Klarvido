import { auth } from '@sb/webapp-api-client/api';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { RoutesConfig } from '../../../app/config/routes';
import { getSafeAuthRedirect } from '../../../shared/utils/authRedirect';

/** Complete the cookie-authenticated OAuth session without exposing bearer tokens. */
export const OAuthCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const generateLocalePath = useGenerateLocalePath();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const next = getSafeAuthRedirect(searchParams.get('next'), '/');

      try {
        // Not coordinatedRefreshToken(): this is a fresh page load, so there's
        // no concurrent refresh in this tab to dedupe against, and that
        // helper's "another tab already refreshed" path resolves with
        // `undefined` even on success - which this page can't tell apart
        // from a real failure.
        const result = await auth.refreshToken();

        if (!result?.success) {
          setError('Unable to confirm your session. Please try again.');
          return;
        }

        trackEvent('auth', 'log-in-oauth');

        // Force a full page reload to reinitialize Apollo with the new session
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
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-muted-foreground">
          <FormattedMessage defaultMessage="Completing sign in..." id="OAuth / Callback / Loading" />
        </p>
      </div>
    </div>
  );
};
