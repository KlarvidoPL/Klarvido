import { useQuery } from '@apollo/client/react';
import { setUserId } from '@sb/webapp-core/services/analytics';
import { PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { extractGraphQLErrors } from '../../api/apolloError.types';
import { coordinatedRefreshToken } from '../../api/auth/auth.requests';
import { CurrentUserType } from '../../graphql';
import commonDataContext from './commonQuery.context';
import { commonQueryCurrentUserQuery } from './commonQuery.graphql';

/**
 *
 * @param children
 * @constructor
 *
 * @category Component
 */
export const CommonQuery = ({ children }: PropsWithChildren) => {
  const { loading, data, error, refetch } = useQuery(commonQueryCurrentUserQuery, { nextFetchPolicy: 'network-only' });
  const redirectAttempted = useRef(false);
  const recoveryAttempted = useRef(false);
  const [recoveryFinished, setRecoveryFinished] = useState(false);
  const restoringSession = !loading && !error && data?.currentUser === null && !recoveryFinished;

  useEffect(() => {
    if (!restoringSession || recoveryAttempted.current) {
      return;
    }
    recoveryAttempted.current = true;

    // An expired access cookie produces a successful anonymous query, so the
    // error interceptor cannot restore this session. Try the HttpOnly refresh
    // cookie before route guards see an anonymous user. Guests simply remain
    // anonymous when no valid refresh cookie exists.
    void (async () => {
      try {
        await coordinatedRefreshToken();
        await refetch();
      } catch {
        // Leave the anonymous result intact; do not revoke a session on a
        // transient refresh failure or refresh repeatedly for signed-out users.
      } finally {
        setRecoveryFinished(true);
      }
    })();
  }, [restoringSession, refetch]);

  const reload = useCallback(async () => {
    try {
      await refetch();
    } catch (error) {
      // Ignore AbortError - this happens when the component unmounts during refetch
      // which is expected behavior during navigation/login flows
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      throw error;
    }
  }, [refetch]);

  const value = useMemo(() => ({ data: data || null, reload, loading, error }), [data, reload, loading, error]);

  const userId = (data?.currentUser as CurrentUserType)?.id;

  useEffect(() => {
    userId && setUserId(userId);
  }, [userId]);

  // Handle authentication errors - if we get an error and no data, the session likely expired
  // The refreshTokenLink should have already attempted to refresh and redirected if failed
  // This is a fallback to prevent blank pages if the redirect didn't happen
  useEffect(() => {
    if (error && !data && !loading && !redirectAttempted.current) {
      const graphQLErrors = extractGraphQLErrors(error);
      const isAuthError =
        error.message?.includes('401') ||
        error.message?.includes('Unauthorized') ||
        graphQLErrors?.some(
          (e) => e.extensions?.['code'] === 'UNAUTHENTICATED' || e.extensions?.['code'] === 'not_authenticated'
        );

      if (isAuthError) {
        redirectAttempted.current = true;

        // Extract locale from current pathname
        const pathname = window.location.pathname;
        const localeMatch = pathname.match(/^\/([a-z]{2})\//);
        const locale = localeMatch ? localeMatch[1] : 'en';

        // Preserve current URL as redirect parameter (include pathname and search params)
        const currentUrl = pathname + window.location.search;
        const redirectParam = encodeURIComponent(currentUrl);
        const loginPath = `/${locale}/auth/login?redirect=${redirectParam}`;

        // Only redirect if not already on login page
        if (!pathname.includes('/auth/login')) {
          // Clear stale auth data
          try {
            localStorage.removeItem('token');
            localStorage.removeItem('refresh_token');
          } catch {
            // Ignore storage errors
          }

          window.location.replace(loginPath);
        }
      }
    }
  }, [error, data, loading]);

  // Show loading state while fetching
  if (loading || restoringSession) {
    return null;
  }

  // If we have an error but no data, render children with null data
  // This allows the app to render (potentially showing login page or error state)
  // instead of showing a blank page forever
  if (error && !data) {
    // For non-auth errors or while redirecting, provide empty context to prevent blank page
    return <commonDataContext.Provider value={value}>{children}</commonDataContext.Provider>;
  }

  if (!data) {
    return null;
  }

  return <commonDataContext.Provider value={value}>{children}</commonDataContext.Provider>;
};
