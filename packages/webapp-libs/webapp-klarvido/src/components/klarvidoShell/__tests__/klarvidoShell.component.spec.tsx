import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IntlProvider } from 'react-intl';

import { KlarvidoShell } from '../klarvidoShell.component';

jest.mock('../../klarvidoWorkspace/klarvidoWorkspace.component', () => ({
  KlarvidoWorkspace: ({ activeRoute }: { activeRoute: string }) => (
    <div data-testid="workspace-route">{activeRoute}</div>
  ),
}));

const renderShell = (onLogout = jest.fn()) =>
  render(
    <IntlProvider locale="en">
      <KlarvidoShell
        companyName="Meble Kowalski Sp. z o.o."
        onLogout={onLogout}
        tenantId="VGVuYW50VHlwZTox"
        user={{ email: 'administrator@klarvido.com', firstName: 'Klarvido' }}
      />
    </IntlProvider>,
  );

describe('KlarvidoShell (KLV-007)', () => {
  it('renders the native shell without the legacy mockup iframe', () => {
    const { container } = renderShell();

    expect(screen.getAllByText('Start').length).toBeGreaterThan(0);
    expect(screen.getByText('Meble Kowalski Sp. z o.o.')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-route')).toHaveTextContent('today');
    expect(container.querySelector('iframe')).not.toBeInTheDocument();
  });

  it('changes the native workspace from sidebar navigation', async () => {
    renderShell();

    await userEvent.click(screen.getAllByText('Faktury')[0]);

    expect(screen.getByTestId('workspace-route')).toHaveTextContent('invoices');
  });

  it('routes notifications to the current settings view', async () => {
    renderShell();

    await userEvent.click(screen.getByRole('button', { name: 'Powiadomienia' }));

    expect(screen.getByTestId('workspace-route')).toHaveTextContent('settings');
  });

  it('keeps the existing logout callback connected', async () => {
    const onLogout = jest.fn();
    renderShell(onLogout);

    await userEvent.click(screen.getAllByText('Klarvido')[1]);
    await userEvent.click(await screen.findByText('Wyloguj się'));

    expect(onLogout).toHaveBeenCalledTimes(1);
  });
});
