import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils/fixtures';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useWebAuthn } from '@sb/webapp-sso/hooks';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql/error';

import { render } from '../../../../../tests/utils/rendering';
import { useAuth } from '../../../../hooks';
import { ChangePasswordForm } from '../changePasswordForm.component';
import { authChangePasswordMutation, requestPasswordSetLinkMutation } from '../changePasswordForm.graphql';

jest.mock('@sb/webapp-core/services/analytics');
jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  useTenantPasskeys: jest.fn(),
}));
jest.mock('@sb/webapp-sso/hooks', () => ({ ...jest.requireActual('@sb/webapp-sso/hooks'), useWebAuthn: jest.fn() }));

const noPasskeys = { passkeys: [], loading: false, refetch: jest.fn(), deletePasskey: jest.fn() };
const authorizeOtpOnly = jest.fn();

beforeEach(() => {
  authorizeOtpOnly.mockReset().mockResolvedValue('fresh-proof');
  jest.mocked(useTenantPasskeys).mockReturnValue(noPasskeys as unknown as ReturnType<typeof useTenantPasskeys>);
  jest
    .mocked(useWebAuthn)
    .mockReturnValue({ authorizePasskeyChange: jest.fn(), authorizeOtpOnly } as unknown as ReturnType<
      typeof useWebAuthn
    >);
});

afterEach(() => {
  localStorage.clear();
});

const formData = {
  oldPassword: 'old-pass',
  newPassword: 'new-pass',
  confirmNewPassword: 'new-pass',
};

const defaultValues = {
  input: {
    oldPassword: formData.oldPassword,
    newPassword: formData.newPassword,
  },
};

const defaultResult = {
  changePassword: {
    authenticated: true,
  },
};

describe('ChangePasswordForm: Component', () => {
  const Component = () => <ChangePasswordForm hasUsablePassword />;

  const fillForm = async (override = {}) => {
    const data = { ...formData, ...override };
    await userEvent.type(screen.getByLabelText(/old password/i), data.oldPassword);
    data.newPassword && (await userEvent.type(screen.getByLabelText(/^new password/i), data.newPassword));
    await userEvent.type(screen.getByLabelText(/confirm new password/i), data.confirmNewPassword);
  };

  const submitForm = () => userEvent.click(screen.getByRole('button', { name: /change password/i }));

  it('should show message on success action call', async () => {
    const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
      variables: defaultValues,
      data: defaultResult,
    });

    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock),
    });

    await waitForApolloMocks(0);

    await fillForm();
    await submitForm();
    await waitForApolloMocks();

    const toast = await screen.findByTestId('toast-1');
    expect(toast).toHaveTextContent('Password successfully changed.');
    expect(trackEvent).toHaveBeenCalledWith('profile', 'password-update');
  });

  it('should clear form', async () => {
    const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
      variables: defaultValues,
      data: defaultResult,
    });
    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock),
    });

    await waitForApolloMocks(0);

    await fillForm();
    await submitForm();

    await waitForApolloMocks();

    expect(screen.queryByDisplayValue(formData.oldPassword)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(formData.newPassword)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(formData.confirmNewPassword)).not.toBeInTheDocument();
  });

  it('should show error if required value is missing', async () => {
    const { waitForApolloMocks } = render(<Component />);

    await waitForApolloMocks();

    await fillForm({ newPassword: null });
    await submitForm();

    const toaster = await screen.findByTestId('toaster');
    expect(toaster).toBeEmptyDOMElement();

    expect(screen.getByText('New password is required')).toBeInTheDocument();
  });

  it('should show error if new passwords dont match', async () => {
    const { waitForApolloMocks } = render(<Component />);
    await waitForApolloMocks();

    await fillForm({ confirmNewPassword: 'misspelled-pass' });
    await submitForm();

    const toaster = await screen.findByTestId('toaster');
    expect(toaster).toBeEmptyDOMElement();

    expect(screen.getByText('Passwords must match')).toBeInTheDocument();
  });

  it('should show field error if action throws error', async () => {
    const errorMessage = 'This password is too common. Please choose a more unique password.';
    const errors = [
      new GraphQLError('GraphQlValidationError', {
        extensions: { newPassword: [{ message: errorMessage, code: 'password_too_common' }] },
      }),
    ];
    const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
      variables: defaultValues,
      data: {},
      errors,
    });

    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock),
    });

    await waitForApolloMocks(0);

    await fillForm();
    await submitForm();

    const toaster = await screen.findByTestId('toaster');
    expect(toaster).toBeEmptyDOMElement();

    expect(await screen.findByText(errorMessage, {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it('should show generic form error if action throws error', async () => {
    const errorMessage = 'Server error';
    const errors = [new GraphQLError(errorMessage)];
    const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
      variables: defaultValues,
      data: {},
      errors,
    });

    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock),
    });

    await waitForApolloMocks(0);

    await fillForm();
    await submitForm();

    const toaster = await screen.findByTestId('toaster');
    expect(toaster).toBeEmptyDOMElement();

    expect(await screen.findByText(errorMessage, {}, { timeout: 3000 })).toBeInTheDocument();
  });

  describe('when the account has no password, no passkey and no 2FA (E04: no fresh-auth factor)', () => {
    const SetPasswordComponent = () => <ChangePasswordForm hasUsablePassword={false} />;
    const getNoFactorMock = () =>
      fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: false, otpEnabled: false }));

    it('shows an emailed-link button instead of password fields - a bare session is not proof', async () => {
      const { waitForApolloMocks } = render(<SetPasswordComponent />, { apolloMocks: [getNoFactorMock()] });
      await waitForApolloMocks();

      expect(screen.queryByLabelText(/old password/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/^new password/i)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /email me a link/i })).toBeInTheDocument();
    });

    it('requests a one-time set-password link by email', async () => {
      const requestLinkMock = composeMockedQueryResult(requestPasswordSetLinkMutation, {
        variables: { input: {} },
        data: { requestPasswordSetLink: { ok: true } },
      });

      const { waitForApolloMocks } = render(<SetPasswordComponent />, {
        apolloMocks: [getNoFactorMock(), requestLinkMock],
      });

      await waitForApolloMocks(0);
      await userEvent.click(await screen.findByRole('button', { name: /email me a link/i }));
      await waitForApolloMocks();

      expect(await screen.findByTestId('toast-1')).toHaveTextContent("We've emailed you a link");
    });
  });

  describe('when the account has no password but has 2FA enabled (E04: fresh-auth via grant)', () => {
    const SetPasswordComponent = () => <ChangePasswordForm hasUsablePassword={false} />;
    const getOtpOnlyMock = () =>
      fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: false, otpEnabled: true }));

    it('shows the password fields directly (a grant is obtained on submit, not up front)', async () => {
      const { waitForApolloMocks } = render(<SetPasswordComponent />, { apolloMocks: [getOtpOnlyMock()] });
      await waitForApolloMocks();

      expect(screen.queryByLabelText(/old password/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/^new password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /set password/i })).toBeInTheDocument();
    });

    it('asks for a fresh-auth grant before submitting, then sets the password', async () => {
      const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
        variables: { input: { newPassword: formData.newPassword } },
        data: defaultResult,
      });

      const { waitForApolloMocks } = render(<SetPasswordComponent />, {
        apolloMocks: [getOtpOnlyMock(), requestMock],
      });

      await waitForApolloMocks(0);

      await userEvent.type(await screen.findByLabelText(/^new password/i), formData.newPassword);
      await userEvent.type(screen.getByLabelText(/confirm new password/i), formData.confirmNewPassword);
      await userEvent.click(screen.getByRole('button', { name: /set password/i }));

      // No grant yet: the dialog asks for the current code rather than submitting directly.
      expect(await screen.findByText('Verify your identity')).toBeInTheDocument();
      const otpInput = screen.getByLabelText('Current two-factor code');
      await userEvent.click(otpInput);
      await userEvent.paste('123456');
      await userEvent.click(screen.getByRole('button', { name: 'Verify' }));

      await waitFor(() => expect(authorizeOtpOnly).toHaveBeenCalledWith('password_set', '123456'));
      await waitForApolloMocks();

      expect(await screen.findByTestId('toast-1')).toHaveTextContent('Password successfully set.');
    });

    it('refetches currentUser after successfully setting a password', async () => {
      const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
        variables: { input: { newPassword: formData.newPassword } },
        data: defaultResult,
      });
      // Refetched after a successful "set password" call so currentUser.hasUsablePassword
      // (and thus the Old Password field) updates without a manual page refresh.
      const refetchedUserMock = fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: true }));

      const Probe = () => {
        const { currentUser } = useAuth();
        return <span data-testid="has-usable-password">{String(currentUser?.hasUsablePassword)}</span>;
      };

      const Wrapper = () => (
        <>
          <SetPasswordComponent />
          <Probe />
        </>
      );

      const { waitForApolloMocks } = render(<Wrapper />, {
        apolloMocks: [getOtpOnlyMock(), requestMock, refetchedUserMock],
      });

      await waitForApolloMocks(0);
      expect(await screen.findByTestId('has-usable-password')).toHaveTextContent('false');

      await userEvent.type(await screen.findByLabelText(/^new password/i), formData.newPassword);
      await userEvent.type(screen.getByLabelText(/confirm new password/i), formData.confirmNewPassword);
      await userEvent.click(screen.getByRole('button', { name: /set password/i }));

      const otpInput = await screen.findByLabelText('Current two-factor code');
      await userEvent.click(otpInput);
      await userEvent.paste('123456');
      await userEvent.click(screen.getByRole('button', { name: 'Verify' }));

      await waitForApolloMocks();

      await waitFor(() => {
        expect(screen.getByTestId('has-usable-password')).toHaveTextContent('true');
      });
    });
  });
});
