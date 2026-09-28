import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../tests/utils/rendering';
import { welcomeModalMarkSeenMutation } from '../welcomeModal.graphql';

jest.mock('canvas-confetti');
import { WelcomeModal } from '../welcomeModal.component';

const markSeenMock = () =>
  composeMockedQueryResult(welcomeModalMarkSeenMutation, {
    variables: { input: {} },
    data: { markWelcomeModalSeen: { ok: true } },
  });

describe('WelcomeModal: Component', () => {
  it('should not render when currentUser.hasSeenWelcomeModal is true', async () => {
    const currentUser = currentUserFactory({ hasSeenWelcomeModal: true });
    const apolloMocks = [fillCommonQueryWithUser(currentUser)];
    const { waitForApolloMocks } = render(<WelcomeModal />, { apolloMocks });

    await waitForApolloMocks(0);

    expect(screen.queryByText(/welcome aboard/i)).not.toBeInTheDocument();
  });

  it('should render when currentUser.hasSeenWelcomeModal is false', async () => {
    const currentUser = currentUserFactory({ hasSeenWelcomeModal: false });
    const apolloMocks = [fillCommonQueryWithUser(currentUser), markSeenMock()];
    const { waitForApolloMocks } = render(<WelcomeModal />, { apolloMocks });

    await waitForApolloMocks(0);

    expect(await screen.findByText(/welcome aboard/i)).toBeInTheDocument();
  });

  it('should call markWelcomeModalSeen mutation when shown', async () => {
    const currentUser = currentUserFactory({ hasSeenWelcomeModal: false });
    const mutationMock = markSeenMock();
    const apolloMocks = [fillCommonQueryWithUser(currentUser), mutationMock];
    const { waitForApolloMocks } = render(<WelcomeModal />, { apolloMocks });

    await waitForApolloMocks(0);
    await screen.findByText(/welcome aboard/i);
    await waitForApolloMocks();

    expect(mutationMock.result).toHaveBeenCalled();
  });

  it('should close modal when Start Exploring is clicked', async () => {
    const currentUser = currentUserFactory({ hasSeenWelcomeModal: false });
    const apolloMocks = [fillCommonQueryWithUser(currentUser), markSeenMock()];
    const { waitForApolloMocks } = render(<WelcomeModal />, { apolloMocks });

    await waitForApolloMocks(0);
    await screen.findByText(/welcome aboard/i);
    await userEvent.click(await screen.findByRole('button', { name: /start exploring/i }));

    expect(screen.queryByText(/welcome aboard/i)).not.toBeInTheDocument();
  });
});
