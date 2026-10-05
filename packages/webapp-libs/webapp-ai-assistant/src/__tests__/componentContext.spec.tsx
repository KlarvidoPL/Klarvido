import { ComponentKind } from '@sb/webapp-api-client/graphql';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { IntlProvider } from 'react-intl';
import { MemoryRouter } from 'react-router-dom';

import { askKlarvido } from '../componentContext';
import { CommandPalette } from '../components/commandPalette';

let mockTenantId = 'tenant-1';
const mockSend = jest.fn();
jest.mock('@sb/webapp-tenants/providers', () => ({
  useCurrentTenant: () => ({ data: { id: mockTenantId } }),
}));
jest.mock('@sb/webapp-tenants/hooks', () => ({
  useGenerateTenantPath: () => (path: string) => path,
}));
jest.mock('../hooks/useAiAssistant', () => ({
  useAiAssistant: () => ({
    messages: [],
    isLoading: false,
    sendMessage: mockSend,
    clearMessages: jest.fn(),
    isConnected: true,
    streamingState: { status: null, activeTools: [], isStreaming: false },
  }),
}));

it('shows removable attachments and discards another organization context', () => {
  const App = () => (
    <IntlProvider locale="en">
      <MemoryRouter>
        <CommandPalette />
      </MemoryRouter>
    </IntlProvider>
  );
  const { rerender } = render(<App />);
  act(() =>
    askKlarvido('other-tenant', 'FOREIGN', {
      kind: ComponentKind.INVOICE_LIST,
    }),
  );
  expect(screen.queryByText('FOREIGN')).not.toBeInTheDocument();
  act(() =>
    askKlarvido('tenant-1', 'FV/1', {
      kind: ComponentKind.INVOICE_DETAILS,
      invoiceIds: ['invoice-1'],
    }),
  );
  expect(screen.getByText('FV/1')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Usuń kontekst' }));
  expect(screen.queryByText('FV/1')).not.toBeInTheDocument();
  act(() =>
    askKlarvido('tenant-1', 'FV/2', {
      kind: ComponentKind.INVOICE_DETAILS,
      invoiceIds: ['invoice-2'],
    }),
  );
  mockTenantId = 'tenant-2';
  rerender(<App />);
  expect(screen.queryByText('FV/2')).not.toBeInTheDocument();
});
