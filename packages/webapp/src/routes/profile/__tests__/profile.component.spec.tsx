import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { Profile } from '../profile.component';

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
  });

  it('should show a "Not verified" badge when the email is unconfirmed', async () => {
    const apolloMocks = [fillCommonQueryWithUser(currentUserFactory({ isConfirmed: false }))];
    render(<Component />, { apolloMocks });

    expect(await screen.findByText(/not verified/i)).toBeInTheDocument();
  });
});
