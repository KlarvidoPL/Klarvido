import { screen, within } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { PropsWithChildren } from 'react';

import currentTenantContext from '../../../providers/currentTenantProvider/currentTenantProvider.context';
import { tenantFactory } from '../../../tests/factories/tenant';
import { render as baseRender } from '../../../tests/utils/rendering';
import { OnboardingProgress } from '../onboardingProgress.component';

const TenantWrapper = ({ children }: PropsWithChildren) => (
  <currentTenantContext.Provider value={{ data: tenantFactory({ id: 'tenant-1' }) }}>
    {children}
  </currentTenantContext.Provider>
);
const render: typeof baseRender = (ui, options = {}) => baseRender(ui, { ...options, TenantWrapper });

describe('OnboardingProgress', () => {
  it('shows all seven steps in one list and marks the current one', async () => {
    render(<OnboardingProgress step={3} />);

    const list = await screen.findByRole('list', { name: 'Onboarding steps' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(7);
    expect(items[2]).toHaveAttribute('aria-current', 'step');
    expect(items[0]).not.toHaveAttribute('aria-current');
  });

  it('lets the user return to completed steps and blocks steps beyond the furthest one reached', async () => {
    const onStepChange = jest.fn();
    render(<OnboardingProgress step={3} maxStep={4} onStepChange={onStepChange} />);

    const list = await screen.findByRole('list', { name: 'Onboarding steps' });
    await userEvent.click(within(list).getByRole('button', { name: 'Organization' }));
    expect(onStepChange).toHaveBeenCalledWith(1);

    expect(within(list).getByRole('button', { name: 'Customers' })).toBeDisabled();
    expect(within(list).getByRole('button', { name: 'Costs' })).toBeDisabled();
    expect(within(list).getByRole('button', { name: 'Revenue' })).toBeEnabled();
  });

  it('does not allow navigation when no change handler is given', async () => {
    render(<OnboardingProgress step={3} />);

    const list = await screen.findByRole('list', { name: 'Onboarding steps' });
    expect(within(list).getByRole('button', { name: 'Organization' })).toBeDisabled();
  });
});
