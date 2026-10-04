import type { IntlShape } from 'react-intl';

// The connection test runs in the backend and returns English text. These messages translate it in the UI.
// Placeholders such as {status} match the variable parts of the backend text.
type TextTemplate = { id: string; template: string; regex: RegExp; names: string[] };

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const compileTemplate = (id: string, template: string): TextTemplate => {
  const names: string[] = [];
  const pattern = template
    .split(/(\{\w+\})/)
    .map((part) => {
      const match = part.match(/^\{(\w+)\}$/);
      if (match) {
        names.push(match[1]);
        return '(.+)';
      }
      return escapeRegExp(part);
    })
    .join('');
  return { id, template, regex: new RegExp(`^${pattern}$`), names };
};

const TEXT_TEMPLATES: TextTemplate[] = [
  compileTemplate('SSO Test / IdP Entity ID', 'IdP Entity ID'),
  compileTemplate('SSO Test / Identity Provider Entity ID is configured', 'Identity Provider Entity ID is configured'),
  compileTemplate(
    'SSO Test / Identity Provider Entity ID is not configured',
    'Identity Provider Entity ID is not configured'
  ),
  compileTemplate('SSO Test / SSO URL Format', 'SSO URL Format'),
  compileTemplate('SSO Test / Single Sign-On URL is configured', 'Single Sign-On URL is configured'),
  compileTemplate('SSO Test / Single Sign-On URL is not configured', 'Single Sign-On URL is not configured'),
  compileTemplate('SSO Test / SSO URL Reachable', 'SSO URL Reachable'),
  compileTemplate('SSO Test / SSO endpoint is reachable (HTTP status)', 'SSO endpoint is reachable (HTTP {status})'),
  compileTemplate(
    'SSO Test / SSO endpoint exists (returned 405 - expected for SAML endpoints)',
    'SSO endpoint exists (returned 405 - expected for SAML endpoints)'
  ),
  compileTemplate('SSO Test / SSO endpoint returned HTTP status', 'SSO endpoint returned HTTP {status}'),
  compileTemplate(
    'SSO Test / The endpoint might still work for SAML requests',
    'The endpoint might still work for SAML requests'
  ),
  compileTemplate(
    'SSO Test / Connection timed out when reaching SSO endpoint',
    'Connection timed out when reaching SSO endpoint'
  ),
  compileTemplate(
    'SSO Test / The IdP might be behind a firewall or slow to respond',
    'The IdP might be behind a firewall or slow to respond'
  ),
  compileTemplate(
    'SSO Test / SSL/TLS error when connecting to SSO endpoint',
    'SSL/TLS error when connecting to SSO endpoint'
  ),
  compileTemplate('SSO Test / Failed to connect to SSO endpoint', 'Failed to connect to SSO endpoint'),
  compileTemplate('SSO Test / IdP Certificate', 'IdP Certificate'),
  compileTemplate('SSO Test / Certificate expired days days ago', 'Certificate expired {days} days ago'),
  compileTemplate('SSO Test / Certificate expires in days days', 'Certificate expires in {days} days'),
  compileTemplate('SSO Test / Consider renewing the certificate soon', 'Consider renewing the certificate soon'),
  compileTemplate(
    'SSO Test / Certificate is valid (expires in days days)',
    'Certificate is valid (expires in {days} days)'
  ),
  compileTemplate('SSO Test / Failed to parse certificate', 'Failed to parse certificate'),
  compileTemplate(
    'SSO Test / Ensure the certificate is in valid PEM or base64 format',
    'Ensure the certificate is in valid PEM or base64 format'
  ),
  compileTemplate('SSO Test / IdP certificate is not configured', 'IdP certificate is not configured'),
  compileTemplate(
    'SSO Test / Certificate is recommended for signature validation',
    'Certificate is recommended for signature validation'
  ),
  compileTemplate('SSO Test / SP Configuration', 'SP Configuration'),
  compileTemplate(
    'SSO Test / Service Provider URLs are using localhost - external IdPs cannot reach these URLs',
    'Service Provider URLs are using localhost - external IdPs cannot reach these URLs'
  ),
  compileTemplate('SSO Test / Service Provider URLs are configured', 'Service Provider URLs are configured'),
  compileTemplate(
    'SSO Test / Service Provider configuration may be incomplete',
    'Service Provider configuration may be incomplete'
  ),
  compileTemplate('SSO Test / SAML Request Generation', 'SAML Request Generation'),
  compileTemplate(
    'SSO Test / SAML AuthnRequest can be generated successfully',
    'SAML AuthnRequest can be generated successfully'
  ),
  compileTemplate('SSO Test / Failed to generate SAML AuthnRequest', 'Failed to generate SAML AuthnRequest'),
  compileTemplate('SSO Test / OIDC Issuer', 'OIDC Issuer'),
  compileTemplate('SSO Test / Issuer URL is configured', 'Issuer URL is configured'),
  compileTemplate('SSO Test / Issuer URL is not configured', 'Issuer URL is not configured'),
  compileTemplate('SSO Test / OIDC Discovery', 'OIDC Discovery'),
  compileTemplate(
    'SSO Test / OpenID Connect discovery endpoint is accessible',
    'OpenID Connect discovery endpoint is accessible'
  ),
  compileTemplate('SSO Test / Discovery endpoint returned invalid JSON', 'Discovery endpoint returned invalid JSON'),
  compileTemplate('SSO Test / Discovery endpoint returned HTTP status', 'Discovery endpoint returned HTTP {status}'),
  compileTemplate(
    'SSO Test / Some IdPs may not support automatic discovery',
    'Some IdPs may not support automatic discovery'
  ),
  compileTemplate(
    'SSO Test / Connection timed out when fetching discovery document',
    'Connection timed out when fetching discovery document'
  ),
  compileTemplate('SSO Test / SSL/TLS error when connecting to issuer', 'SSL/TLS error when connecting to issuer'),
  compileTemplate('SSO Test / Could not fetch discovery document', 'Could not fetch discovery document'),
  compileTemplate(
    'SSO Test / Manual endpoint configuration may be required',
    'Manual endpoint configuration may be required'
  ),
  compileTemplate('SSO Test / Required Endpoints', 'Required Endpoints'),
  compileTemplate(
    'SSO Test / Missing endpoints in discovery: endpoints',
    'Missing endpoints in discovery: {endpoints}'
  ),
  compileTemplate('SSO Test / All required OIDC endpoints are present', 'All required OIDC endpoints are present'),
  compileTemplate('SSO Test / Client ID', 'Client ID'),
  compileTemplate('SSO Test / OAuth Client ID is configured', 'OAuth Client ID is configured'),
  compileTemplate('SSO Test / OAuth Client ID is not configured', 'OAuth Client ID is not configured'),
  compileTemplate('SSO Test / Client Secret', 'Client Secret'),
  compileTemplate('SSO Test / OAuth Client Secret is configured', 'OAuth Client Secret is configured'),
  compileTemplate('SSO Test / OAuth Client Secret is not configured', 'OAuth Client Secret is not configured'),
  compileTemplate('SSO Test / Callback URL', 'Callback URL'),
  compileTemplate(
    'SSO Test / Callback URL is using localhost - external IdPs cannot reach this URL',
    'Callback URL is using localhost - external IdPs cannot reach this URL'
  ),
  compileTemplate('SSO Test / OAuth callback URL is configured', 'OAuth callback URL is configured'),
  compileTemplate(
    'SSO Test / Callback URL configuration may be incomplete',
    'Callback URL configuration may be incomplete'
  ),
  compileTemplate('SSO Test / API URL', 'API URL'),
  compileTemplate('SSO Test / API URL is configured for production', 'API URL is configured for production'),
  compileTemplate(
    'SSO Test / API URL is set to localhost - SSO will not work with external identity providers',
    'API URL is set to localhost - SSO will not work with external identity providers'
  ),
  compileTemplate('SSO Test / API_URL environment variable is not set', 'API_URL environment variable is not set'),
  compileTemplate(
    'SSO Test / Set API_URL environment variable to your public API domain',
    'Set API_URL environment variable to your public API domain'
  ),
  compileTemplate(
    'SSO Test / Set the API_URL environment variable to your public API domain',
    'Set the API_URL environment variable to your public API domain'
  ),
  compileTemplate(
    'SSO Test / This will cause SSO redirects to fail. Set API_URL to your public API domain.',
    'This will cause SSO redirects to fail. Set API_URL to your public API domain.'
  ),
];

const DETAIL_LABEL_IDS: Record<string, string> = {
  value: 'SSO Test / Detail / value',
  hint: 'SSO Test / Detail / hint',
  error: 'SSO Test / Detail / error',
  expires: 'SSO Test / Detail / expires',
  discoveredEndpoints: 'SSO Test / Detail / discoveredEndpoints',
  entityId: 'SSO Test / Detail / entityId',
  requestIdFormat: 'SSO Test / Detail / requestIdFormat',
  acsUrl: 'SSO Test / Detail / acsUrl',
  authorization: 'SSO Test / Detail / authorization',
  token: 'SSO Test / Detail / token',
};

export const translateSsoTestText = (intl: IntlShape, text: string): string => {
  for (const entry of TEXT_TEMPLATES) {
    const match = entry.regex.exec(text);
    if (!match) continue;
    const values = Object.fromEntries(entry.names.map((name, index) => [name, match[index + 1]]));
    return intl.formatMessage({ id: entry.id, defaultMessage: entry.template }, values);
  }
  return text;
};

export const translateSsoDetailLabel = (intl: IntlShape, key: string): string => {
  const id = DETAIL_LABEL_IDS[key];
  return id ? intl.formatMessage({ id, defaultMessage: key }) : key;
};
