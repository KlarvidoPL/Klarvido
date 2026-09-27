import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { PasskeyRegistered } from '../passkeyRegistered.component';

describe('PasskeyRegistered: Component', () => {
  it('should render title and content with passkey name', async () => {
    render(
      <PasskeyRegistered
        id="1"
        data={{
          passkey_name: 'MacBook Touch ID',
          authenticator_type: 'platform',
        }}
        readAt={null}
        createdAt="2024-01-01T00:00:00Z"
      />
    );

    expect(await screen.findByText(/passkey registered/i)).toBeInTheDocument();
    expect(screen.getByText(/a new passkey "macbook touch id" was added to your account/i)).toBeInTheDocument();
  });
});
