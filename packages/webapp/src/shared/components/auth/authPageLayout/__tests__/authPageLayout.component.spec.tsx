import { screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../../../tests/utils/rendering';
import { AuthPageLayout } from '../authPageLayout.component';

jest.mock('../../../backgrounds/topography', () => ({
  Topography: () => <div data-testid="topography-background" />,
}));

jest.mock('../../../backgrounds/prism', () => ({
  Prism: () => <div data-testid="prism-background" />,
}));

jest.mock('../../floatingThemeToggle', () => ({
  FloatingThemeToggle: () => <div data-testid="floating-theme-toggle" />,
}));

describe('AuthPageLayout: Component', () => {
  it('renders its content on the default topography background', async () => {
    render(
      <AuthPageLayout>
        <div>Authentication content</div>
      </AuthPageLayout>
    );

    expect(await screen.findByText('Authentication content')).toBeInTheDocument();
    expect(screen.getByTestId('topography-background')).toBeInTheDocument();
    expect(screen.queryByTestId('prism-background')).not.toBeInTheDocument();
  });

  it('switches to the prism background', async () => {
    render(
      <AuthPageLayout>
        <div>Authentication content</div>
      </AuthPageLayout>
    );

    await userEvent.click(await screen.findByRole('switch', { name: /switch authentication background/i }));

    expect(screen.getByTestId('prism-background')).toBeInTheDocument();
    expect(screen.queryByTestId('topography-background')).not.toBeInTheDocument();
  });
});
