import { currentUserFactory, fillCommonQueryWithUser } from '@sb/webapp-api-client/tests/factories';
import { composeMockedQueryResult } from '@sb/webapp-api-client/tests/utils';
import { screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { PropsWithChildren } from 'react';
import { useLocation } from 'react-router';

import currentTenantContext from '../../../providers/currentTenantProvider/currentTenantProvider.context';
import { tenantFactory } from '../../../tests/factories/tenant';
import { render } from '../../../tests/utils/rendering';
import { OrganizationOnboarding } from '../organizationOnboarding.component';
import {
  organizationOnboardingProfileQuery,
  saveOrganizationOnboardingStepMutation,
} from '../organizationOnboarding.graphql';

const tenantId = 'tenant-1';
const TenantWrapper = ({ children }: PropsWithChildren) => (
  <currentTenantContext.Provider value={{ data: tenantFactory({ id: tenantId }) }}>
    {children}
  </currentTenantContext.Provider>
);
const LocationProbe = () => <span data-testid="location">{useLocation().pathname}</span>;

const profile = {
  __typename: 'OrganizationOnboardingProfileType' as const,
  respondentRole: 'OWNER_MANAGEMENT',
  customerType: 'B2B',
  revenueModels: ['PROJECT'],
  costDrivers: ['MATERIALS'],
  pricing: 'FIXED',
  mainGoal: 'PRICING',
  currentStep: 6,
  isRequired: false,
  ksefStatus: 'not_connected',
  completedAt: null,
};

const profileMock = (currentStep = 6, ksefDemoConnected = false, isRequired = false) =>
  composeMockedQueryResult(organizationOnboardingProfileQuery, {
    variables: { tenantId },
    data: {
      organizationOnboardingProfile: {
        ...profile,
        currentStep,
        isRequired,
        ksefStatus: ksefDemoConnected ? 'demo' : 'not_connected',
      },
    },
  });

describe('OrganizationOnboarding', () => {
  afterEach(() => sessionStorage.clear());

  it('goes back from Customers to company details and restores an unfinished answer', async () => {
    render(
      <>
        <OrganizationOnboarding />
        <LocationProbe />
      </>,
      {
        TenantWrapper,
        routerProps: { initialEntries: ['/en/tenant-1/tenant/onboarding'] },
        apolloMocks: (mocks) => [...mocks, profileMock(2)],
      }
    );

    expect(await screen.findByText('Who usually pays you?')).toBeInTheDocument();
    const progress = screen.getByRole('list', { name: 'Onboarding steps' });
    expect(within(progress).getAllByRole('listitem')).toHaveLength(8);
    expect(within(progress).getByText('Customers').closest('li')).toHaveAttribute('aria-current', 'step');
    await userEvent.click(screen.getByRole('button', { name: 'Mostly consumers (B2C)' }));
    await userEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByTestId('location')).toHaveTextContent('/en/tenant-1/tenant/onboarding');
    expect(screen.getByText('Company details').closest('li')).toHaveAttribute('aria-current', 'step');
    await userEvent.click(screen.getByRole('button', { name: /3\. Customers/i }));
    expect(await screen.findByText('Who usually pays you?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mostly consumers (B2C)' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('goes back from Revenue to Customers without clearing the saved answer', async () => {
    render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [...mocks, profileMock(3)],
    });
    expect(await screen.findByText('What do customers pay you for?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByText('Who usually pays you?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mostly businesses (B2B)' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('resumes at the saved step and requires exactly 40 characters for KSeF', async () => {
    const token = 'x'.repeat(40);
    const saveMock = composeMockedQueryResult(saveOrganizationOnboardingStepMutation, {
      variables: { tenantId, step: 6, ksefToken: token },
      data: { saveOrganizationOnboardingStep: { profile: { ...profile, currentStep: 7, ksefStatus: 'demo' } } },
    });
    render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [...mocks, profileMock(), saveMock, profileMock(7, true)],
    });

    expect(await screen.findByRole('heading', { name: 'KSeF' })).toBeInTheDocument();
    const next = screen.getByRole('button', { name: /next/i });
    expect(next).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/demo token/i), token.slice(0, 39));
    expect(next).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/demo token/i), token.slice(39));
    expect(next).toBeEnabled();
    await userEvent.click(next);
    expect(await screen.findByText('Your business profile')).toBeInTheDocument();
    expect(saveMock.result).toHaveBeenCalled();
    expect(screen.queryByText(token)).not.toBeInTheDocument();
  });

  it('loads the saved revenue answer after a reload', async () => {
    render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [...mocks, profileMock(3)],
    });
    expect(await screen.findByText('What do customers pay you for?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Project / assignment' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('disables additional revenue and cost choices at their limits', async () => {
    const revenueAtLimit = profileMock(3);
    revenueAtLimit.result = jest.fn(() => ({
      data: {
        organizationOnboardingProfile: {
          ...profile,
          currentStep: 3,
          revenueModels: ['PROJECT', 'PRODUCT'],
        },
      },
    }));
    const view = render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [...mocks, revenueAtLimit],
    });
    expect(await screen.findByRole('button', { name: 'Time worked' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Project / assignment' })).toBeEnabled();
    view.unmount();

    const costsAtLimit = profileMock(4);
    costsAtLimit.result = jest.fn(() => ({
      data: {
        organizationOnboardingProfile: {
          ...profile,
          currentStep: 4,
          costDrivers: ['MATERIALS', 'EMPLOYEES', 'TRANSPORT'],
        },
      },
    }));
    render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [...mocks, costsAtLimit],
    });
    expect(await screen.findByRole('button', { name: 'Marketing / commissions' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Materials / goods' })).toBeEnabled();
  });

  it('shows the organization-created toast only after confirming the summary', async () => {
    const completedTenant = tenantFactory({ id: tenantId, onboardingRequired: true, onboardingCompleted: true });
    const completedUser = currentUserFactory({ tenants: [completedTenant] });
    const completeMock = composeMockedQueryResult(saveOrganizationOnboardingStepMutation, {
      variables: { tenantId, step: 7 },
      data: {
        saveOrganizationOnboardingStep: {
          profile: {
            ...profile,
            currentStep: 7,
            isRequired: true,
            ksefStatus: 'demo',
            completedAt: '2026-10-01T10:00:00Z',
          },
        },
      },
    });
    render(<OrganizationOnboarding />, {
      TenantWrapper,
      routerProps: {
        initialEntries: ['/en/tenant-1/tenant/onboarding'],
      },
      apolloMocks: (mocks) => [
        ...mocks,
        profileMock(7, true, true),
        completeMock,
        profileMock(7, true, true),
        fillCommonQueryWithUser(completedUser),
      ],
    });

    expect(await screen.findByText('Your business profile')).toBeInTheDocument();
    expect(screen.queryByText('Organization added successfully!')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Confirm profile' }));
    expect(await screen.findByText('Organization added successfully!')).toBeInTheDocument();
    expect(completeMock.result).toHaveBeenCalled();
  });

  it('completes the persisted flow from Customers through Summary', async () => {
    const token = 'k'.repeat(40);
    const requiredProfile = (currentStep: number, ksefStatus = 'not_connected', completedAt: string | null = null) => ({
      ...profile,
      currentStep,
      isRequired: true,
      ksefStatus,
      completedAt,
    });
    const saveMock = (
      step: number,
      variables: Record<string, unknown>,
      nextProfile: ReturnType<typeof requiredProfile>
    ) =>
      composeMockedQueryResult(saveOrganizationOnboardingStepMutation, {
        variables: { tenantId, step, ...variables },
        data: { saveOrganizationOnboardingStep: { profile: nextProfile } },
      });
    const queryMock = (nextProfile: ReturnType<typeof requiredProfile>) =>
      composeMockedQueryResult(organizationOnboardingProfileQuery, {
        variables: { tenantId },
        data: { organizationOnboardingProfile: nextProfile },
      });
    const completedTenant = tenantFactory({ id: tenantId, onboardingRequired: true, onboardingCompleted: true });
    const completedUser = currentUserFactory({ tenants: [completedTenant] });

    render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [
        ...mocks,
        queryMock(requiredProfile(2)),
        saveMock(2, { respondentRole: 'OWNER_MANAGEMENT', customerType: 'B2B' }, requiredProfile(3)),
        queryMock(requiredProfile(3)),
        saveMock(3, { revenueModels: ['PROJECT'] }, requiredProfile(4)),
        queryMock(requiredProfile(4)),
        saveMock(4, { costDrivers: ['MATERIALS'] }, requiredProfile(5)),
        queryMock(requiredProfile(5)),
        saveMock(5, { pricing: 'FIXED', mainGoal: 'PRICING' }, requiredProfile(6)),
        queryMock(requiredProfile(6)),
        saveMock(6, { ksefToken: token }, requiredProfile(7, 'demo')),
        queryMock(requiredProfile(7, 'demo')),
        saveMock(7, {}, requiredProfile(7, 'demo', '2026-10-02T08:00:00Z')),
        queryMock(requiredProfile(7, 'demo', '2026-10-02T08:00:00Z')),
        fillCommonQueryWithUser(completedUser),
      ],
    });

    expect(await screen.findByText('Who usually pays you?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('What do customers pay you for?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Which costs grow with your sales?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('How do you make key decisions?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('heading', { name: 'KSeF' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/demo token/i), token);
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Your business profile')).toBeInTheDocument();
    expect(screen.getByText('Owner / management')).toBeInTheDocument();
    expect(screen.queryByText(token)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Confirm profile' }));
    expect(await screen.findByText('Organization added successfully!')).toBeInTheDocument();
  });
});
