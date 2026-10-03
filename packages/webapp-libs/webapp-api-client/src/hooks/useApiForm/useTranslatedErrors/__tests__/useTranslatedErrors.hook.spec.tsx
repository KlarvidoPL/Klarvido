import { renderHook as renderPlainHook } from '@testing-library/react';

import { renderHook } from '../../../../tests/utils/rendering';
import { ErrorMessages } from '../../useApiForm.types';
import { useTranslatedErrors } from '../useTranslatedErrors.hook';

describe('useTranslatedErrors: Hook', () => {
  const render = (args?: ErrorMessages) => renderHook(() => useTranslatedErrors(args));

  describe('provided with custom messages', () => {
    const customMessages = { email: { CUSTOM_ERROR: 'custom error message' } };

    it('should return default translation if exists', async () => {
      const { result, waitForApolloMocks } = render(customMessages);
      await waitForApolloMocks();
      expect(result.current.translateErrorMessage('email', { code: 'CUSTOM_ERROR' })).toBe('custom error message');
    });

    it('should return input if no translation exists', async () => {
      const { result, waitForApolloMocks } = render(customMessages);
      await waitForApolloMocks();
      expect(result.current.translateErrorMessage('email', { code: 'NON_EXISTING_ERROR' })).toBe('NON_EXISTING_ERROR');
    });
  });
});

it('uses the latest localized messages and a localized fallback for unknown validation codes', () => {
  const { result, rerender } = renderPlainHook(({ messages }) => useTranslatedErrors(messages), {
    initialProps: { messages: { nip: { too_long: 'Too long', default: 'Check this value' } } },
  });
  rerender({ messages: { nip: { too_long: 'Za długie', default: 'Sprawdź tę wartość' } } });
  expect(result.current.translateErrorMessage('nip', { code: 'too_long', message: 'English backend error' })).toBe(
    'Za długie'
  );
  expect(result.current.translateErrorMessage('nip', { code: 'unknown', message: 'English backend error' })).toBe(
    'Sprawdź tę wartość'
  );
});
