import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { SSODomainLapsed } from '../ssoDomainLapsed.component';

describe('SSODomainLapsed: Component', () => {
  it('should render title and the deactivated connections', async () => {
    render(
      <SSODomainLapsed
        id="1"
        data={{
          domain: 'client.pl',
          tenant_name: 'Test Org',
          connection_names: ['Okta'],
        }}
        readAt={null}
        createdAt="2024-01-01T00:00:00Z"
      />
    );

    expect(await screen.findByText(/sso domain lapsed/i)).toBeInTheDocument();
    expect(screen.getByText(/"client.pl" for "test org"/i)).toBeInTheDocument();
    expect(screen.getByText(/connections deactivated: okta/i)).toBeInTheDocument();
  });

  it('should render without connection names when none were deactivated', async () => {
    render(
      <SSODomainLapsed
        id="2"
        data={{
          domain: 'client.pl',
          tenant_name: 'Test Org',
          connection_names: [],
        }}
        readAt={null}
        createdAt="2024-01-01T00:00:00Z"
      />
    );

    expect(await screen.findByText(/no longer verified/i)).toBeInTheDocument();
    expect(screen.queryByText(/connections deactivated/i)).not.toBeInTheDocument();
  });
});
