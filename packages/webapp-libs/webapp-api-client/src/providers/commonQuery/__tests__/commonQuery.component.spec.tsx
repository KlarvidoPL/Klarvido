import { screen, waitFor } from '@testing-library/react';

import * as authRequests from '../../../api/auth/auth.requests';
import { currentUserFactory, fillCommonQueryWithUser } from '../../../tests/factories';
import { render } from '../../../tests/utils/rendering';
import { useCommonQuery } from '../commonQuery.hook';

const SessionStatus = () => {
  const { data } = useCommonQuery();
  return <span>{data?.currentUser ? 'Signed in' : 'Signed out'}</span>;
};

describe('session restoration on page reload', () => {
  afterEach(() => jest.restoreAllMocks());

  it('restores an expired access session before rendering anonymous routes', async () => {
    let finishRefresh!: (value: { success: boolean }) => void;
    const refresh = jest.spyOn(authRequests, 'coordinatedRefreshToken').mockImplementation(
      () =>
        new Promise((resolve) => {
          finishRefresh = resolve;
        })
    );
    render(<SessionStatus />, {
      apolloMocks: [fillCommonQueryWithUser(null), fillCommonQueryWithUser(currentUserFactory())],
    });

    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Signed out')).not.toBeInTheDocument();
    finishRefresh({ success: true });
    expect(await screen.findByText('Signed in')).toBeInTheDocument();
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('allows guests through after one failed refresh attempt', async () => {
    const refresh = jest
      .spyOn(authRequests, 'coordinatedRefreshToken')
      .mockRejectedValue(new Error('No refresh cookie'));
    render(<SessionStatus />, { apolloMocks: [fillCommonQueryWithUser(null)] });

    expect(await screen.findByText('Signed out')).toBeInTheDocument();
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('does not rotate refresh tokens when the access session is still valid', async () => {
    const refresh = jest.spyOn(authRequests, 'coordinatedRefreshToken');
    render(<SessionStatus />, { apolloMocks: [fillCommonQueryWithUser(currentUserFactory())] });

    expect(await screen.findByText('Signed in')).toBeInTheDocument();
    expect(refresh).not.toHaveBeenCalled();
  });
});
