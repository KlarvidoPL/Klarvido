"""Bounded passkey requests, atomic abuse limits, and privacy-safe diagnostics."""

from io import BytesIO

import logging
import re
import time
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import APIException, ValidationError, ParseError
from rest_framework.parsers import JSONParser
from rest_framework.throttling import SimpleRateThrottle

from common.ratelimiting.config import get_rate_limit
from common.ratelimiting.constants import RateLimitCategory
from common.ratelimiting.utils import get_client_ip as _get_client_ip, rate_limit_ip
from .constants import SSOAuditEventType
from .models import SSOAuditLog, UserPasskey

logger = logging.getLogger(__name__)


class PasskeyJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        body = stream.read(131073)
        if len(body) > 131072:
            raise ParseError('Invalid passkey request')
        return super().parse(BytesIO(body), media_type=media_type, parser_context=parser_context)


def client_ip(request):
    """Delegates to the single trusted-proxy-aware resolver shared across the codebase (see
    common.ratelimiting.utils.get_client_ip); only trusts X-Forwarded-For through hops that
    match settings.TRUSTED_PROXIES."""
    return _get_client_ip(request)


def validate_request(serializer_class, request):
    if not isinstance(request.data, dict):
        raise ValidationError({'non_field_errors': ['Invalid passkey request']})
    serializer = serializer_class(data=request.data)
    if not serializer.is_valid():
        # Do not echo malformed credential/proof values or parser exceptions.
        raise ValidationError({'non_field_errors': ['Invalid passkey request']})
    return serializer.validated_data


def audit_failure(request, operation, reason='invalid_request'):
    user = getattr(request, '_user', None)
    user = user if user and user.is_authenticated else None
    SSOAuditLog.log_event(
        event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED,
        user=user,
        ip_address=client_ip(request),
        success=False,
        description='Passkey operation rejected',
        metadata={'operation': operation, 'reason': reason},
    )


class PasskeyIPThrottle(SimpleRateThrottle):
    """Redis atomic fixed-window counters, also applied to authenticated requests."""

    scope = 'passkey_ip'

    def get_rate(self):
        return get_rate_limit(RateLimitCategory.AUTH_PASSKEY)

    def identifier(self, request):
        return rate_limit_ip(request)

    def allow_request(self, request, view):
        identifier = self.identifier(request)
        if identifier is None:
            return True
        now = time.time()
        digest = salted_hmac('passkey-throttle', str(identifier)).hexdigest()
        key = f'{self.scope}:{digest}:{int(now // self.duration)}'
        self.remaining = self.duration - now % self.duration
        try:
            cache.add(key, 0, timeout=self.duration + 1)
            attempts = cache.incr(key)
        except Exception:
            logger.error('Passkey rate-limit storage unavailable')
            error = APIException('Authentication temporarily unavailable')
            error.status_code = 503
            raise error
        return attempts <= self.num_requests

    def wait(self):
        return self.remaining


class PasskeyAccountThrottle(PasskeyIPThrottle):
    scope = 'passkey_account'

    def identifier(self, request):
        # Public login may switch accounts even when the browser is already
        # signed in. Limit the presented credential's owner, not that old session.
        if isinstance(request.data, dict):
            identifier = request.data.get('credentialId')
            if isinstance(identifier, str) and len(identifier) <= 2048:
                owner = UserPasskey.objects.filter(credential_id=identifier).values_list('user_id', flat=True).first()
                if owner is not None:
                    return owner
        return request.user.pk if request.user.is_authenticated else None


def validate_configuration():
    """Reject unsafe deployed passkey settings at application startup."""
    local = settings.DEBUG and getattr(settings, 'ENVIRONMENT_NAME', '') == 'local'
    if getattr(settings, 'WEBAUTHN_ALLOW_ORIGIN_MISMATCH', False) and not local:
        raise ImproperlyConfigured('WebAuthn origin mismatch override is only allowed in local development')
    deployed = not settings.DEBUG or getattr(settings, 'ENVIRONMENT_NAME', '') not in {'', 'local', 'test', 'testing'}
    origin = settings.WEB_APP_URL
    try:
        parsed = urlsplit(origin)
    except (ValueError, TypeError):
        raise ImproperlyConfigured('WEB_APP_URL must be a valid origin')
    if (
        parsed.scheme not in {'http', 'https'}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
        or origin != f'{parsed.scheme}://{parsed.netloc}'
        or parsed.hostname != parsed.hostname.lower()
        or parsed.netloc != parsed.netloc.lower()
        or (deployed and parsed.scheme != 'https')
    ):
        raise ImproperlyConfigured('WEB_APP_URL must be a canonical HTTPS origin in deployed environments')
    try:
        port = parsed.port
    except ValueError:
        raise ImproperlyConfigured('WEB_APP_URL has an invalid port')
    if (parsed.scheme, port) in {('https', 443), ('http', 80)}:
        raise ImproperlyConfigured('WEB_APP_URL must omit its default port')
    if deployed and not settings.COOKIE_SECURE:
        raise ImproperlyConfigured('Deployed authentication cookies must be secure')
    try:
        canonical_host = parsed.hostname.encode('idna').decode('ascii')
    except UnicodeError:
        raise ImproperlyConfigured('WEB_APP_URL has an invalid hostname')
    if canonical_host != parsed.hostname:
        raise ImproperlyConfigured('WEB_APP_URL must use its canonical ASCII hostname')
    if deployed and (
        '.' not in canonical_host
        or any(
            re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) is None for label in canonical_host.split('.')
        )
    ):
        raise ImproperlyConfigured('Deployed WEB_APP_URL must use a valid DNS hostname')
    try:
        throttle = PasskeyIPThrottle()
        if not throttle.num_requests or throttle.num_requests < 1 or not throttle.duration:
            raise ValueError('Disabled rate')
    except (TypeError, ValueError, KeyError):
        raise ImproperlyConfigured('auth.passkey must have a positive, valid rate limit')
    for extra in getattr(settings, 'WEBAUTHN_ALLOWED_ORIGINS', []):
        if extra != origin:
            raise ImproperlyConfigured('Passkeys accept only the configured frontend origin and RP hostname')
    if settings.PASSKEY_MAX_CHALLENGES < 1 or settings.PASSKEY_MAX_USER_CHALLENGES < 1:
        raise ImproperlyConfigured('Passkey challenge limits must be positive')
    if deployed and 'redis' not in settings.CACHES['default']['BACKEND'].lower():
        raise ImproperlyConfigured('Deployed passkey throttling requires a shared Redis cache')
    if deployed and not getattr(settings, 'TRUSTED_PROXIES', None):
        # Not fatal: without it, every client behind the deployment's reverse proxy shares one
        # IP-based rate-limit bucket (and one passkey throttle bucket) instead of being
        # distinguished - a real availability risk, but not a bypass, so this only warns.
        logger.warning(
            'TRUSTED_PROXIES is empty in a deployed environment - IP-based rate limiting and '
            'passkey throttling will bucket every client behind the reverse proxy together.'
        )
