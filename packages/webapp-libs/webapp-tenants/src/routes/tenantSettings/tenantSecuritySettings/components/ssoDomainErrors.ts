import { extractGraphQLErrors } from '@sb/webapp-api-client/api';
import type { IntlShape } from 'react-intl';

// Stable codes from apps/sso/services/domain_verification.py. Raw backend text never reaches the UI.
export const SSO_DOMAIN_ERROR_CODES = [
  'public_domain',
  'invalid_domain',
  'domain_taken',
  'dns_record_not_found',
  'domain_in_use',
  'no_domains',
  'domains_not_verified',
] as const;

export type SsoDomainErrorCode = (typeof SSO_DOMAIN_ERROR_CODES)[number];

const collectStrings = (value: unknown): string[] => {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(collectStrings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(collectStrings);
  return [];
};

// Finds a known domain error code in the message or extensions of a GraphQL error.
// extractGraphQLErrors reads both Apollo error shapes (graphQLErrors and Apollo 4's errors).
export const getSsoDomainErrorCode = (error: unknown): SsoDomainErrorCode | null => {
  const strings = (extractGraphQLErrors(error) ?? []).flatMap(collectStrings);
  const found = strings.find((value): value is SsoDomainErrorCode =>
    (SSO_DOMAIN_ERROR_CODES as readonly string[]).includes(value)
  );
  return found ?? null;
};

// Connection names the backend attached to a domain_in_use error (see DomainVerificationError.details)
export const getSsoDomainErrorConnections = (error: unknown): string[] => {
  const names = (extractGraphQLErrors(error) ?? []).flatMap((item) => {
    const connectionNames = (item as { extensions?: { connection_names?: unknown } })?.extensions?.connection_names;
    return Array.isArray(connectionNames)
      ? connectionNames.filter((name): name is string => typeof name === 'string')
      : [];
  });
  return names;
};

// Full translated explanation for a domain error, or null when the error is not a known domain error
export const getSsoDomainErrorDetail = (intl: IntlShape, error: unknown): string | null => {
  const code = getSsoDomainErrorCode(error);
  if (!code) return null;
  if (code === 'domain_in_use') {
    const connections = getSsoDomainErrorConnections(error);
    if (connections.length > 0) {
      return intl.formatMessage(
        {
          id: 'SSO / Error / domain_in_use with connections',
          defaultMessage: 'Remove this domain from these SSO connections before deleting it: {connections}.',
        },
        { connections: connections.join(', ') }
      );
    }
  }
  return getSsoDomainErrorMessage(intl, code);
};

export const getSsoDomainErrorMessage = (intl: IntlShape, code: SsoDomainErrorCode): string => {
  switch (code) {
    case 'public_domain':
      return intl.formatMessage({
        id: 'SSO / Error / public_domain',
        defaultMessage: 'Public email providers such as gmail.com cannot be claimed. Use your company domain.',
      });
    case 'invalid_domain':
      return intl.formatMessage({
        id: 'SSO / Error / invalid_domain',
        defaultMessage: 'Enter a domain name such as example.com.',
      });
    case 'domain_taken':
      return intl.formatMessage({
        id: 'SSO / Error / domain_taken',
        defaultMessage: 'This domain is already verified by another organization. Contact support if you own it.',
      });
    case 'dns_record_not_found':
      return intl.formatMessage({
        id: 'SSO / Error / dns_record_not_found',
        defaultMessage: 'The DNS record was not found yet. DNS changes can take up to an hour, then try again.',
      });
    case 'domain_in_use':
      return intl.formatMessage({
        id: 'SSO / Error / domain_in_use',
        defaultMessage: 'Remove this domain from every SSO connection before deleting it.',
      });
    case 'no_domains':
      return intl.formatMessage({
        id: 'SSO / Error / no_domains',
        defaultMessage: 'Add at least one verified domain to the connection before activating it.',
      });
    case 'domains_not_verified':
      return intl.formatMessage({
        id: 'SSO / Error / domains_not_verified',
        defaultMessage: 'Verify every allowed domain of this connection before activating it.',
      });
  }
};

// Field errors from the connection form can be a domain error code; show the translated text instead
export const translateSsoDomainFieldError = (intl: IntlShape, message: string): string => {
  const code = (SSO_DOMAIN_ERROR_CODES as readonly string[]).find((value) => value === message);
  return code ? getSsoDomainErrorMessage(intl, code as SsoDomainErrorCode) : message;
};
