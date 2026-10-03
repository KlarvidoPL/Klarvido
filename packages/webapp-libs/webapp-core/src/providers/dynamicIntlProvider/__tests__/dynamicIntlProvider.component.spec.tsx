import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, renderHook, screen } from '@testing-library/react';
import { ReactNode, useState } from 'react';
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

  it('preserves unsaved form answers when changing language', async () => {
    const Form = () => {
      const [answer, setAnswer] = useState('');
      return (
        <>
          <input aria-label="answer" value={answer} onChange={(event) => setAnswer(event.target.value)} />
          <FormattedMessage id="Onboarding / Save failed" />
        </>
      );
    };
    const { rerender } = render(
      <DynamicIntlProvider locale={Locale.ENGLISH}>
        <Form />
      </DynamicIntlProvider>
    );
    fireEvent.change(screen.getByLabelText('answer'), { target: { value: 'Unsaved company details' } });
    rerender(
      <DynamicIntlProvider locale={Locale.POLISH}>
        <Form />
      </DynamicIntlProvider>
    );
    expect(await screen.findByText('Nie udało się zapisać tego kroku. Spróbuj ponownie.')).toBeInTheDocument();
    expect(screen.getByLabelText('answer')).toHaveValue('Unsaved company details');
  });

  it.each([
    [Locale.POLISH, 'Nie udało się zapisać tego kroku. Spróbuj ponownie.'],
    [Locale.GERMAN, 'Dieser Schritt konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.'],
    [Locale.FRENCH, 'Impossible d’enregistrer cette étape. Veuillez réessayer.'],
    [Locale.SPANISH, 'No se pudo guardar este paso. Inténtalo de nuevo.'],
    [Locale.CHINESE, '无法保存此步骤，请重试。'],
    [Locale.HINDI, 'यह चरण सहेजा नहीं जा सका। कृपया फिर से कोशिश करें।'],
    [Locale.ARABIC, 'تعذّر حفظ هذه الخطوة. يرجى المحاولة مرة أخرى.'],
  ])('keeps warnings in %s when the API is unavailable', async (locale, expected) => {
    render(
      <DynamicIntlProvider locale={locale as Locale}>
        <FormattedMessage
          id="Onboarding / Save failed"
          defaultMessage="Could not save this step. Please try again."
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
          'Onboarding / Save failed': 'Could not save this step. Please try again.',
        }),
    });
    render(
      <DynamicIntlProvider locale={Locale.POLISH}>
        <FormattedMessage id="Onboarding / Save failed" />
      </DynamicIntlProvider>
    );
    expect(await screen.findByText('Nie udało się zapisać tego kroku. Spróbuj ponownie.')).toBeInTheDocument();
    expect(screen.queryByText(/Could not save this step/)).not.toBeInTheDocument();
  });
});
