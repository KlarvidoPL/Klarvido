import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { GraphQLError } from 'graphql/error/GraphQLError';

import { render } from '../../../tests/utils/rendering';
import { TenantForm, TenantFormProps } from '../tenantForm.component';

const EMPTY_COMPANY_DETAILS = { nip: '', companyName: '', regon: '', address: '', vatStatus: '' };

describe('TenantForm: Component', () => {
  const defaultProps: TenantFormProps = {
    initialData: {
      name: 'initial name',
    },
    onSubmit: jest.fn(),
    loading: false,
  };

  const Component = (props: Partial<TenantFormProps>) => <TenantForm {...defaultProps} {...props} />;

  it('should display empty string', async () => {
    render(<Component initialData={{ name: '' }} />);
    const value = (await screen.findByPlaceholderText('Name')).getAttribute('value');
    expect(value).toBe('');
  });

  it('should not show company details unless enabled', async () => {
    render(<Component />);
    await screen.findByPlaceholderText('Name');
    expect(screen.queryByLabelText(/nip/i)).not.toBeInTheDocument();
  });

  describe('action completes successfully', () => {
    it('should call onSubmit prop', async () => {
      const onSubmit = jest.fn();
      render(<Component onSubmit={onSubmit} />);

      const nameField = await screen.findByPlaceholderText('Name');
      await userEvent.clear(nameField);
      await userEvent.type(nameField, 'new tenant name');
      await userEvent.click(screen.getByRole('button', { name: /save/i }));

      expect(onSubmit).toHaveBeenCalledWith({ name: 'new tenant name', ...EMPTY_COMPANY_DETAILS });
    });

    it('should submit company details', async () => {
      const onSubmit = jest.fn();
      render(
        <Component
          onSubmit={onSubmit}
          showCompanyDetails
          initialData={{ name: 'Acme', nip: '9721382373', vatStatus: 'ACTIVE' }}
        />
      );

      await userEvent.type(await screen.findByLabelText(/company name/i), 'ACME SP. Z O.O.');
      await userEvent.type(screen.getByLabelText(/regon/i), '123456785');
      await userEvent.type(screen.getByLabelText(/address/i), 'UL. PRZYKŁADOWA 1');
      await userEvent.click(screen.getByRole('button', { name: /save/i }));

      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Acme',
        nip: '9721382373',
        companyName: 'ACME SP. Z O.O.',
        regon: '123456785',
        address: 'UL. PRZYKŁADOWA 1',
        vatStatus: 'ACTIVE',
      });
    });
  });

  it('should not submit an invalid NIP', async () => {
    const onSubmit = jest.fn();
    render(<Component onSubmit={onSubmit} showCompanyDetails initialData={{ name: 'Acme', nip: '1234567890' }} />);

    await userEvent.click(await screen.findByRole('button', { name: /save/i }));

    expect(await screen.findByText('Invalid NIP number')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('should not submit an invalid REGON', async () => {
    const onSubmit = jest.fn();
    render(
      <Component
        onSubmit={onSubmit}
        showCompanyDetails
        initialData={{ name: 'Acme', nip: '9721382373', regon: '123456789' }}
      />
    );

    await userEvent.click(await screen.findByRole('button', { name: /save/i }));

    expect(await screen.findByText('Invalid REGON number')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('should show non field error if error', async () => {
    const mockError = { graphQLErrors: [new GraphQLError('Provided value is invalid')] } as any;
    render(<Component error={mockError as Error} />);

    expect(await screen.findByText('Provided value is invalid')).toBeInTheDocument();
  });
});
