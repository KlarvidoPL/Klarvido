import { fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils/fixtures';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql/error/GraphQLError';
import { append } from 'ramda';

import { render } from '../../../../../tests/utils/rendering';
import { PasswordResetConfirmForm, PasswordResetConfirmFormProps } from '../passwordResetConfirmForm.component';
import { authRequestPasswordResetConfirmMutation } from '../passwordResetConfirmForm.graphql';

jest.mock('@sb/webapp-core/services/analytics');

describe('PasswordResetConfirmForm: Component', () => {
  const defaultProps: PasswordResetConfirmFormProps = {
    user: 'user-id',
    token: 'token-value',
  };

  const defaultVariables = {
    input: { newPassword: 'new-password', user: 'user-id', token: 'token-value' },
  };

  const formData = {
    newPassword: 'new-password',
    confirmPassword: 'new-password',
  };

  const fillForm = async (data = {}) => {
    const d = { ...formData, ...data };
    await userEvent.type(await screen.findByLabelText(/^new password$/i), d.newPassword);
    if (d.confirmPassword) {
      await userEvent.type(screen.getByLabelText(/^confirm new password$/i), d.confirmPassword);
    }
  };

  const sendForm = async () => {
    await userEvent.click(screen.getByRole('button', { name: /^update password$/i }));
  };

  const Component = (props: Partial<PasswordResetConfirmFormProps>) => (
    <PasswordResetConfirmForm {...defaultProps} {...props} />
  );

  it('should show success message and sign the browser in (E04/forgot-password UX)', async () => {
    // Completing this is as strong a proof as a password, so the mutation now signs this
    // browser in immediately (fresh cookies) instead of sending the user back to /login to
    // type the password they just set - the frontend reflects that by refetching currentUser.
    const requestMock = composeMockedQueryResult(authRequestPasswordResetConfirmMutation, {
      variables: defaultVariables,
      data: {
        passwordResetConfirm: {
          ok: true,
          authenticated: true,
        },
      },
    });
    const refreshQueryMock = fillCommonQueryWithUser();

    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: (defaultMocks) => defaultMocks.concat(requestMock, refreshQueryMock),
    });

    await fillForm();
    await sendForm();

    const toast = await screen.findByTestId('toast-1');
    expect(toast).toHaveTextContent('Password reset successfully!');
    expect(trackEvent).toHaveBeenCalledWith('auth', 'reset-password-confirm');

    await waitForApolloMocks();
  });

  it('should show error if required value is missing', async () => {
    const requestMock = composeMockedQueryResult(authRequestPasswordResetConfirmMutation, {
      variables: defaultVariables,
      data: {},
    });
    render(<Component />, { apolloMocks: append(requestMock) });

    await fillForm({ confirmPassword: null });
    await sendForm();

    expect(screen.getByText(/please confirm your new password/i)).toBeInTheDocument();
  });

  it('should show field error if action throws error', async () => {
    const errorMessage = 'The password is too common.';

    const requestMock = composeMockedQueryResult(authRequestPasswordResetConfirmMutation, {
      variables: defaultVariables,
      data: {},
      errors: [
        new GraphQLError('GraphQlValidationError', {
          extensions: { nonFieldErrors: [{ message: errorMessage, code: errorMessage }] },
        }),
      ],
    });
    render(<Component />, { apolloMocks: append(requestMock) });

    await fillForm();
    await sendForm();

    expect(await screen.findByText(errorMessage)).toBeInTheDocument();
  });

  it('should show generic form error if action throws error', async () => {
    const errorMessage = 'Server error';

    const requestMock = composeMockedQueryResult(authRequestPasswordResetConfirmMutation, {
      variables: defaultVariables,
      data: {},
      errors: [new GraphQLError(errorMessage)],
    });

    render(<Component />, { apolloMocks: append(requestMock) });

    await fillForm();
    await sendForm();

    expect(await screen.findByText(errorMessage)).toBeInTheDocument();
  });
});
