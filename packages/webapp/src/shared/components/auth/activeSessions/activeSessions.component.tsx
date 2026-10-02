import { useMutation, useQuery } from '@apollo/client/react';
import { gql } from '@sb/webapp-api-client/graphql';
import { Button } from '@sb/webapp-core/components/buttons';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { Loader2, Monitor, Smartphone, Tablet, XCircle } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

// GraphQL queries and mutations
export const activeSessionsQuery = gql(`
  query ActiveSessionsQuery {
    mySessions(first: 50) {
      edges {
        node {
          id
          sessionId
          deviceName
          deviceType
          browser
          operatingSystem
          ipAddress
          location
          isActive
          isCurrent
          lastActivityAt
          expiresAt
          createdAt
        }
      }
    }
  }
`);

const REVOKE_SESSION_MUTATION = gql(`
  mutation RevokeSessionMutation($sessionId: String!, $reason: String) {
    revokeSession(sessionId: $sessionId, reason: $reason) {
      ok
    }
  }
`);

const REVOKE_ALL_SESSIONS_MUTATION = gql(`
  mutation RevokeAllSessionsMutation {
    revokeAllSessions {
      ok
      revokedCount
    }
  }
`);

interface SessionNode {
  id: string;
  sessionId: string;
  deviceName: string;
  deviceType: string;
  browser: string;
  operatingSystem: string;
  ipAddress: string;
  location: string;
  isActive: boolean;
  isCurrent: boolean;
  lastActivityAt: string;
  expiresAt: string;
  createdAt: string;
}

const getDeviceIcon = (deviceType: string) => {
  switch (deviceType?.toLowerCase()) {
    case 'mobile':
      return <Smartphone className="h-5 w-5" />;
    case 'tablet':
      return <Tablet className="h-5 w-5" />;
    default:
      return <Monitor className="h-5 w-5" />;
  }
};

// The backend stores "Unknown" when it can't tell the browser / OS from the user agent
const knownOrNull = (value?: string | null) => (value && value !== 'Unknown' ? value : null);

// Built here rather than using the backend's deviceName, which is a fixed English "{browser} on {os}"
const formatDeviceName = (session: SessionNode, intl: ReturnType<typeof useIntl>) => {
  const browser = knownOrNull(session.browser);
  const os = knownOrNull(session.operatingSystem);
  if (browser && os) {
    return intl.formatMessage({ defaultMessage: '{browser} on {os}', id: 'Sessions / Browser on OS' }, { browser, os });
  }
  return browser || os || intl.formatMessage({ defaultMessage: 'Unknown device', id: 'Sessions / Unknown device' });
};

// The backend records activity at most once a minute per session, so anything this recent counts as "now"
const ACTIVE_NOW_MINUTES = 2;

const formatLastActive = (session: SessionNode, intl: ReturnType<typeof useIntl>) => {
  const diffMinutes = Math.floor((Date.now() - new Date(session.lastActivityAt).getTime()) / (1000 * 60));

  // The current device is the one looking at this list, so it's always active now
  if (session.isCurrent || diffMinutes < ACTIVE_NOW_MINUTES) {
    return intl.formatMessage({ defaultMessage: 'Active now', id: 'Sessions / Active now' });
  }
  // Intl.RelativeTimeFormat handles each language's plural forms ("1 minutę temu", "4 minuty temu", "5 minut temu")
  let time: string;
  if (diffMinutes < 60) {
    time = intl.formatRelativeTime(-diffMinutes, 'minute');
  } else if (diffMinutes < 60 * 24) {
    time = intl.formatRelativeTime(-Math.floor(diffMinutes / 60), 'hour');
  } else {
    time = intl.formatRelativeTime(-Math.floor(diffMinutes / (60 * 24)), 'day');
  }
  return intl.formatMessage({ defaultMessage: 'Last active {time}', id: 'Sessions / Last active relative' }, { time });
};

const SessionDetails = ({ session }: { session: SessionNode }) => {
  const intl = useIntl();

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
      {session.ipAddress && (
        <>
          <span>{session.ipAddress}</span>
          <span>•</span>
        </>
      )}
      {session.location && (
        <>
          <span>{session.location}</span>
          <span>•</span>
        </>
      )}
      <span>
        <FormattedMessage
          defaultMessage="Signed in {date}"
          id="Sessions / Signed in date"
          values={{
            date: intl.formatDate(session.createdAt, {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            }),
          }}
        />
      </span>
      <span>•</span>
      <span>{formatLastActive(session, intl)}</span>
    </div>
  );
};

export const ActiveSessions = () => {
  const { toast } = useToast();
  const intl = useIntl();
  const [revokingId, setRevokingId] = useState<string | null>(null);

  // Fetch sessions from backend
  const { data, loading, refetch } = useQuery(activeSessionsQuery, {
    fetchPolicy: 'cache-and-network',
  });

  // Mutations
  const [revokeSession] = useMutation(REVOKE_SESSION_MUTATION, {
    onCompleted: () => {
      refetch();
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Session has been signed out.',
          id: 'Sessions / Session Revoked',
        }),
        variant: 'success',
      });
    },
    onError: () => {
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Failed to sign out session.',
          id: 'Sessions / Revoke Error',
        }),
        variant: 'destructive',
      });
    },
  });

  const [revokeAllSessions, { loading: revokingAll }] = useMutation(REVOKE_ALL_SESSIONS_MUTATION, {
    onCompleted: (result) => {
      refetch();
      const count = result?.revokeAllSessions?.revokedCount || 0;
      toast({
        description: intl.formatMessage(
          {
            defaultMessage: '{count, plural, =0 {No sessions} =1 {1 session} other {# sessions}} signed out.',
            id: 'Sessions / All Sessions Revoked',
          },
          { count }
        ),
        variant: 'success',
      });
    },
    onError: () => {
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Failed to sign out sessions.',
          id: 'Sessions / Revoke All Error',
        }),
        variant: 'destructive',
      });
    },
  });

  // Parse sessions from query result
  const sessions: SessionNode[] = (data?.mySessions?.edges || [])
    .map((edge) => edge?.node)
    .filter((node): node is SessionNode => node != null);
  const activeSessions = sessions.filter((s) => s.isActive);
  const otherSessions = activeSessions.filter((s) => !s.isCurrent);
  const currentSession = activeSessions.find((s) => s.isCurrent);

  const handleRevokeSession = async (session: SessionNode) => {
    setRevokingId(session.id);
    try {
      await revokeSession({
        variables: { sessionId: session.sessionId, reason: 'User requested' },
      });
    } finally {
      setRevokingId(null);
    }
  };

  const handleSignOutAllSessions = async () => {
    await revokeAllSessions();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Current Session */}
      {currentSession && (
        <div className="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-full bg-primary/10 p-2 text-primary">
              {getDeviceIcon(currentSession.deviceType)}
            </div>
            <div>
              <div className="mb-1 flex items-center gap-2">
                <p className="text-sm font-medium">{formatDeviceName(currentSession, intl)}</p>
                <Badge variant="default" className="text-xs">
                  <FormattedMessage defaultMessage="This device" id="Sessions / This Device Badge" />
                </Badge>
              </div>
              <SessionDetails session={currentSession} />
            </div>
          </div>
        </div>
      )}

      {/* Other Sessions */}
      {otherSessions.length > 0 && (
        <>
          <div className="space-y-2">
            {otherSessions.map((session) => (
              <div key={session.id} className="flex items-center justify-between rounded-lg border p-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-full bg-muted p-2">{getDeviceIcon(session.deviceType)}</div>
                  <div>
                    <p className="mb-1 text-sm font-medium">{formatDeviceName(session, intl)}</p>
                    <SessionDetails session={session} />
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRevokeSession(session)}
                  disabled={revokingId === session.id}
                >
                  {revokingId === session.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive dark:text-red-400" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Sign out all other sessions button */}
      {otherSessions.length > 0 && (
        <div className="flex justify-end pt-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={handleSignOutAllSessions}
            disabled={revokingAll}
            className="dark:bg-red-400 dark:hover:bg-red-400/90"
          >
            {revokingAll && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            <XCircle className="mr-2 h-4 w-4" />
            <FormattedMessage defaultMessage="Sign out all other sessions" id="Sessions / Sign Out All Button" />
          </Button>
        </div>
      )}

      {/* No other sessions message */}
      {otherSessions.length === 0 && (
        <p className="py-2 text-center text-sm text-muted-foreground">
          <FormattedMessage
            defaultMessage="No other active sessions. You're only signed in on this device."
            id="Sessions / No Other Sessions"
          />
        </p>
      )}
    </div>
  );
};
