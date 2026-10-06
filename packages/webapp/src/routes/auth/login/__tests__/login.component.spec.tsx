import { render, screen } from '@testing-library/react';
import { IntlProvider } from 'react-intl';
import { MemoryRouter } from 'react-router-dom';

import { Login } from '../login.component';

jest.mock('@sb/webapp-core/hooks', () => ({ useGenerateLocalePath: () => (path: string) => `/en/${path}` }));
jest.mock('@sb/webapp-core/config/env', () => ({
  ENV: { ENABLE_PASSWORD_LOGIN: true, ENABLE_SOCIAL_LOGIN: true, ENABLE_PASSKEYS: true, ENABLE_SSO: true },
}));
jest.mock('../../../../shared/components/auth/authLogo', () => ({ AuthLogo: () => null }));
jest.mock('../../../../shared/components/auth/floatingThemeToggle', () => ({ FloatingThemeToggle: () => null }));
jest.mock('../../../../shared/components/auth/loginForm', () => ({ LoginForm: () => <div>Email login</div> }));
jest.mock('../../../../shared/components/auth/passkeyLoginButton', () => ({
  PasskeyLoginButton: () => <div>Passkey login</div>,
}));
jest.mock('../../../../shared/components/auth/socialLoginButtons', () => ({
  SocialLoginButtons: () => <div>Google login</div>,
}));

it('renders supported login methods without SSO even with an old enablement flag', () => {
  render(
    <IntlProvider locale="en">
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    </IntlProvider>
  );
  expect(screen.getByText('Email login')).toBeInTheDocument();
  expect(screen.getByText('Passkey login')).toBeInTheDocument();
  expect(screen.getByText('Google login')).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /SSO/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /SSO/i })).not.toBeInTheDocument();
});
