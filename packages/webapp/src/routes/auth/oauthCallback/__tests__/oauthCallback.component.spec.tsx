import { trackEvent } from '@sb/webapp-core/services/analytics';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { createMockRouterProps, render } from '../../../../tests/utils/rendering';
import { OAuthCallback } from '../oauthCallback.component';

jest.mock('@sb/webapp-core/services/analytics');

const mockRefreshToken = jest.fn();
jest.mock('@sb/webapp-api-client/api', () => ({
  ...jest.requireActual<typeof import('@sb/webapp-api-client/api')>('@sb/webapp-api-client/api'),
  auth: { refreshToken: () => mockRefreshToken() },
}));

const mockNavigate = jest.fn();
const originalLocation = window.location;

const mockUseSearchParams = jest.fn(() => [new URLSearchParams('')]);

jest.mock('react-router-dom', () => ({
  ...jest.requireActual<typeof import('react-router-dom')>('react-router-dom'),
  useNavigate: () => mockNavigate,
  useSearchParams: () => mockUseSearchParams(),
}));

beforeEach(() => {
  mockNavigate.mockReset();
  mockRefreshToken.mockReset();
  Object.defineProperty(window, 'location', {
    value: { ...originalLocation, href: '' },
    writable: true,
  });
});

afterEach(() => {
  Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
});

describe('OAuthCallback: Component', () => {
  it('should refresh tokens and redirect to next when the token refresh succeeds', async () => {
    mockRefreshToken.mockResolvedValue({ access: 'access-token', refresh: 'refresh-token' });
    mockUseSearchParams.mockReturnValue([new URLSearchParams('?next=%2Fen%2Fprofile')]);

    render(<OAuthCallback />, {
      routerProps: createMockRouterProps(`auth/oauth/callback`, {}),
    });

    await screen.findByText(/completing sign in/i);

    expect(trackEvent).toHaveBeenCalledWith('auth', 'log-in-oauth');
    expect(window.location.href).toBe('/en/profile');
  });

  it('should ignore a cross-origin next and redirect to "/" instead (open-redirect guard)', async () => {
    mockRefreshToken.mockResolvedValue({ access: 'access-token', refresh: 'refresh-token' });
    mockUseSearchParams.mockReturnValue([new URLSearchParams('?next=https%3A%2F%2Fevil.example.com%2Fphish')]);

    render(<OAuthCallback />, {
      routerProps: createMockRouterProps(`auth/oauth/callback`, {}),
    });

    await screen.findByText(/completing sign in/i);

    expect(window.location.href).toBe('/');
  });

  it('should show error when the refresh response has no access token', async () => {
    mockRefreshToken.mockResolvedValue({});

    render(<OAuthCallback />, {
      routerProps: createMockRouterProps(`auth/oauth/callback`, {}),
    });

    expect(await screen.findByText(/missing authentication tokens/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /return to login/i })).toBeInTheDocument();
  });

  it('should show error when the token refresh call fails', async () => {
    mockRefreshToken.mockRejectedValue(new Error('401'));

    render(<OAuthCallback />, {
      routerProps: createMockRouterProps(`auth/oauth/callback`, {}),
    });

    expect(await screen.findByText(/failed to complete authentication/i)).toBeInTheDocument();
  });

  it('should navigate to login when return to login is clicked', async () => {
    mockRefreshToken.mockResolvedValue({});

    render(<OAuthCallback />, {
      routerProps: createMockRouterProps(`auth/oauth/callback`, {}),
    });

    const returnButton = await screen.findByRole('button', { name: /return to login/i });
    await userEvent.click(returnButton);

    expect(mockNavigate).toHaveBeenCalledWith('/en/auth/login');
  });
});
