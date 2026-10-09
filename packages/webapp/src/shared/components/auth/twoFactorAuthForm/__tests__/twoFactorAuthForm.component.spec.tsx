import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useWebAuthn } from '@sb/webapp-sso/hooks';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../../tests/utils/rendering';
import { TwoFactorAuthForm, TwoFactorAuthFormProps } from '../twoFactorAuthForm.component';
import { disableOtpMutation, generateOtpMutation } from '../twoFactorAuthForm.graphql';

jest.mock('@sb/webapp-core/services/analytics');
jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  useTenantPasskeys: jest.fn(),
}));
jest.mock('@sb/webapp-sso/hooks', () => ({ ...jest.requireActual('@sb/webapp-sso/hooks'), useWebAuthn: jest.fn() }));

const authorizePasskeyChange = jest.fn();
const noPasskeys = { passkeys: [], loading: false, refetch: jest.fn(), deletePasskey: jest.fn() };

beforeEach(() => {
  authorizePasskeyChange.mockReset().mockResolvedValue('fresh-proof');
  jest.mocked(useTenantPasskeys).mockReturnValue(noPasskeys as unknown as ReturnType<typeof useTenantPasskeys>);
  jest
    .mocked(useWebAuthn)
    .mockReturnValue({ authorizePasskeyChange, authorizeOtpOnly: jest.fn() } as unknown as ReturnType<
      typeof useWebAuthn
    >);
});

describe('TwoFactorAuthForm: Component', () => {
  const defaultProps: TwoFactorAuthFormProps = {};

  const Component = (props: Partial<TwoFactorAuthFormProps>) => <TwoFactorAuthForm {...defaultProps} {...props} />;

  // Skipped due to a known issue with React 19 strict mode + Apollo Client 4.x:
  // a component with a mutation-calling useEffect (AddTwoFactorAuth calls generateOtp
  // on mount) double-mounts under strict mode, and the first unmount aborts the
  // in-flight request, which throws a DOMException that crashes Jest. Re-enable once
  // Apollo Client fixes React 19 strict-mode compatibility.
  it.skip('should open 2FA setup modal directly when the account cannot reauthenticate', async () => {
    const generateOtpMock = composeMockedQueryResult(generateOtpMutation, {
      variables: { input: {} },
      data: { generateOtp: { base32: 'base32string', otpauthUrl: 'otpAuthUrl' } },
    });

    render(<Component />, {
      // No password, no passkeys (noPasskeys above): first-time enrollment skips the
      // reauth gate entirely, going straight to the QR setup modal.
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: false })), generateOtpMock],
    });

    const setupButton = await screen.findByRole('button', { name: /enable 2fa/i });
    await userEvent.click(setupButton);

    expect(await screen.findByText(/Set Up Two-Factor Authentication/i)).toBeInTheDocument();
  });

  it('asks to reauthenticate before opening the QR setup modal when the account has a password', async () => {
    render(<Component />, {
      apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true, otpEnabled: false }))],
    });

    await userEvent.click(await screen.findByRole('button', { name: /enable 2fa/i }));

    expect(await screen.findByText('Verify your identity')).toBeInTheDocument();
    expect(screen.queryByText(/Set Up Two-Factor Authentication/i)).not.toBeInTheDocument();
  });

  it('disables 2FA through a single confirm-and-verify dialog', async () => {
    const disableOtpMock = composeMockedQueryResult(disableOtpMutation, {
      variables: { input: {} },
      data: { disableOtp: { ok: true } },
    });
    const user = currentUserFactory({ hasUsablePassword: true, otpEnabled: true });

    render(<Component isEnabled />, {
      apolloMocks: [fillCommonQueryWithUser(user), disableOtpMock, fillCommonQueryWithUser(user)],
    });

    await userEvent.click(await screen.findByRole('button', { name: /disable/i }));

    // One dialog: the warning and the password/OTP form are both already there, no
    // separate "are you sure" step first.
    expect(screen.getByText('Disable two-factor authentication?')).toBeInTheDocument();
    expect(screen.getByLabelText('Account password')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Account password'), 'secret');
    const otpInput = screen.getByLabelText('Current two-factor code');
    await userEvent.click(otpInput);
    await userEvent.paste('123456');
    await userEvent.click(screen.getByRole('button', { name: 'Disable' }));

    await waitFor(() =>
      expect(authorizePasskeyChange).toHaveBeenCalledWith('otp_disable', undefined, 'secret', '123456')
    );
    expect(await screen.findByText(/Two-Factor Auth disabled successfully!/i)).toBeInTheDocument();
    expect(trackEvent).toHaveBeenCalledWith('auth', 'otp-disabled');
  });
});
