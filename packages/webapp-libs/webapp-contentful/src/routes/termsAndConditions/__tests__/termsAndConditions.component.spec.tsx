import { screen } from '@testing-library/react';

import { render } from '../../../tests/utils/rendering';
import { TermsAndConditions } from '../termsAndConditions.component';

describe('TermsAndConditions: Component', () => {
  const Component = () => <TermsAndConditions />;

  it('should render page title and description', async () => {
    render(<Component />);

    expect(await screen.findByRole('heading', { name: /terms and conditions/i })).toBeInTheDocument();
    expect(screen.getByText(/legal terms for using our service/i)).toBeInTheDocument();
  });

  it('should render the static terms and conditions content', async () => {
    render(<Component />);

    expect(await screen.findByText(/welcome to klarvido/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /intellectual property/i })).toBeInTheDocument();
  });
});
