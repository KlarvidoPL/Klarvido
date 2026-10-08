import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql';
import { append } from 'ramda';

import { render } from '../../../../../tests/utils/rendering';
import { validateOtpMutation } from '../../twoFactorAuthForm/twoFactorAuthForm.graphql';
import { ValidateOtpForm } from '../validateOtpForm.component';

const mockNavigate = jest.fn();

jest.mock('@sb/webapp-core/services/analytics');

jest.mock('react-router-dom', () => {
  return {
    ...jest.requireActual<NodeModule>('react-router-dom'),
    useNavigate: () => mockNavigate,
  };
});

const Component = () => <ValidateOtpForm />;

const tokensMock = { authenticated: true };
const user = currentUserFactory();

describe('ValidateOtpForm: Component', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  it('should call trackEvent after successful validation', async () => {
    const token = '331553';
    const requestMock = composeMockedQueryResult(validateOtpMutation, {
      variables: { input: { otpToken: token } },
      data: { validateOtp: tokensMock },
    });

    const refreshQueryMock = fillCommonQueryWithUser(user);

    const { waitForApolloMocks } = render(<Component />, {
      apolloMocks: (mocks) => mocks.concat(requestMock, refreshQueryMock),
    });

    const input = await screen.findByPlaceholderText(/000000/i);
    const submitButton = screen.getByRole('button', { name: /verify code/i });

    await userEvent.type(input, token);
    await userEvent.click(submitButton);
    await waitForApolloMocks();

    expect(trackEvent).toHaveBeenCalledWith('auth', 'otp-validate');
  });

  it.each(['Verification token is invalid', 'Too many incorrect codes. Try again in 15 minutes.'])(
    'should display OTP error: %s',
    async (errorMessage) => {
      const token = '111111';
      // Remove data field so composeMockedQueryResult uses error field instead of result.errors
      const requestMock = composeMockedQueryResult(validateOtpMutation, {
        variables: { input: { otpToken: token } },
        data: {},
        errors: [new GraphQLError(errorMessage)],
      });

      render(<Component />, { apolloMocks: append(requestMock) });

      const input = await screen.findByPlaceholderText(/000000/i);
      const submitButton = screen.getByRole('button', { name: /verify code/i });

      await userEvent.type(input, token);
      await userEvent.click(submitButton);

      // Wait for error to be processed and displayed
      expect(
        await screen.findByText(
          errorMessage === 'Verification token is invalid' ? 'The verification code is invalid.' : errorMessage,
          {},
          { timeout: 3000 }
        )
      ).toBeInTheDocument();
    }
  );
  it('should translate an expired login challenge without exposing cookie details', async () => {
    const token = '111111';
    const technicalMessage = "No valid token found in cookie 'otp_auth_token'";
    const requestMock = composeMockedQueryResult(validateOtpMutation, {
      variables: { input: { otpToken: token } },
      data: {},
      errors: [
        new GraphQLError(technicalMessage, {
          extensions: { non_field_errors: [{ message: technicalMessage, code: 'invalid_token' }] },
        }),
      ],
    });
    render(<Component />, { apolloMocks: append(requestMock) });
    await userEvent.type(await screen.findByPlaceholderText(/000000/i), token);
    await userEvent.click(screen.getByRole('button', { name: /verify code/i }));
    expect(await screen.findByText('Your sign-in session has expired. Please sign in again.')).toBeInTheDocument();
    expect(screen.queryByText(technicalMessage)).not.toBeInTheDocument();
  });
});
