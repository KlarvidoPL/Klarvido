import { fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { act, screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { companyLookupByNipQuery } from '../../../hooks/useCompanyLookup';
import { render as baseRender } from '../../../tests/utils/rendering';
import {
  organizationNipExistsQuery,
  organizationOnboardingDraftQuery,
  saveOrganizationOnboardingDraftMutation,
} from '../../organizationOnboarding/organizationOnboarding.graphql';
import { AddTenantForm } from '../addTenantForm.component';

jest.mock('@sb/webapp-core/services/analytics');

const NIP = '9721382373';
const render: typeof baseRender = (ui, options = {}) =>
  baseRender(ui, {
    ...options,
    apolloMocks: (mocks) => [
      ...mocks,
      composeMockedQueryResult(organizationOnboardingDraftQuery, { data: { organizationOnboardingDraft: null } }),
      {
        ...composeMockedQueryResult(organizationNipExistsQuery, {
          variables: { nip: NIP, country: 'PL' },
          data: { organizationNipExists: false },
        }),
        maxUsageCount: 10,
      },
      ...(typeof options.apolloMocks === 'function' ? options.apolloMocks([]) : (options.apolloMocks ?? [])),
    ],
  });

const lookupMock = (company: Record<string, string> | null) =>
  composeMockedQueryResult(companyLookupByNipQuery, {
    variables: { nip: NIP, country: 'PL' },
    data: {
      companyLookupByNip: {
        __typename: 'CompanyLookupType',
        found: !!company,
        nip: NIP,
        companyName: company?.companyName ?? null,
        regon: company?.regon ?? null,
        address: company?.address ?? null,
        vatStatus: company?.vatStatus ?? null,
      },
    },
  });

const fillStepOne = async (name = 'new item name', nip = NIP) => {
  await userEvent.type(await screen.findByPlaceholderText('Display name'), name);
  await userEvent.type(screen.getByLabelText(/nip/i), nip);
  await userEvent.click(screen.getByRole('button', { name: /next/i }));
};

describe('AddTenantForm: Component', () => {
  const Component = () => <AddTenantForm />;

  it('should display empty first step', async () => {
    render(<Component />);
    expect(await screen.findByPlaceholderText('Display name')).toHaveValue('');
    expect(screen.getByLabelText(/nip/i)).toHaveValue('');
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/role in the company/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create organization/i })).not.toBeInTheDocument();
    const progress = screen.getByRole('list', { name: 'Onboarding steps' });
    expect(within(progress).getAllByRole('listitem')).toHaveLength(8);
    expect(within(progress).getByText('Organization').closest('li')).toHaveAttribute('aria-current', 'step');
    expect(within(progress).getByText('KSeF')).toBeInTheDocument();
  });

  it('should preselect the only supported country and prefix the NIP with its code', async () => {
    render(<Component />);

    expect((await screen.findAllByRole('combobox'))[0]).toHaveTextContent('Poland');
    expect(screen.getByText(/currently supported: poland/i)).toBeInTheDocument();
    // The "PL" prefix sits inside the NIP input, as part of its label
    expect(screen.getByLabelText(/nip/i).closest('label')).toHaveTextContent('PL');
  });

  it('should accept the NIP pasted in its EU VAT number form', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne('Acme', 'PL 972-138-23-73');

    // Valid, and looked up as the plain NIP (the mock only matches nip "9721382373")
    expect(await screen.findByText(/couldn't find this NIP/i)).toBeInTheDocument();
  });

  it('should require a valid NIP before moving to the next step', async () => {
    render(<Component />);

    await fillStepOne('Acme', '1234567890');

    expect(await screen.findByText('Invalid NIP number')).toBeInTheDocument();
    expect(screen.queryByLabelText(/company name/i)).not.toBeInTheDocument();
  });

  it('should prefill company details found in the MF register', async () => {
    render(<Component />, {
      apolloMocks: [
        lookupMock({
          companyName: 'ACME SP. Z O.O.',
          regon: '123456785',
          address: 'UL. PRZYKŁADOWA 1, 00-001 WARSZAWA',
          vatStatus: 'ACTIVE',
        }),
      ],
    });

    await fillStepOne();

    expect(await screen.findByDisplayValue('ACME SP. Z O.O.')).toBeInTheDocument();
    expect(screen.getByText('Company details').closest('li')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByDisplayValue('123456785')).toBeInTheDocument();
    expect(screen.getByDisplayValue('UL. PRZYKŁADOWA 1, 00-001 WARSZAWA')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveTextContent('Active VAT payer');
    expect(screen.getByText(/we found your company/i)).toBeInTheDocument();
  });

  it('should leave company details empty when the NIP is not in the MF register', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne();

    expect(await screen.findByText(/couldn't find this NIP/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company name/i)).toHaveValue('');
    expect(screen.getByLabelText(/regon/i)).toHaveValue('');
    expect(screen.getByLabelText(/address/i)).toHaveValue('');
  });

  it('should allow manual entry when the MF lookup fails', async () => {
    const failedLookup = composeMockedQueryResult(companyLookupByNipQuery, {
      variables: { nip: NIP, country: 'PL' },
      errors: [{ message: 'MF unavailable' }],
    });
    render(<Component />, { apolloMocks: [failedLookup] });

    await fillStepOne();

    expect(await screen.findByText(/couldn't find this NIP/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/company name/i)).toBeEnabled();
    expect(screen.getByLabelText(/regon/i)).toBeEnabled();
    expect(screen.getByLabelText(/address/i)).toBeEnabled();
  });

  it('should require every company field before creating the organization', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne();

    // Nothing was found, so every field is empty: each one is flagged and creating is blocked
    expect(await screen.findByText('Company name is required')).toBeInTheDocument();
    expect(screen.getByText('REGON is required')).toBeInTheDocument();
    expect(screen.getByText('Address is required')).toBeInTheDocument();
    expect(screen.getByText('VAT status is required')).toBeInTheDocument();
    const createButton = screen.getByRole('button', { name: /next/i });
    expect(createButton).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/company name/i), 'JAN KOWALSKI');
    await userEvent.type(screen.getByLabelText(/regon/i), '123456785');
    await userEvent.type(screen.getByLabelText(/address/i), 'UL. DŁUGA 1, 00-001 WARSZAWA');
    expect(screen.queryByText('Company name is required')).not.toBeInTheDocument();
    // VAT status still missing
    expect(createButton).toBeDisabled();
  });

  it('should go back to step one and stay there, keeping its values', async () => {
    render(<Component />, { apolloMocks: [lookupMock(null)] });

    await fillStepOne('Acme');
    await userEvent.click(await screen.findByRole('button', { name: /back/i }));

    expect(await screen.findByPlaceholderText('Display name')).toHaveValue('Acme');
    expect(screen.getByLabelText(/nip/i)).toHaveValue(NIP);
    // Regression: the Back click used to be turned into a form submit (= Next) that jumped straight back to step 2
    await act(() => new Promise((resolve) => setTimeout(resolve, 100)));
    expect(screen.queryByLabelText(/company name/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
  });

  it('should name the fields the MF register is missing', async () => {
    render(<Component />, {
      apolloMocks: [
        lookupMock({
          companyName: 'JAN KOWALSKI',
          regon: '',
          address: 'UL. DŁUGA 1, 00-001 WARSZAWA',
          vatStatus: 'ACTIVE',
        }),
      ],
    });

    await fillStepOne();

    expect(await screen.findByText(/but it has no/i)).toHaveTextContent('REGON');
    expect(screen.getByDisplayValue('JAN KOWALSKI')).toBeInTheDocument();
    expect(screen.getByLabelText(/regon/i)).toHaveValue('');
  });

  it('rejects a NIP already present under the account before calling MF', async () => {
    baseRender(<Component />, {
      apolloMocks: (mocks) => [
        ...mocks,
        composeMockedQueryResult(organizationOnboardingDraftQuery, { data: { organizationOnboardingDraft: null } }),
        composeMockedQueryResult(organizationNipExistsQuery, {
          variables: { nip: NIP, country: 'PL' },
          data: { organizationNipExists: true },
        }),
      ],
    });
    await fillStepOne();
    expect(
      await screen.findByText('An organization with this NIP already exists in your account.')
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/company name/i)).not.toBeInTheDocument();
  });

  it('saves a draft after step two and continues to Customers without creating an organization', async () => {
    const company = {
      name: 'new item name',
      country: 'PL',
      nip: NIP,
      companyName: 'ACME SP. Z O.O.',
      regon: '123456785',
      address: 'Warsaw',
      vatStatus: 'ACTIVE',
    };
    const save = composeMockedQueryResult(saveOrganizationOnboardingDraftMutation, {
      variables: { step: 1, company },
      data: {
        saveOrganizationOnboardingDraft: {
          tenant: null,
          profile: { currentStep: 2, ksefStatus: 'not_connected', completedAt: null },
        },
      },
    });
    const draft = {
      companyData: company,
      respondentRole: '',
      customerType: '',
      revenueModels: [],
      costDrivers: [],
      pricing: '',
      mainGoal: '',
      currentStep: 2,
      isRequired: true,
      ksefStatus: 'not_connected',
      completedAt: null,
    };
    render(<Component />, {
      apolloMocks: [
        lookupMock(company),
        save,
        {
          ...composeMockedQueryResult(organizationOnboardingDraftQuery, {
            data: { organizationOnboardingDraft: draft },
          }),
          maxUsageCount: 3,
        },
      ],
    });
    await fillStepOne();
    await screen.findByDisplayValue(company.companyName);
    expect(screen.queryByRole('button', { name: /create organization/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(await screen.findByText('Who usually pays you?')).toBeInTheDocument();
    expect(save.result).toHaveBeenCalled();
    expect(screen.queryByText('Organization added successfully!')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByLabelText(/company name/i)).toHaveValue(company.companyName);
  });
  it('runs all eight steps and creates the organization only on Summary confirmation', async () => {
    const company = {
      name: 'new item name',
      country: 'PL',
      nip: NIP,
      companyName: 'ACME SP. Z O.O.',
      regon: '123456785',
      address: 'Warsaw',
      vatStatus: 'ACTIVE',
    };
    const token = 'x'.repeat(40);
    const answers = {
      respondentRole: 'ACCOUNTING',
      customerType: 'B2B',
      revenueModels: ['PROJECT'],
      costDrivers: ['MATERIALS'],
      pricing: 'FIXED',
      mainGoal: 'COSTS',
    };
    const draft = (currentStep: number) => ({
      companyData: company,
      ...answers,
      currentStep,
      isRequired: true,
      ksefStatus: currentStep === 7 ? 'demo' : 'not_connected',
      completedAt: null,
    });
    const query = (currentStep: number, maxUsageCount = 1) => ({
      ...composeMockedQueryResult(organizationOnboardingDraftQuery, {
        data: { organizationOnboardingDraft: draft(currentStep) },
      }),
      maxUsageCount,
    });
    const save = (step: number, variables: Record<string, unknown> = {}) =>
      composeMockedQueryResult(saveOrganizationOnboardingDraftMutation, {
        variables: { step, ...variables },
        data: {
          saveOrganizationOnboardingDraft: {
            tenant: step === 7 ? { id: 'created-tenant', name: company.name } : null,
            profile: {
              currentStep: Math.min(step + 1, 7),
              ksefStatus: step >= 6 ? 'demo' : 'not_connected',
              completedAt: step === 7 ? '2026-10-03T08:00:00Z' : null,
            },
          },
        },
      });
    const create = save(7, { company, ...answers });
    render(<Component />, {
      apolloMocks: [
        lookupMock(company),
        save(1, { company }),
        query(2, 2),
        save(2, { respondentRole: answers.respondentRole, customerType: answers.customerType }),
        query(3),
        save(3, { revenueModels: answers.revenueModels }),
        query(4),
        save(4, { costDrivers: answers.costDrivers }),
        query(5),
        save(5, { pricing: answers.pricing, mainGoal: answers.mainGoal }),
        query(6),
        save(6, { ksefToken: token }),
        query(7),
        create,
        fillCommonQueryWithUser(),
      ],
    });
    await fillStepOne();
    await screen.findByDisplayValue(company.companyName);
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Who usually pays you?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('What do customers pay you for?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Which costs grow with your sales?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(
      await screen.findByRole('heading', { name: 'How do you usually set prices?', level: 2 })
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('heading', { name: 'KSeF' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/ksef token/i), token);
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Your business profile')).toBeInTheDocument();
    expect(create.result).not.toHaveBeenCalled();
    expect(screen.queryByText('Organization added successfully!')).not.toBeInTheDocument();
    expect(screen.queryByText(token)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Create organization' }));
    expect(await screen.findByText('Organization added successfully!')).toBeInTheDocument();
    expect(create.result).toHaveBeenCalledTimes(1);
  });
});
