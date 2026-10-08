import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils/fixtures';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql/error';

import { render } from '../../../../../tests/utils/rendering';
import { useAuth } from '../../../../hooks';
import { ChangePasswordForm } from '../changePasswordForm.component';
import { authChangePasswordMutation } from '../changePasswordForm.graphql';

jest.mock('@sb/webapp-core/services/analytics');

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

  describe('when the account has no password yet (OAuth-only signup)', () => {
    const SetPasswordComponent = () => <ChangePasswordForm hasUsablePassword={false} />;

    it('should not render the old password field', async () => {
      const { waitForApolloMocks } = render(<SetPasswordComponent />);
      await waitForApolloMocks();

      expect(screen.queryByLabelText(/old password/i)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /set password/i })).toBeInTheDocument();
    });

    it('should submit without an oldPassword variable', async () => {
      const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
        variables: { input: { newPassword: formData.newPassword } },
        data: defaultResult,
      });

      const { waitForApolloMocks } = render(<SetPasswordComponent />, {
        apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock),
      });

      await waitForApolloMocks(0);

      await userEvent.type(screen.getByLabelText(/^new password/i), formData.newPassword);
      await userEvent.type(screen.getByLabelText(/confirm new password/i), formData.confirmNewPassword);
      await userEvent.click(screen.getByRole('button', { name: /set password/i }));

      await waitForApolloMocks();

      const toast = await screen.findByTestId('toast-1');
      expect(toast).toHaveTextContent('Password successfully set.');
    });

    it('should store fresh auth tokens after successfully setting a password', async () => {
      const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
        variables: { input: { newPassword: formData.newPassword } },
        data: { changePassword: { authenticated: true } },
      });

      const { waitForApolloMocks } = render(<SetPasswordComponent />, {
        apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock),
      });

      await waitForApolloMocks(0);

      await userEvent.type(screen.getByLabelText(/^new password/i), formData.newPassword);
      await userEvent.type(screen.getByLabelText(/confirm new password/i), formData.confirmNewPassword);
      await userEvent.click(screen.getByRole('button', { name: /set password/i }));

      await waitForApolloMocks();

      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('should refetch currentUser after successfully setting a password', async () => {
      const requestMock = composeMockedQueryResult(authChangePasswordMutation, {
        variables: { input: { newPassword: formData.newPassword } },
        data: defaultResult,
      });
      const initialUserMock = fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: false }));
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
        apolloMocks: [initialUserMock, requestMock, refetchedUserMock],
      });

      await waitForApolloMocks(0);
      expect(screen.getByTestId('has-usable-password')).toHaveTextContent('false');

      await userEvent.type(screen.getByLabelText(/^new password/i), formData.newPassword);
      await userEvent.type(screen.getByLabelText(/confirm new password/i), formData.confirmNewPassword);
      await userEvent.click(screen.getByRole('button', { name: /set password/i }));

      await waitForApolloMocks();

      await waitFor(() => {
        expect(screen.getByTestId('has-usable-password')).toHaveTextContent('true');
      });
    });
  });
});
