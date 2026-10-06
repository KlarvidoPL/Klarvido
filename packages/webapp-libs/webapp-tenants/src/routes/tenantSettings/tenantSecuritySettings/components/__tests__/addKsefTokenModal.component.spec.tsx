import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { render } from '@sb/webapp-api-client/tests/utils/rendering';
import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { useTenantKsef } from '../../../../../hooks/useTenantKsef';
import { membershipFactory, tenantFactory } from '../../../../../tests/factories/tenant';
import { AddKsefTokenModal } from '../addKsefTokenModal';

jest.mock('../../../../../hooks/useTenantKsef', () => ({
  useTenantKsef: jest.fn(),
}));

const mockedUseTenantKsef = useTenantKsef as jest.Mock;

const validCredential = { status: 'VALID', tokenName: 'KlarvidoTest', tokenHint: 'debb' };

describe('AddKsefTokenModal: Component', () => {
  const setToken = jest.fn();
  const closeModal = jest.fn();
  const onSaved = jest.fn();

  const renderModal = () => {
    const tenant = tenantFactory({ id: 'tenant-1', membership: membershipFactory({ role: 'OWNER' }) });
    const user = currentUserFactory({ tenants: [tenant] });
    return render(<AddKsefTokenModal tenantId="tenant-1" closeModal={closeModal} onSaved={onSaved} />, {
      apolloMocks: [fillCommonQueryWithUser(user)],
    });
  };

  const tokenInput = () => document.querySelector('input[type="password"]') as HTMLInputElement;

  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseTenantKsef.mockReturnValue({ setToken });
  });

  it('shows the four connection steps and the KSeF web application link', async () => {
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();

    expect(screen.getByText('Open the KSeF web application')).toBeInTheDocument();
    expect(screen.getByText('Generate a new token')).toBeInTheDocument();
    expect(screen.getByText('Copy the token')).toBeInTheDocument();
    expect(screen.getByText('Paste it below')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /ksef\.mf\.gov\.pl/i })).toHaveAttribute('href', 'https://ksef.mf.gov.pl');
  });

  it('asks for a token and does not submit when the field is empty', async () => {
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();

    await userEvent.click(screen.getByRole('button', { name: /verify and save/i }));

    expect(await screen.findByText('Paste the KSeF token')).toBeInTheDocument();
    expect(setToken).not.toHaveBeenCalled();
  });

  it('saves a verified token, then closes and refreshes the card', async () => {
    setToken.mockResolvedValue({
      data: { setKsefToken: { ok: true, errorCode: '', ksefCredential: validCredential } },
    });
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();

    await userEvent.type(tokenInput(), 'real-token-1234');
    await userEvent.click(screen.getByRole('button', { name: /verify and save/i }));

    await waitFor(() => expect(closeModal).toHaveBeenCalled());
    expect(setToken).toHaveBeenCalledWith({ variables: { tenantId: 'tenant-1', token: 'real-token-1234' } });
    expect(onSaved).toHaveBeenCalled();
  });

  it('still closes when KSeF was unreachable and the token was saved unverified', async () => {
    setToken.mockResolvedValue({
      data: {
        setKsefToken: {
          ok: true,
          errorCode: 'SERVICE_UNAVAILABLE',
          ksefCredential: { ...validCredential, status: 'UNVERIFIED' },
        },
      },
    });
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();

    await userEvent.type(tokenInput(), 'real-token-1234');
    await userEvent.click(screen.getByRole('button', { name: /verify and save/i }));

    await waitFor(() => expect(closeModal).toHaveBeenCalled());
    expect(onSaved).toHaveBeenCalled();
  });

  it('keeps the modal open and explains an invalid token without echoing it', async () => {
    setToken.mockResolvedValue({
      data: { setKsefToken: { ok: false, errorCode: 'INVALID_TOKEN', ksefCredential: null } },
    });
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();

    await userEvent.type(tokenInput(), 'wrong-token-0000');
    await userEvent.click(screen.getByRole('button', { name: /verify and save/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/did not accept this token/i);
    expect(screen.queryByText('wrong-token-0000')).not.toBeInTheDocument();
    expect(closeModal).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it('shows a generic error when the request fails', async () => {
    setToken.mockRejectedValue(new Error('network down'));
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();

    await userEvent.type(tokenInput(), 'real-token-1234');
    await userEvent.click(screen.getByRole('button', { name: /verify and save/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/something went wrong/i);
    expect(closeModal).not.toHaveBeenCalled();
  });

  it('explains missing invoice read permission and keeps the token modal open', async () => {
    setToken.mockResolvedValue({
      data: { setKsefToken: { ok: false, errorCode: 'INVOICE_READ_MISSING', ksefCredential: null } },
    });
    const { waitForApolloMocks } = renderModal();
    await waitForApolloMocks();
    await userEvent.type(tokenInput(), 'no-read-token');
    await userEvent.click(screen.getByRole('button', { name: /verify and save/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/invoice read permission \(InvoiceRead\)/i);
    expect(closeModal).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });
});
