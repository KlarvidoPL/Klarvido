import { GraphQLFormattedError } from 'graphql';

/**
 * Apollo Client error type that includes both GraphQL and network errors.
 * Updated for Apollo Client 4 which may use different property names.
 */
export interface ApolloErrorLike extends Error {
  graphQLErrors?: ReadonlyArray<GraphQLFormattedError>;
  errors?: ReadonlyArray<GraphQLFormattedError>;
  result?: { errors?: ReadonlyArray<GraphQLFormattedError> };
  networkError?: Error | null;
  extraInfo?: any;
}

/**
 * Extracts GraphQL errors from Apollo Client error object.
 * Handles both Apollo Client 3.x (graphQLErrors) and 4.x (errors, result.errors) structures.
 *
 * @param error - The Apollo Client error object
 * @returns Array of GraphQL errors or undefined if none found
 */
export const extractGraphQLErrors = (
  error: ApolloErrorLike | any
): ReadonlyArray<GraphQLFormattedError> | undefined => {
  return error?.graphQLErrors || error?.errors || error?.result?.errors;
};

// Top-level messages that are never meant for display: some backend exceptions
// (common.graphql.exceptions.GraphQlValidationError/GraphQlMutationError) deliberately
// override __str__ to return just the exception class name, putting the real detail in
// `extensions` instead - and a plain DRF `PermissionDenied()` raised with no message falls
// back to this generic code. Never show these literally; treat them as "no detail available".
const RAW_BACKEND_ERROR_PLACEHOLDERS = new Set(['GraphQlValidationError', 'GraphQlMutationError', 'permission_denied']);

/**
 * Extracts the best available human-readable detail text from a GraphQL error response,
 * regardless of which of this backend's two error shapes produced it (see CLAUDE.md):
 * - Serializer-based mutations put object-level `validate()` errors under
 *   `extensions.non_field_errors[0].message`.
 * - Plain `graphene.Mutation` classes that raise `GraphQlValidationError`/`GraphQlMutationError`
 *   directly put the real text in `extensions` as a list (`[{ message, code }]`), while the
 *   top-level `message` is just the exception class name (see RAW_BACKEND_ERROR_PLACEHOLDERS).
 *
 * Returns undefined when no usable detail is found, so callers can fall back to a translated
 * generic message instead of ever showing raw/placeholder backend text.
 */
export const getGraphQLErrorDetail = (error: ApolloErrorLike | any): string | undefined => {
  const firstError = extractGraphQLErrors(error)?.[0];
  if (!firstError) {
    return undefined;
  }

  const extensions = firstError.extensions as any;
  if (Array.isArray(extensions) && typeof extensions[0]?.message === 'string') {
    return extensions[0].message;
  }
  if (extensions && typeof extensions === 'object') {
    const nonFieldErrors = extensions.non_field_errors;
    if (Array.isArray(nonFieldErrors) && typeof nonFieldErrors[0]?.message === 'string') {
      return nonFieldErrors[0].message;
    }
    if (typeof extensions.message === 'string') {
      return extensions.message;
    }
  }

  if (typeof firstError.message === 'string' && !RAW_BACKEND_ERROR_PLACEHOLDERS.has(firstError.message)) {
    return firstError.message;
  }

  return undefined;
};
