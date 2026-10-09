import { screen, waitFor, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../../tests/utils/rendering';
import { SocialAccounts } from '../socialAccounts.component';

const mockFetch = jest.fn();
const mockUnlink = jest.fn();
const mockNavigate = jest.fn();
jest.mock('@sb/webapp-api-client/api/csrf', () => ({ csrfFetch: (...args: unknown[]) => mockFetch(...args) }));
jest.mock('@sb/webapp-sso/hooks', () => ({
  ...jest.requireActual<typeof import('@sb/webapp-sso/hooks')>('@sb/webapp-sso/hooks'),
  useWebAuthn: () => ({ unlinkSocialAccount: mockUnlink, isSupported: true }),
}));
jest.mock('react-router-dom', () => ({
  ...jest.requireActual<typeof import('react-router-dom')>('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const account = { id: '12', provider: 'google-oauth2', canUnlink: true };
const data = { accounts: [account], hasPassword: true, hasPasskey: true, otpEnabled: true };

beforeEach(() => {
  mockFetch.mockReset();
  mockUnlink.mockReset();
  mockNavigate.mockReset();
  mockFetch.mockResolvedValue({ ok: true, json: async () => data });
});

it('lists the provider and opens a fresh-authentication dialog', async () => {
  render(<SocialAccounts />);
  expect(await screen.findByText('Google')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: /^disconnect$/i }));
  expect(screen.getByRole('dialog')).toHaveTextContent(/signs you out on all devices/i);
  expect(screen.getByLabelText(/account password/i)).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText(/two-factor code/i)).toHaveAttribute('inputmode', 'numeric');
});

it('submits password and OTP, then uses the existing logout route to clear client state', async () => {
  mockUnlink.mockResolvedValue(undefined);
  render(<SocialAccounts />);
  await userEvent.click(await screen.findByRole('button', { name: /^disconnect$/i }));
  await userEvent.type(screen.getByLabelText(/account password/i), 'correct-password');
  await userEvent.type(screen.getByLabelText(/two-factor code/i), '012345');
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /^disconnect$/i }));
  await waitFor(() => expect(mockUnlink).toHaveBeenCalledWith('12', 'correct-password', '012345'));
  expect(mockNavigate).toHaveBeenCalledWith('/en/auth/logout', { replace: true });
});

it('supports passkey confirmation without password or OTP', async () => {
  mockUnlink.mockResolvedValue(undefined);
  render(<SocialAccounts />);
  await userEvent.click(await screen.findByRole('button', { name: /^disconnect$/i }));
  await userEvent.click(screen.getByRole('button', { name: /verify with an existing passkey/i }));
  expect(mockUnlink).toHaveBeenCalledWith('12', undefined, undefined);
});

it('keeps the connection and clears entered secrets after verification failure', async () => {
  mockUnlink.mockRejectedValue({ code: 'incorrect_password' });
  mockFetch.mockResolvedValue({ ok: true, json: async () => ({ ...data, otpEnabled: false }) });
  render(<SocialAccounts />);
  await userEvent.click(await screen.findByRole('button', { name: /^disconnect$/i }));
  expect(screen.queryByLabelText(/two-factor code/i)).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/account password/i), 'wrong');
  await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: /^disconnect$/i }));
  expect(await screen.findByText(/account password is incorrect/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/account password/i)).toHaveValue('');
  expect(mockNavigate).not.toHaveBeenCalled();
});

it('prevents disconnecting the last available login method', async () => {
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => ({ ...data, accounts: [{ ...account, canUnlink: false }] }),
  });
  render(<SocialAccounts />);
  expect(await screen.findByRole('button', { name: /^disconnect$/i })).toBeDisabled();
  expect(screen.getByText(/add a password or passkey/i)).toBeInTheDocument();
});

it('shows a load error without displaying account details', async () => {
  mockFetch.mockResolvedValue({ ok: false });
  render(<SocialAccounts />);
  expect(await screen.findByRole('alert')).toHaveTextContent(/unable to load connected accounts/i);
});
