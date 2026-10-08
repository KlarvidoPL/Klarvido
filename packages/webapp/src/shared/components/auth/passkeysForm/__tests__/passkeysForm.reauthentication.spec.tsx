import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { useWebAuthn } from '@sb/webapp-sso/hooks';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../../tests/utils/rendering';
import { PasskeysForm } from '../passkeysForm.component';

jest.mock('@sb/webapp-core/config/env', () => ({ ENV: { ENABLE_PASSKEYS: true, BASE_API_URL: '/api' } }));
jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  useTenantPasskeys: jest.fn(),
}));
jest.mock('@sb/webapp-sso/hooks', () => ({ useWebAuthn: jest.fn() }));

const authorize = jest.fn();
const remove = jest.fn();
const register = jest.fn();
const passkey = {
  id: 'pk-1',
  name: 'My security key',
  authenticatorType: 'platform',
  createdAt: '2024-01-15',
  lastUsedAt: null,
  useCount: 0,
};
const supportDescriptor = Object.getOwnPropertyDescriptor(window, 'PublicKeyCredential');

beforeEach(() => {
  Object.defineProperty(window, 'PublicKeyCredential', { configurable: true, value: jest.fn() });
  authorize.mockReset().mockResolvedValue('fresh-proof');
  remove.mockReset().mockResolvedValue({});
  register.mockReset().mockResolvedValue(true);
  jest.mocked(useTenantPasskeys).mockReturnValue({
    passkeys: [passkey],
    loading: false,
    refetch: jest.fn(),
    deletePasskey: remove,
  } as unknown as ReturnType<typeof useTenantPasskeys>);
  jest
    .mocked(useWebAuthn)
    .mockReturnValue({ authorizePasskeyChange: authorize, registerPasskey: register } as unknown as ReturnType<
      typeof useWebAuthn
    >);
});

afterEach(() => {
  if (supportDescriptor) Object.defineProperty(window, 'PublicKeyCredential', supportDescriptor);
  else Reflect.deleteProperty(window, 'PublicKeyCredential');
});

it('verifies an existing passkey before deleting and sends its authorization header', async () => {
  render(<PasskeysForm />);
  await userEvent.click(await screen.findByRole('button', { name: 'Remove passkey?' }));
  expect(remove).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Verify with an existing passkey' }));
  await waitFor(() =>
    expect(remove).toHaveBeenCalledWith({
      variables: { input: { id: 'pk-1' } },
      context: { headers: { 'X-Passkey-Authorization': 'fresh-proof' } },
    })
  );
  expect(authorize).toHaveBeenCalledWith('delete', 'pk-1', undefined, undefined);
});

it('keeps the passkey when verification fails', async () => {
  authorize.mockRejectedValue(new Error('Verification failed'));
  render(<PasskeysForm />);
  await userEvent.click(await screen.findByRole('button', { name: 'Remove passkey?' }));
  await userEvent.click(screen.getByRole('button', { name: 'Verify with an existing passkey' }));
  await waitFor(() => expect(authorize).toHaveBeenCalled());
  expect(remove).not.toHaveBeenCalled();
  expect(screen.getByRole('dialog')).toBeInTheDocument();
});

it('verifies password and OTP before registering the first passkey', async () => {
  jest.mocked(useTenantPasskeys).mockReturnValue({
    passkeys: [],
    loading: false,
    refetch: jest.fn(),
    deletePasskey: remove,
  } as unknown as ReturnType<typeof useTenantPasskeys>);
  render(<PasskeysForm />, {
    apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ otpEnabled: true, otpVerified: true }))],
  });
  await userEvent.click(await screen.findByRole('button', { name: 'Add Passkey' }));
  await userEvent.type(screen.getByLabelText('Give your passkey a name'), 'My new key');
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(register).not.toHaveBeenCalled();
  await userEvent.type(screen.getByLabelText('Account password'), 'password');
  const otpInput = screen.getByLabelText('Two-factor code');
  await userEvent.type(otpInput, 'letters');
  expect(otpInput).toHaveValue('');
  expect(screen.getByRole('button', { name: 'Verify with password' })).toBeDisabled();
  await userEvent.click(otpInput);
  await userEvent.paste('12ab3456');
  expect(otpInput).toHaveValue('123456');
  await userEvent.click(screen.getByRole('button', { name: 'Verify with password' }));
  await waitFor(() => expect(register).toHaveBeenCalledWith('My new key', 'fresh-proof'));
  expect(authorize).toHaveBeenCalledWith('register', undefined, 'password', '123456');
});

it('hides the two-factor field when OTP is disabled and verifies with password alone', async () => {
  render(<PasskeysForm />, { apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ otpEnabled: false }))] });
  await userEvent.click(await screen.findByRole('button', { name: 'Remove passkey?' }));
  expect(screen.queryByLabelText('Two-factor code')).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Account password'), 'password');
  await userEvent.click(screen.getByRole('button', { name: 'Verify with password' }));
  await waitFor(() => expect(authorize).toHaveBeenCalledWith('delete', 'pk-1', 'password', undefined));
});
