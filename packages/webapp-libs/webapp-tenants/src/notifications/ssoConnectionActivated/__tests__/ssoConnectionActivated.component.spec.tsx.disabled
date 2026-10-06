import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { SSOConnectionActivated } from '../ssoConnectionActivated.component';

describe('SSOConnectionActivated: Component', () => {
  it('should render title and content with connection details', async () => {
    render(
      <SSOConnectionActivated
        id="1"
        data={{
          connection_name: 'Okta',
          connection_type: 'SAML',
          tenant_name: 'Test Org',
        }}
        readAt={null}
        createdAt="2024-01-01T00:00:00Z"
      />
    );

    expect(await screen.findByText(/sso connection activated/i)).toBeInTheDocument();
    expect(screen.getByText(/saml connection "okta" for "test org" is now active/i)).toBeInTheDocument();
  });
});
