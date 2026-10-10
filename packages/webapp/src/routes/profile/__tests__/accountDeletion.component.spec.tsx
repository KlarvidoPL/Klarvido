import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { useWebAuthn } from '@sb/webapp-sso/hooks';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../tests/utils/rendering';
import { AccountDeletion } from '../accountDeletion.component';
import { accountDeletionEligibilityQuery, deleteAccountMutation } from '../accountDeletion.graphql';

jest.mock('@sb/webapp-sso/hooks', () => ({ ...jest.requireActual('@sb/webapp-sso/hooks'), useWebAuthn: jest.fn() }));
jest.mock('@sb/webapp-tenants/hooks', () => ({
  ...jest.requireActual('@sb/webapp-tenants/hooks'),
  useGenerateTenantPath:
    () =>
    (_path: string, { tenantId }: { tenantId: string }) =>
      `/en/${tenantId}/tenant/settings/members`,
}));

const authorize = jest.fn();
beforeEach(() => {
  authorize.mockReset().mockResolvedValue('fresh-proof');
  jest
    .mocked(useWebAuthn)
    .mockReturnValue({ authorizePasskeyChange: authorize } as unknown as ReturnType<typeof useWebAuthn>);
});

const eligibility = (blocked = false, passkey = false) => ({
  request: { query: accountDeletionEligibilityQuery },
  result: {
    data: {
      accountDeletionBlockers: blocked ? [{ id: 'org', name: 'My organization', __typename: 'TenantType' }] : [],
      myPasskeys: {
        __typename: 'PasskeyConnection',
        edges: passkey
          ? [{ __typename: 'PasskeyEdge', node: { __typename: 'PasskeyType', id: 'key', isActive: true } }]
          : [],
      },
    },
  },
  maxUsageCount: Infinity,
});

it('blocks a last owner and links to organization membership management', async () => {
  render(<AccountDeletion />, { apolloMocks: [fillCommonQueryWithUser(currentUserFactory()), eligibility(true)] });
  expect(await screen.findByRole('link', { name: 'My organization' })).toHaveAttribute(
    'href',
    '/en/org/tenant/settings/members'
  );
  expect(screen.getByRole('button', { name: 'Delete account' })).toBeDisabled();
  expect(authorize).not.toHaveBeenCalled();
});

it('requires password setup for a social-only account with no passkey', async () => {
  render(<AccountDeletion />, {
    apolloMocks: [fillCommonQueryWithUser(currentUserFactory({ hasUsablePassword: false })), eligibility()],
  });
  expect(await screen.findByText(/Set a password using/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Delete account' })).toBeDisabled();
});

it('requires email confirmation and a fresh password, and keeps the dialog after a backend rejection', async () => {
  const user = currentUserFactory({ email: 'person@example.com', hasUsablePassword: true, otpEnabled: false });
  render(<AccountDeletion />, {
    apolloMocks: [
      fillCommonQueryWithUser(user),
      eligibility(),
      {
        request: { query: deleteAccountMutation, variables: { input: { confirmation: user.email } } },
        result: {
          errors: [
            {
              message: 'Ownership changed',
              extensions: { confirmation: [{ message: 'Transfer ownership first', code: 'invalid' }] },
            },
          ],
        },
      },
    ],
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Delete account' })).toBeEnabled());
  await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Your email address'), user.email);
  await userEvent.type(screen.getByLabelText('Current password'), 'current-secret');
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  await waitFor(() => expect(authorize).toHaveBeenCalledWith('account_delete', undefined, 'current-secret'));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.getByRole('alertdialog')).toBeInTheDocument();
});

it('does not submit deletion when fresh authentication fails', async () => {
  authorize.mockRejectedValue(new Error('Fresh authentication failed'));
  const user = currentUserFactory({ email: 'person@example.com', hasUsablePassword: true, otpEnabled: false });
  render(<AccountDeletion />, { apolloMocks: [fillCommonQueryWithUser(user), eligibility()] });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Delete account' })).toBeEnabled());
  await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));
  await userEvent.type(screen.getByLabelText('Your email address'), user.email);
  await userEvent.type(screen.getByLabelText('Current password'), 'wrong');
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.getByRole('alertdialog')).toBeInTheDocument();
});

it('requires OTP for passkey deletion and displays the backend OTP error in the shared destructive color', async () => {
  const user = currentUserFactory({
    email: 'person@example.com',
    hasUsablePassword: false,
    otpEnabled: true,
    otpVerified: true,
  });
  render(<AccountDeletion />, {
    apolloMocks: [
      fillCommonQueryWithUser(user),
      eligibility(false, true),
      {
        request: {
          query: deleteAccountMutation,
          variables: { input: { confirmation: user.email, otpToken: '123456' } },
        },
        result: {
          errors: [
            {
              message: 'Invalid code',
              extensions: { otpToken: [{ message: 'Invalid code', code: 'otp_verification_failure' }] },
            },
          ],
        },
      },
    ],
  });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Delete account' })).toBeEnabled());
  await userEvent.click(screen.getByRole('button', { name: 'Delete account' }));
  const confirm = screen.getByRole('button', { name: 'Confirm deletion with a passkey' });
  await userEvent.type(screen.getByLabelText('Your email address'), user.email);
  expect(confirm).toBeDisabled();
  await userEvent.type(screen.getByLabelText('Authentication code'), '123456');
  await userEvent.click(confirm);
  await waitFor(() => expect(authorize).toHaveBeenCalledWith('account_delete', undefined, undefined));
  expect(await screen.findByRole('alert')).toHaveClass('dark:text-red-400');
  expect(screen.getByLabelText('Authentication code')).toHaveValue('');
});
