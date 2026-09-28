import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql';

import { render } from '../../../tests/utils/rendering';
import { Profile } from '../profile.component';
import { profileResendConfirmationEmailMutation } from '../profile.graphql';

describe('Profile: Component', () => {
  const Component = () => <Profile />;

  it('should display profile data', async () => {
    const apolloMocks = [
      fillCommonQueryWithUser(
        currentUserFactory({
          firstName: 'Jack',
          lastName: 'White',
          email: 'jack.white@mail.com',
        })
      ),
    ];
    render(<Component />, { apolloMocks });
    expect(await screen.findByDisplayValue('Jack')).toBeInTheDocument();
    expect(screen.getByDisplayValue('White')).toBeInTheDocument();
    expect(screen.getByText(/jack.white@mail.com/i)).toBeInTheDocument();
  });

  it('should not show a verification badge when the email is confirmed', async () => {
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ isConfirmed: true }))];
    render(<Component />, { apolloMocks });

    await screen.findByText(/profile overview/i);
    expect(screen.queryByText(/not verified/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /resend verification email/i })).not.toBeInTheDocument();
  });

  it('should show a "Not verified" badge and resend button when the email is unconfirmed', async () => {
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ isConfirmed: false }))];
    render(<Component />, { apolloMocks });

    expect(await screen.findByText(/not verified/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /resend verification email/i })).toBeInTheDocument();
  });

  it('should show a success toast when resending the confirmation email', async () => {
    const requestMock = composeMockedQueryResult(profileResendConfirmationEmailMutation, {
      variables: { input: {} },
      data: { resendConfirmationEmail: { ok: true } },
    });
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ isConfirmed: false })), requestMock];
    render(<Component />, { apolloMocks });

    const resendButton = await screen.findByRole('button', { name: /resend verification email/i });
    await userEvent.click(resendButton);

    const toast = await screen.findByTestId('toast-1');
    expect(toast).toHaveTextContent(/verification email sent/i);
  });

  it('should show an error toast when resending the confirmation email fails', async () => {
    const requestMock = composeMockedQueryResult(profileResendConfirmationEmailMutation, {
      variables: { input: {} },
      data: null,
      errors: [new GraphQLError('Rate limited')],
    });
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ isConfirmed: false })), requestMock];
    render(<Component />, { apolloMocks });

    const resendButton = await screen.findByRole('button', { name: /resend verification email/i });
    await userEvent.click(resendButton);

    const toast = await screen.findByTestId('toast-1');
    expect(toast).toHaveTextContent(/failed to send verification email/i);
  });
});
