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
  ksefStatus: 'not_connected',
  completedAt: null,
};

const profileMock = (currentStep = 6, ksefDemoConnected = false) =>
  composeMockedQueryResult(organizationOnboardingProfileQuery, {
    variables: { tenantId },
    data: {
      organizationOnboardingProfile: {
        ...profile,
        currentStep,
        ksefStatus: ksefDemoConnected ? 'demo' : 'not_connected',
      },
    },
  });

describe('OrganizationOnboarding', () => {
  afterEach(() => sessionStorage.clear());

  it('goes back from Customers to company settings and restores an unfinished answer', async () => {
    const view = render(
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
    expect(screen.getByTestId('location')).toHaveTextContent('/en/tenant-1/tenant/settings/general');
    view.unmount();

    render(<OrganizationOnboarding />, {
      TenantWrapper,
      apolloMocks: (mocks) => [...mocks, profileMock(2)],
    });
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
});
