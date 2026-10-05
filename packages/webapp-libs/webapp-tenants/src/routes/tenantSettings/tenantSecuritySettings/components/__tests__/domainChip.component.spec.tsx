import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../../tests/utils/rendering';
import { DomainChip, getDomainVerification } from '../domainChip';

describe('DomainChip', () => {
  it('shows a not-verified badge for a domain that is not verified', async () => {
    render(<DomainChip domain="ordigita.com" verified={false} onRemove={jest.fn()} />);

    expect(await screen.findByRole('img', { name: 'Not verified' })).toBeInTheDocument();
  });

  it('shows no badge while verification is unknown or when verified', async () => {
    const { unmount } = render(<DomainChip domain="ordigita.com" verified={null} onRemove={jest.fn()} />);
    expect(screen.queryByRole('img', { name: 'Not verified' })).not.toBeInTheDocument();
    unmount();

    render(<DomainChip domain="fciesielski.com" verified onRemove={jest.fn()} />);
    expect(screen.queryByRole('img', { name: 'Not verified' })).not.toBeInTheDocument();
  });

  it('calls onRemove when the remove button is clicked', async () => {
    const user = userEvent.setup();
    const onRemove = jest.fn();
    render(<DomainChip domain="ordigita.com" verified={false} onRemove={onRemove} />);

    await user.click(await screen.findByRole('button'));

    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('reports verification only after the domain list has loaded', () => {
    const domains = [{ domain: 'fciesielski.com', status: 'VERIFIED' }];

    expect(getDomainVerification(domains, true, 'fciesielski.com')).toBeNull();
    expect(getDomainVerification(domains, false, 'fciesielski.com')).toBe(true);
    expect(getDomainVerification(domains, false, 'ordigita.com')).toBe(false);
  });
});
