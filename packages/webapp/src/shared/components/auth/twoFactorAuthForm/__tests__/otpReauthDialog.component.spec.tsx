import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { useWebAuthn } from '@sb/webapp-sso/hooks';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../../tests/utils/rendering';
import { OtpReauthDialog } from '../otpReauthDialog.component';

jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  useTenantPasskeys: jest.fn(),
}));
jest.mock('@sb/webapp-sso/hooks', () => ({ ...jest.requireActual('@sb/webapp-sso/hooks'), useWebAuthn: jest.fn() }));

const authorizePasskeyChange = jest.fn();
const authorizeOtpOnly = jest.fn();
const onClose = jest.fn();
const onAuthorized = jest.fn();

const noPasskeys = { passkeys: [], loading: false, refetch: jest.fn(), deletePasskey: jest.fn() };
const onePasskey = {
  passkeys: [{ id: 'pk-1', name: 'My key', authenticatorType: 'platform', createdAt: '2024-01-15', lastUsedAt: null, useCount: 0 }],
  loading: false,
  refetch: jest.fn(),
  deletePasskey: jest.fn(),
};

beforeEach(() => {
  authorizePasskeyChange.mockReset().mockResolvedValue('fresh-proof');
  authorizeOtpOnly.mockReset().mockResolvedValue('fresh-proof');
  onClose.mockReset();
  onAuthorized.mockReset();
  jest.mocked(useTenantPasskeys).mockReturnValue(noPasskeys as unknown as ReturnType<typeof useTenantPasskeys>);
  jest.mocked(useWebAuthn).mockReturnValue({
    authorizePasskeyChange,
    authorizeOtpOnly,
  } as unknown as ReturnType<typeof useWebAuthn>);
});

describe('OtpReauthDialog: enabling (otp_setup)', () => {
  it('asks for password and calls authorizePasskeyChange with the otp_setup action', async () => {
    render(<OtpReauthDialog open action="otp_setup" onClose={onClose} onAuthorized={onAuthorized} />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true, otpEnabled: false }))],
    });

    expect(await screen.findByText('Verify your identity')).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Account password'), 'secret');
    await userEvent.click(screen.getByRole('button', { name: 'Verify with password' }));

    await waitFor(() => expect(authorizePasskeyChange).toHaveBeenCalledWith('otp_setup', undefined, 'secret', undefined));
    expect(onAuthorized).toHaveBeenCalledWith('fresh-proof');
  });

  it('also sends the current code when OTP is already enabled (replacing the secret)', async () => {
    render(<OtpReauthDialog open action="otp_setup" onClose={onClose} onAuthorized={onAuthorized} />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true, otpEnabled: true }))],
    });

    await userEvent.type(await screen.findByLabelText('Account password'), 'secret');
    const otpInput = screen.getByLabelText('Current two-factor code');
    await userEvent.click(otpInput);
    await userEvent.paste('123456');
    await userEvent.click(screen.getByRole('button', { name: 'Verify with password' }));

    await waitFor(() =>
      expect(authorizePasskeyChange).toHaveBeenCalledWith('otp_setup', undefined, 'secret', '123456')
    );
  });
});

describe('OtpReauthDialog: disabling (otp_disable)', () => {
  it('shows the disable warning and a destructive Disable button in a single dialog', async () => {
    render(<OtpReauthDialog open action="otp_disable" onClose={onClose} onAuthorized={onAuthorized} />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true, otpEnabled: true }))],
    });

    expect(await screen.findByText('Disable two-factor authentication?')).toBeInTheDocument();
    expect(screen.getByText(/removes the extra layer of security/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Account password'), 'secret');
    const otpInput = screen.getByLabelText('Current two-factor code');
    await userEvent.click(otpInput);
    await userEvent.paste('654321');

    const submit = screen.getByRole('button', { name: 'Disable' });
    await userEvent.click(submit);

    await waitFor(() =>
      expect(authorizePasskeyChange).toHaveBeenCalledWith('otp_disable', undefined, 'secret', '654321')
    );
    expect(onAuthorized).toHaveBeenCalledWith('fresh-proof');
  });

  it('offers verifying with an existing passkey instead of a password', async () => {
    jest.mocked(useTenantPasskeys).mockReturnValue(onePasskey as unknown as ReturnType<typeof useTenantPasskeys>);
    // otpEnabled: false here - the passkey ceremony doesn't use a typed code at all (see
    // passkeysForm.reauthentication.spec.tsx's equivalent test), this isolates that path.
    render(<OtpReauthDialog open action="otp_disable" onClose={onClose} onAuthorized={onAuthorized} />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true, otpEnabled: false }))],
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Verify with an existing passkey' }));

    await waitFor(() =>
      expect(authorizePasskeyChange).toHaveBeenCalledWith('otp_disable', undefined, undefined, undefined)
    );
    expect(onAuthorized).toHaveBeenCalledWith('fresh-proof');
  });

  it('falls back to a code-only form when the account has no password and no passkey', async () => {
    render(<OtpReauthDialog open action="otp_disable" onClose={onClose} onAuthorized={onAuthorized} />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: false, otpEnabled: true }))],
    });

    expect(await screen.findByText(/enter your current two-factor code/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Account password')).not.toBeInTheDocument();
    const otpInput = screen.getByLabelText('Current two-factor code');
    await userEvent.click(otpInput);
    await userEvent.paste('111222');
    await userEvent.click(screen.getByRole('button', { name: 'Disable' }));

    await waitFor(() => expect(authorizeOtpOnly).toHaveBeenCalledWith('otp_disable', '111222'));
    expect(authorizePasskeyChange).not.toHaveBeenCalled();
  });

  it('calls onClose without authorizing when cancelled', async () => {
    render(<OtpReauthDialog open action="otp_disable" onClose={onClose} onAuthorized={onAuthorized} />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true, otpEnabled: false }))],
    });

    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }));

    expect(onClose).toHaveBeenCalled();
    expect(authorizePasskeyChange).not.toHaveBeenCalled();
  });
});
