import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { TenantDeleted } from '../tenantDeleted.component';

describe('TenantDeleted: Component', () => {
  it('should say which organization was deleted and by whom', async () => {
    render(
      <TenantDeleted
        id="1"
        data={{ tenant_name: 'Test Org', name: 'John Doe' }}
        issuer={{ email: 'john@example.com', avatar: null }}
        readAt={null}
        createdAt="2024-01-01T00:00:00Z"
      />
    );

    expect(await screen.findByText(/john@example.com/i)).toBeInTheDocument();
    expect(screen.getByText(/organization "test org" was deleted by "john doe"/i)).toBeInTheDocument();
  });

  it('should use the issuer email when the name is empty', async () => {
    render(
      <TenantDeleted
        id="1"
        data={{ tenant_name: 'Test Org', name: '' }}
        issuer={{ email: 'jane@example.com', avatar: null }}
        readAt={null}
        createdAt="2024-01-01T00:00:00Z"
      />
    );

    expect(await screen.findByText(/organization "test org" was deleted by "jane@example.com"/i)).toBeInTheDocument();
  });
});
