import type { IntlShape } from 'react-intl';

// Error codes come from apps/ksef/constants.py. Raw KSeF responses never reach the UI.
export const getKsefErrorMessage = (intl: IntlShape, errorCode: string | null | undefined): string => {
  switch (errorCode) {
    case 'INVALID_TOKEN':
      return intl.formatMessage({
        id: 'KSeF / Error invalid token',
        defaultMessage: 'KSeF did not accept this token. Check that it is copied correctly and was not revoked.',
      });
    case 'NO_PERMISSIONS':
      return intl.formatMessage({
        id: 'KSeF / Error no permissions',
        defaultMessage: 'This token has no permissions for the company. Generate a new token with invoice read access.',
      });
    case 'INVOICE_READ_MISSING':
      return intl.formatMessage({
        id: 'KSeF / Error invoice read missing',
        defaultMessage:
          'This token does not have invoice read permission (InvoiceRead). Generate a new token with this permission.',
      });
    case 'SERVICE_UNAVAILABLE':
      return intl.formatMessage({
        id: 'KSeF / Error service unavailable',
        defaultMessage: 'KSeF could not be reached right now. Try again later.',
      });
    case 'COUNTRY_NOT_SUPPORTED':
      return intl.formatMessage({
        id: 'KSeF / Error country not supported',
        defaultMessage: 'KSeF is only available for Polish organizations.',
      });
    case 'NIP_MISSING':
      return intl.formatMessage({
        id: 'KSeF / Error NIP missing',
        defaultMessage: 'Add the organization NIP before connecting KSeF.',
      });
    case 'TOKEN_EMPTY':
      return intl.formatMessage({
        id: 'KSeF / Error token empty',
        defaultMessage: 'Paste the KSeF token before saving.',
      });
    case 'ENCRYPTION_NOT_CONFIGURED':
      return intl.formatMessage({
        id: 'KSeF / Error encryption not configured',
        defaultMessage: 'The KSeF connection is not available on this server. Contact support.',
      });
    case 'DECRYPTION_FAILED':
      return intl.formatMessage({
        id: 'KSeF / Error decryption failed',
        defaultMessage: 'The saved token cannot be read. Replace it with a new token.',
      });
    default:
      return intl.formatMessage({
        id: 'KSeF / Error generic',
        defaultMessage: 'Something went wrong while connecting KSeF. Try again.',
      });
  }
};
