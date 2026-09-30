import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen } from '@testing-library/react';

import { render } from '../../../../../tests/utils/rendering';
import { ActiveSessions, activeSessionsQuery } from '../activeSessions.component';

const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60 * 1000).toISOString();

const sessionNode = (overrides: Record<string, unknown>) => ({
  __typename: 'SSOSessionType',
  id: 'session-1',
  sessionId: 'session-id-1',
  deviceName: 'Chrome on macOS',
  deviceType: 'desktop',
  browser: 'Chrome',
  operatingSystem: 'macOS',
  ipAddress: '10.0.0.1',
  location: '',
  isActive: true,
  isCurrent: false,
  lastActivityAt: minutesAgo(0),
  expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
  createdAt: '2026-09-28T08:15:00Z',
  ...overrides,
});

const sessionsMock = (nodes: ReturnType<typeof sessionNode>[]) =>
  composeMockedQueryResult(activeSessionsQuery, {
    data: {
      mySessions: {
        __typename: 'SSOSessionConnection',
        edges: nodes.map((node) => ({ __typename: 'SSOSessionEdge', node })),
      },
    },
  });

describe('ActiveSessions: Component', () => {
  it('should show when each session signed in and how long ago it was active', async () => {
    render(<ActiveSessions />, {
      apolloMocks: [
        sessionsMock([
          sessionNode({ id: 'current', isCurrent: true, lastActivityAt: minutesAgo(0) }),
          sessionNode({ id: 'other', deviceName: 'Firefox on Windows', lastActivityAt: minutesAgo(4) }),
        ]),
      ],
    });

    expect(await screen.findByText('Firefox on Windows')).toBeInTheDocument();
    // The exact sign-in date stays visible for every session
    expect(screen.getAllByText(/^Signed in 09\/28\/2026/)).toHaveLength(2);
    expect(screen.getByText('Active now')).toBeInTheDocument();
    expect(screen.getByText('Last active 4 minutes ago')).toBeInTheDocument();
  });

  it('should use the singular form for one unit', async () => {
    render(<ActiveSessions />, {
      apolloMocks: [sessionsMock([sessionNode({ isCurrent: true, lastActivityAt: minutesAgo(1) })])],
    });

    expect(await screen.findByText('Last active 1 minute ago')).toBeInTheDocument();
  });
});
