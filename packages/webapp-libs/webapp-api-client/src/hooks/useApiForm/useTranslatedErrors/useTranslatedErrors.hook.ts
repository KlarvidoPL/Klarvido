import { path } from 'ramda';
import { useCallback, useMemo } from 'react';
import { FieldValues, Path } from 'react-hook-form';

import { FieldError } from '../../../api/types';
import { ErrorMessages, FieldErrorMessages } from '../useApiForm.types';

export const useTranslatedErrors = <FormData extends FieldValues = FieldValues>(messages?: ErrorMessages<FormData>) => {
  const serializedMessages = JSON.stringify(messages);
  const customMessages = useMemo(
    () => (serializedMessages ? (JSON.parse(serializedMessages) as ErrorMessages<FormData>) : undefined),
    [serializedMessages]
  );

  const translateErrorMessage = useCallback(
    (field: Path<FormData> | 'nonFieldErrors', error?: FieldError) => {
      if (!error) {
        return '';
      }

      const fallbackMessage = error.message || error.code;
      if (!customMessages) {
        return fallbackMessage;
      }

      const msg = path<FieldErrorMessages>(field.split('.'), customMessages);
      return msg?.[error.code] ?? msg?.['default'] ?? fallbackMessage;
    },
    [customMessages]
  );
  return { translateErrorMessage };
};
