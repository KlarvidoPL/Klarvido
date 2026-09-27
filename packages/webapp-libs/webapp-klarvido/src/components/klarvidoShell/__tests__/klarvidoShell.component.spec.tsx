import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IntlProvider } from 'react-intl';

import { KlarvidoShell } from '../klarvidoShell.component';

const renderShell = (onLogout = jest.fn()) =>
  render(
    <IntlProvider locale="en">
      <KlarvidoShell
        companyName="Meble Kowalski Sp. z o.o."
        onLogout={onLogout}
        user={{ email: 'administrator@klarvido.com', firstName: 'Klarvido' }}
      />
    </IntlProvider>,
  );

describe('KlarvidoShell (KLV-007)', () => {
  it('renders the React shell around the reference workspace', () => {
    renderShell();

    expect(screen.getAllByText('Start').length).toBeGreaterThan(0);
    expect(screen.getByText('Meble Kowalski Sp. z o.o.')).toBeInTheDocument();
    expect(screen.getByTitle('Obszar roboczy Klarvido')).toHaveAttribute(
      'src',
      '/klarvido/mockup.html#/today',
    );
  });

  it('forwards sidebar navigation to the reference workspace', async () => {
    renderShell();

    await userEvent.click(screen.getAllByText('Faktury')[0]);

    expect(screen.getByTitle<HTMLIFrameElement>('Obszar roboczy Klarvido').contentWindow?.location.hash).toBe(
      '#/invoices',
    );
  });

  it('closes the mobile menu after navigating', async () => {
    renderShell();

    await userEvent.click(screen.getByRole('button', { name: 'Otwórz menu' }));
    expect(screen.getAllByRole('button', { name: 'Zamknij menu' })).not.toHaveLength(0);
    await userEvent.click(screen.getAllByText('Faktury').at(-1)!);

    expect(screen.getByTitle<HTMLIFrameElement>('Obszar roboczy Klarvido').contentWindow?.location.hash).toBe(
      '#/invoices',
    );
    expect(screen.queryByRole('button', { name: 'Zamknij menu' })).not.toBeInTheDocument();
  });

  it('opens and closes the assistant panel', async () => {
    renderShell();

    await userEvent.click(screen.getByRole('button', { name: 'Zapytaj Klarvido' }));
    expect(screen.getByRole('complementary', { name: 'Asystent Klarvido' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Zamknij asystenta' }));

    expect(screen.queryByRole('complementary', { name: 'Asystent Klarvido' })).not.toBeInTheDocument();
  });

  it('keeps the existing logout callback connected', async () => {
    const onLogout = jest.fn();
    renderShell(onLogout);

    await userEvent.click(screen.getAllByText('Klarvido')[1]);
    await userEvent.click(await screen.findByText('Wyloguj się'));

    expect(onLogout).toHaveBeenCalledTimes(1);
  });
});
