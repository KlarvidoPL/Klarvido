"""Pure redaction helpers shared by Django, Sentry and server logging."""
import json
import logging
import re
from urllib.parse import unquote

FILTERED = '[Filtered]'
SENSITIVE_KEY_FRAGMENTS = (
    'token',
    'password',
    'secret',
    'otp',
    'base32',
    'authorization',
    'cookie',
    'csrf',
    'credential',
)
SENSITIVE_KEYS = {'code', 'state', 'email', 'username', 'ipaddress', 'ip_address', 'remote_addr'}
BODY_KEYS = {
    'data',
    'body',
    'variables',
    'query_string',
    'query',
    'form',
    'payload',
    'response',
    'request_body',
    'headers',
    'sanitized_query',
    'statement',
    'user_agent',
}
AUTH_PATH = re.compile(r'(/auth/(?:reset-password/confirm|confirm)/)[^\s/?#]+/[^\s/?#]+', re.I)
INVITATION_PATH = re.compile(r'(/tenant-invitation/)[^\s/?#]+', re.I)
URL_QUERY = re.compile(r'(https?://[^\s?"<>]+|/[^\s?"<>]+)\?[^\s"<>]*', re.I)
CREDENTIAL_TEXT = re.compile(
    r'(?:password|token|secret|otp|base32|authorization|cookie|csrf|otpauth|code|state|email)\s*["\x27]?\s*[:=]|otpauth://|Bearer\s+\S+',
    re.I,
)


def _is_sensitive(key):
    normalized = re.sub(r'[^a-z0-9_]', '', str(key).lower())
    return normalized in SENSITIVE_KEYS or any(part in normalized for part in SENSITIVE_KEY_FRAGMENTS)


def scrub_string(value):
    decoded = unquote(value)
    if decoded.lstrip().startswith(('{', '[')):
        try:
            return json.dumps(_redact(json.loads(decoded)))
        except (ValueError, RecursionError):
            return FILTERED
    if CREDENTIAL_TEXT.search(decoded):
        return FILTERED
    decoded = AUTH_PATH.sub(r'\1[Filtered]/[Filtered]', decoded)
    decoded = INVITATION_PATH.sub(r'\1[Filtered]', decoded)
    decoded = re.sub(r'(https?://)[^/\s]+@', r'\1[Filtered]@', decoded, flags=re.I)
    return URL_QUERY.sub(r'\1?[Filtered]', decoded)


def _redact(value, depth=0):
    if depth > 20:
        return FILTERED
    if isinstance(value, dict):
        return {
            key: FILTERED if _is_sensitive(key) or str(key).lower() in BODY_KEYS else _redact(val, depth + 1)
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, depth + 1) for item in value]
    if isinstance(value, str):
        return scrub_string(value)
    return value


class CredentialSafeFormatter(logging.Formatter):
    def format(self, record):
        # Sanitize formatted exceptions as well as interpolated arguments; do not mutate shared LogRecords.
        return scrub_string(super().format(record))
