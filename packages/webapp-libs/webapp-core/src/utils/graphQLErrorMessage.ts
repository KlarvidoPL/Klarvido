import { IntlShape } from 'react-intl';

/**
 * Translated catch-all shown instead of raw/unrecognized backend error text - e.g. a rare
 * race condition a specific error message isn't worth maintaining for, or a backend error
 * shape a caller doesn't otherwise recognize. Pair with `getGraphQLErrorDetail` from
 * `@sb/webapp-api-client/api` (which already filters out known placeholder strings like
 * "GraphQlValidationError") so recognized errors still get a specific, actionable message
 * and only genuinely unhandled ones fall back to this.
 */
export const getGenericErrorMessage = (intl: IntlShape): string =>
  intl.formatMessage({
    defaultMessage: 'Something went wrong. Please try again.',
    id: 'Common / Errors / Generic fallback',
  });
