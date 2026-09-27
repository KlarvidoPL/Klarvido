import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { PrivacyPolicy } from '../privacyPolicy.component';

describe('PrivacyPolicy: Component', () => {
  const Component = () => <PrivacyPolicy />;

  it('should render page title and description', async () => {
    render(<Component />);

    expect(await screen.findByRole('heading', { name: /privacy policy/i })).toBeInTheDocument();
    expect(screen.getByText(/how we handle and protect your data/i)).toBeInTheDocument();
  });

  it('should render the static privacy policy content', async () => {
    render(<Component />);

    expect(await screen.findByText(/how klarvido collects, uses, discloses/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /your rights/i })).toBeInTheDocument();
  });
});
