import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { PropsWithChildren } from 'react';

import { render } from '../../../tests/utils/rendering';
import { ChoiceGroup } from '../choiceGroup.component';

const TenantWrapper = ({ children }: PropsWithChildren) => <>{children}</>;

const options = [
  { value: 'alpha', label: 'Alpha' },
  { value: 'beta', label: 'Beta' },
  { value: 'gamma', label: 'Gamma' },
];

describe('ChoiceGroup', () => {
  it('marks only the selected tile as pressed and shows its check icon', async () => {
    render(<ChoiceGroup options={options} selected={['beta']} onChange={jest.fn()} />, { TenantWrapper });

    const beta = await screen.findByRole('button', { name: 'Beta' });
    expect(beta).toHaveAttribute('aria-pressed', 'true');
    expect(beta.querySelector('svg')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Alpha' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Alpha' }).querySelector('svg')).not.toBeInTheDocument();
  });

  it('replaces the answer in single-choice mode', async () => {
    const onChange = jest.fn();
    render(<ChoiceGroup options={options} selected={['beta']} onChange={onChange} />, { TenantWrapper });

    await userEvent.click(await screen.findByRole('button', { name: 'Gamma' }));
    expect(onChange).toHaveBeenCalledWith(['gamma']);
  });

  it('toggles answers and stops at the maximum in multi-choice mode', async () => {
    const onChange = jest.fn();
    render(<ChoiceGroup options={options} selected={['alpha', 'beta']} onChange={onChange} max={2} />, {
      TenantWrapper,
    });

    expect(await screen.findByRole('button', { name: 'Gamma' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Alpha' }));
    expect(onChange).toHaveBeenLastCalledWith(['beta']);
  });
});
