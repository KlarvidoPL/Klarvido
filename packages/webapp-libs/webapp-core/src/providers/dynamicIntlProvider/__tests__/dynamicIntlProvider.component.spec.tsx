import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, screen } from '@testing-library/react';
import { ReactNode } from 'react';
import { FormattedMessage } from 'react-intl';

import { Locale } from '../../../config/i18n';
import { render } from '../../../tests/utils/rendering';
import { DynamicIntlProvider } from '../dynamicIntlProvider.component';

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

const createWrapper = (locale: Locale = Locale.ENGLISH) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <DynamicIntlProvider locale={locale}>{children}</DynamicIntlProvider>
    </QueryClientProvider>
  );
};

describe('DynamicIntlProvider', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    // Default: return 404 to use bundled translations
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
    });
  });

  it('should render children with bundled translations as fallback', async () => {
    const TestComponent = () => <FormattedMessage id="NonExistent / Key" defaultMessage="Default Test Message" />;

    const { container } = render(<TestComponent />, {
      wrapper: createWrapper(),
    });

    // Should render the default message since there's no translation
    expect(container).toHaveTextContent('Default Test Message');
  });

  it('should use remote translations when available', async () => {
    const remoteTranslations = {
      'Test / Key': 'Remote Test Message',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(remoteTranslations),
    });

    const TestComponent = () => <FormattedMessage id="Test / Key" defaultMessage="Default Test Message" />;

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    // Force enable remote translations for this test
    const originalEnv = process.env.VITE_USE_REMOTE_TRANSLATIONS;
    process.env.VITE_USE_REMOTE_TRANSLATIONS = 'true';

    render(
      <QueryClientProvider client={queryClient}>
        <DynamicIntlProvider locale={Locale.ENGLISH} translationsBaseUrl="https://test.com">
          <TestComponent />
        </DynamicIntlProvider>
      </QueryClientProvider>
    );

    // Restore env
    process.env.VITE_USE_REMOTE_TRANSLATIONS = originalEnv;
  });

  it('should support different locales', () => {
    const TestComponent = () => <FormattedMessage id="Test / Key" defaultMessage="Hello" />;

    const { container } = render(<TestComponent />, {
      wrapper: createWrapper(Locale.POLISH),
    });

    // Should render with Polish locale
    expect(container).toBeTruthy();
  });

  it('should handle missing translations gracefully', () => {
    const TestComponent = () => <FormattedMessage id="Unknown / Key" defaultMessage="Fallback Message" />;

    const { container } = render(<TestComponent />, {
      wrapper: createWrapper(),
    });

    // Should render the fallback message
    expect(container).toHaveTextContent('Fallback Message');
  });
});

describe('DynamicIntlProvider: localized validation fallback', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ ok: false, status: 503 });
  });

  it.each([
    [Locale.POLISH, 'Organizacja z tym NIP-em już istnieje na Twoim koncie.'],
    [Locale.GERMAN, 'Eine Organisation mit dieser NIP existiert bereits in Ihrem Konto.'],
    [Locale.FRENCH, 'Une organisation avec ce NIP existe déjà dans votre compte.'],
    [Locale.SPANISH, 'Ya existe una organización con este NIP en tu cuenta.'],
    [Locale.CHINESE, '你的账户中已存在使用此 NIP 的组织。'],
    [Locale.HINDI, 'इस NIP वाला संगठन आपके खाते में पहले से मौजूद है।'],
    [Locale.ARABIC, 'توجد بالفعل مؤسسة بهذا الرقم NIP في حسابك.'],
  ])('keeps warnings in %s when the API is unavailable', async (locale, expected) => {
    render(
      <DynamicIntlProvider locale={locale as Locale}>
        <FormattedMessage
          id="Onboarding / Duplicate NIP"
          defaultMessage="An organization with this NIP already exists in your account."
        />
      </DynamicIntlProvider>
    );
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });

  it('keeps the Polish translation when the API supplies an untranslated English default', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          'Onboarding / Duplicate NIP': 'An organization with this NIP already exists in your account.',
          'Onboarding / Save failed': 'Could not save this step. Please try again.',
        }),
    });
    render(
      <DynamicIntlProvider locale={Locale.POLISH}>
        <FormattedMessage id="Onboarding / Duplicate NIP" />
        <FormattedMessage id="Onboarding / Save failed" />
      </DynamicIntlProvider>
    );
    expect(await screen.findByText(/Organizacja z tym NIP-em już istnieje na Twoim koncie/)).toBeInTheDocument();
    expect(await screen.findByText(/Nie udało się zapisać tego kroku/)).toBeInTheDocument();
    expect(screen.queryByText(/An organization with this NIP/)).not.toBeInTheDocument();
  });
});
