import { ENV } from '@sb/webapp-core/config/env';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../tests/utils/rendering';
import { Login } from '../login.component';

let mockSearch = '';
const mockNavigate = jest.fn();
const mockCsrfFetch = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual<typeof import('react-router-dom')>('react-router-dom'),
  useLocation: () => ({ pathname: '/en/auth/login', search: mockSearch }),
  useNavigate: () => mockNavigate,
}));
jest.mock('@sb/webapp-api-client/api/csrf', () => ({ csrfFetch: (...args: unknown[]) => mockCsrfFetch(...args) }));
jest.mock('@sb/webapp-core/config/env', () => ({
  ...jest.requireActual<typeof import('@sb/webapp-core/config/env')>('@sb/webapp-core/config/env'),
  ENV: {
    ENABLE_SOCIAL_LOGIN: true,
    ENABLE_PASSKEYS: true,
    ENABLE_PASSWORD_LOGIN: true,
    BASE_API_URL: '/api',
    SUPPORT_EMAIL: '',
  },
}));
jest.mock('../../../../shared/components/auth/loginForm', () => ({ LoginForm: () => <div>Password login</div> }));
jest.mock('../../../../shared/components/auth/passkeyLoginButton', () => ({
  PasskeyLoginButton: () => <button>Passkey login</button>,
}));
jest.mock('../../../../shared/components/auth/socialLoginButtons', () => ({
  SocialLoginButtons: () => <button>Google login</button>,
}));

beforeEach(() => {
  mockSearch = '';
  mockNavigate.mockReset();
  mockCsrfFetch.mockReset();
  ENV.SUPPORT_EMAIL = '';
});

it('explains account confirmation and offers password or passkey without restarting Google login', async () => {
  mockSearch = '?social=link_required';
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  expect(screen.getByRole('status')).toHaveTextContent(/sign in below with your password/i);
  expect(screen.getByRole('status')).toHaveTextContent(/two-factor code/i);
  expect(screen.getByRole('heading', { name: /connect google to your account/i })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent(/two-factor authentication settings stay unchanged/i);
  expect(screen.getByText('Password login')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Passkey login' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Google login' })).not.toBeInTheDocument();
});

it('cancels the server-side confirmation before returning to ordinary login', async () => {
  mockSearch = '?social=link_required';
  mockCsrfFetch.mockResolvedValue({ ok: true });
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  await userEvent.click(screen.getByRole('button', { name: /cancel linking/i }));
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/en/auth/login', { replace: true }));
  expect(mockCsrfFetch).toHaveBeenCalledWith('/api/auth/social-link/cancel/', { method: 'POST' });
});

it('retains confirmation and offers a retry if cancellation fails', async () => {
  mockSearch = '?social=link_required';
  mockCsrfFetch.mockResolvedValue({ ok: false });
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  await userEvent.click(screen.getByRole('button', { name: /cancel linking/i }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/unable to cancel/i);
  expect(mockNavigate).not.toHaveBeenCalled();
});

it('explains that a matching account exists but is unconfirmed, without a support email configured', async () => {
  mockSearch = '?social=unconfirmed_account';
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  expect(screen.getByRole('status')).toHaveTextContent(/account with this email already exists/i);
  expect(screen.getByRole('heading', { name: /verify your email before connecting google/i })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /forgot your password/i })).toHaveAttribute(
    'href',
    '/en/auth/reset-password'
  );
  expect(screen.getByRole('status')).toHaveTextContent(/didn't create this account, contact support/i);
});

it('offers a mailto link to support when a support email is configured', async () => {
  ENV.SUPPORT_EMAIL = 'support@example.com';
  mockSearch = '?social=unconfirmed_account';
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  expect(screen.getByRole('link', { name: 'support@example.com' })).toHaveAttribute(
    'href',
    'mailto:support@example.com'
  );
});

it('shows a safe failure message for rejected social callbacks', async () => {
  mockSearch = '?social=failed';
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  expect(screen.getByRole('alert')).toHaveTextContent(/social sign-in could not be completed/i);
});

it('keeps normal social login available without a linking request', async () => {
  const { waitForApolloMocks } = render(<Login />);
  await waitForApolloMocks();
  expect(screen.getByRole('button', { name: 'Google login' })).toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
