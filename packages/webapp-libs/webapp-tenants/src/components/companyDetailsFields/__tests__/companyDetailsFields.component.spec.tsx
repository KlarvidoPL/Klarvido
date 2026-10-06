import { Locale, formatTranslationMessages } from '@sb/webapp-core/config/i18n';
import plMessages from '@sb/webapp-core/translations/pl.json';
import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { PropsWithChildren } from 'react';
import { FormProvider, useForm } from 'react-hook-form';

import { render } from '../../../tests/utils/rendering';
import { CompanyDetailsFields, CompanyDetailsFormFields, VatStatus } from '../companyDetailsFields.component';

const TenantWrapper = ({ children }: PropsWithChildren) => <>{children}</>;

const Harness = ({ vatStatus = '' }: { vatStatus?: string }) => {
  const form = useForm<CompanyDetailsFormFields>({
    defaultValues: { regon: '', companyName: '', address: '', vatStatus },
  });
  return (
    <FormProvider {...form}>
      <CompanyDetailsFields />
    </FormProvider>
  );
};

const renderInPolish = (ui: JSX.Element) =>
  render(ui, {
    TenantWrapper,
    intlLocale: Locale.POLISH,
    intlMessages: formatTranslationMessages(Locale.POLISH, plMessages),
  });

describe('CompanyDetailsFields: VAT status', () => {
  it('offers every VAT status with its translated label', async () => {
    renderInPolish(<Harness />);

    await userEvent.click(await screen.findByRole('combobox'));
    expect(screen.getByRole('option', { name: 'Czynny podatnik VAT' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Zwolniony z VAT' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Niezarejestrowany jako podatnik VAT' })).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(Object.keys(VatStatus).length);
  });

  it('shows the translated label of a saved VAT status instead of its raw code', async () => {
    renderInPolish(<Harness vatStatus={VatStatus.EXEMPT} />);

    expect(await screen.findByRole('combobox')).toHaveTextContent('Zwolniony z VAT');
    expect(screen.queryByText(VatStatus.EXEMPT)).not.toBeInTheDocument();
  });
});
