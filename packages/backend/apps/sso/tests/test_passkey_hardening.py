"""F14: bounded inputs, private errors/history, atomic limits and secure configuration."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connections

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from apps.sso.exceptions import PasskeyChallengeCapacityExceeded
from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, WebAuthnChallenge, PasskeyManagementGrant
from apps.sso.passkey_security import PasskeyIPThrottle, client_ip, validate_configuration
from apps.sso.tasks import cleanup_passkey_challenges
from apps.sso.tests.factories import UserPasskeyFactory
from common.ratelimiting.config import clear_config_cache

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolate_limits():
    cache.clear()
    clear_config_cache()
    yield
    clear_config_cache()
    cache.clear()


def browser(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    proof = client.get('/api/auth/csrf/').json()['csrfToken']
    client.credentials(HTTP_X_CSRFTOKEN=proof)
    return client


@pytest.mark.parametrize(
    'payload',
    [
        [],
        'private-input',
        123,
        None,
        {},
        {
            'challenge': 'fake',
            'credentialId': {'private': 'input'},
            'authenticatorData': 'test',
            'clientDataJSON': 'test',
            'signature': 'test',
        },
        {
            'challenge': 'fake',
            'credentialId': 123,
            'authenticatorData': 'test',
            'clientDataJSON': 'test',
            'signature': 'test',
        },
        {
            'challenge': 'fake',
            'credentialId': 'a' * 2049,
            'authenticatorData': 'test',
            'clientDataJSON': 'test',
            'signature': 'test',
        },
    ],
)
def test_malformed_assertions_return_safe_errors_without_side_effects(payload):
    response = browser().post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 400
    assert b'private-input' not in response.content
    assert not WebAuthnChallenge.objects.exists()
    event = SSOAuditLog.objects.get(event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED)
    assert not event.success
    assert event.metadata == {'operation': 'authentication', 'reason': 'invalid_request'}


def test_malformed_json_does_not_expose_parser_details():
    response = browser().post(
        '/api/sso/passkeys/authenticate/verify', '{"private-input":', content_type='application/json'
    )
    assert response.status_code == 400
    assert b'private-input' not in response.content
    assert b'line ' not in response.content


def test_request_size_is_bounded_before_challenge_creation():
    response = browser().post('/api/sso/passkeys/authenticate/options', {'extra': 'x' * 131072}, format='json')
    assert response.status_code == 400
    assert not WebAuthnChallenge.objects.exists()


@pytest.mark.parametrize('authenticated', [False, True])
def test_central_limit_applies_to_anonymous_and_authenticated_clients(settings, user, authenticated, freezer):
    freezer.move_to('2026-10-08 12:00:05')
    settings.RATE_LIMITS = {'auth.passkey': {'rate': '2/min'}}
    client = browser(user if authenticated else None)
    url = '/api/sso/passkeys/authenticate/options'
    assert client.post(url, {}, format='json').status_code == 200
    assert client.post(url, {}, format='json').status_code == 200
    response = client.post(url, {}, format='json')
    assert response.status_code == 429
    assert 'Retry-After' in response
    assert WebAuthnChallenge.objects.count() == 2


@pytest.mark.parametrize('authenticated', [False, True])
def test_known_account_limit_spans_multiple_ips(settings, user, user_factory, freezer, authenticated):
    freezer.move_to('2026-10-08 12:00:05')
    settings.RATE_LIMITS = {'auth.passkey': {'rate': '2/min'}}
    credential = UserPasskeyFactory(user=user)
    payload = {'credentialId': credential.credential_id}
    attacker = user_factory() if authenticated else None
    for number in range(3):
        response = browser(attacker).post(
            '/api/sso/passkeys/authenticate/verify', payload, format='json', REMOTE_ADDR=f'192.0.2.{number+1}'
        )
        assert response.status_code == (400 if number < 2 else 429)


def test_atomic_limit_cannot_be_exceeded_by_concurrent_workers(settings, freezer):
    freezer.move_to('2026-10-08 12:00:05')
    settings.RATE_LIMITS = {'auth.passkey': {'rate': '3/min'}}
    request = APIRequestFactory().get('/', REMOTE_ADDR='192.0.2.1')
    with ThreadPoolExecutor(max_workers=8) as pool:
        allowed = list(pool.map(lambda _: PasskeyIPThrottle().allow_request(request, None), range(20)))
    assert sum(allowed) == 3


def test_cache_failure_blocks_challenge_issuance():
    client = browser()
    with patch('apps.sso.passkey_security.cache.add', side_effect=RuntimeError('private redis detail')):
        response = client.post('/api/sso/passkeys/authenticate/options', {}, format='json')
    assert response.status_code == 503
    assert b'private redis detail' not in response.content
    assert not WebAuthnChallenge.objects.exists()


def test_forwarded_ip_requires_explicit_proxy_trust(settings):
    request = APIRequestFactory().get('/', REMOTE_ADDR='192.0.2.10', HTTP_X_FORWARDED_FOR='198.51.100.99, 203.0.113.20')
    settings.PASSKEY_TRUSTED_PROXY_COUNT = 0
    assert client_ip(request) == '192.0.2.10'
    settings.PASSKEY_TRUSTED_PROXY_COUNT = 1
    assert client_ip(request) == '203.0.113.20'
    settings.PASSKEY_TRUSTED_PROXY_COUNT = 2
    assert client_ip(request) == '198.51.100.99'
    request.META['HTTP_X_FORWARDED_FOR'] = 'malformed'
    settings.PASSKEY_TRUSTED_PROXY_COUNT = 1
    assert client_ip(request) is None


def test_challenge_capacity_is_bounded_and_expired_rows_are_reclaimed(settings):
    settings.PASSKEY_MAX_CHALLENGES = 2
    client = browser()
    url = '/api/sso/passkeys/authenticate/options'
    assert client.post(url, {}, format='json').status_code == 200
    assert client.post(url, {}, format='json').status_code == 200
    assert client.post(url, {}, format='json').status_code == 429
    WebAuthnChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert client.post(url, {}, format='json').status_code == 200
    assert WebAuthnChallenge.objects.count() == 1


def test_cleanup_removes_expired_challenges_and_keeps_live_ones():
    old = WebAuthnChallenge.create_challenge(ttl_seconds=-1)
    live = WebAuthnChallenge.create_challenge()
    # Issuance opportunistically cleans expired rows, so add another expired row directly.
    WebAuthnChallenge.objects.create(
        challenge='old', challenge_type='authentication', expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert cleanup_passkey_challenges() == 1
    assert not WebAuthnChallenge.objects.filter(pk=old.pk).exists()
    assert WebAuthnChallenge.objects.filter(pk=live.pk).exists()


@pytest.mark.parametrize(
    'invalid',
    [
        {'WEBAUTHN_ALLOW_ORIGIN_MISMATCH': True},
        {'WEB_APP_URL': 'http://app.example.com'},
        {'WEB_APP_URL': 'https://app.example.com/path'},
        {'WEB_APP_URL': 'https://user:secret@app.example.com'},
        {'WEB_APP_URL': 'https://APP.example.com'},
        {'WEB_APP_URL': 'https://app.example.com:443'},
        {'WEB_APP_URL': 'https://app.example.com:invalid'},
        {'WEB_APP_URL': 'https://localhost'},
        {'COOKIE_SECURE': False},
        {'RATE_LIMITS': {'auth.passkey': {'rate': '0/min'}}},
        {'WEBAUTHN_ALLOWED_ORIGINS': ['https://other.example.com']},
        {'PASSKEY_TRUSTED_PROXY_COUNT': -1},
        {'PASSKEY_MAX_CHALLENGES': 0},
        {'CACHES': {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}},
    ],
)
def test_unsafe_production_configuration_is_rejected(settings, invalid):
    settings.DEBUG = False
    settings.ENVIRONMENT_NAME = 'production'
    settings.WEB_APP_URL = 'https://app.example.com'
    settings.COOKIE_SECURE = True
    settings.WEBAUTHN_ALLOW_ORIGIN_MISMATCH = False
    for name, value in invalid.items():
        setattr(settings, name, value)
    with pytest.raises(ImproperlyConfigured):
        validate_configuration()


def test_secure_configuration_and_explicit_local_override_are_accepted(settings):
    settings.DEBUG = False
    settings.ENVIRONMENT_NAME = 'production'
    settings.WEB_APP_URL = 'https://app.example.com'
    settings.COOKIE_SECURE = True
    settings.WEBAUTHN_ALLOW_ORIGIN_MISMATCH = False
    validate_configuration()
    settings.DEBUG = True
    settings.ENVIRONMENT_NAME = 'local'
    settings.WEB_APP_URL = 'http://localhost:3000'
    settings.WEBAUTHN_ALLOW_ORIGIN_MISMATCH = True
    validate_configuration()


def test_personal_history_never_exposes_another_account_or_credentials(user, user_factory):
    SSOAuditLog.log_event(
        event_type=SSOAuditEventType.PASSKEY_REGISTERED,
        user=user,
        metadata={'credential': 'private-proof'},
        error_message='private-parser-detail',
    )
    SSOAuditLog.log_event(event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS, user=user_factory())
    response = browser(user).get('/api/sso/passkeys/history')
    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert len(response.data) == 1
    assert set(response.data[0]) == {'eventType', 'createdAt', 'success'}
    assert b'private' not in response.content
    assert browser().get('/api/sso/passkeys/history').status_code in (401, 403)


def test_expired_management_grants_are_cleaned_without_touching_live_ones(user):
    expired = PasskeyManagementGrant.objects.create(
        user=user, action='register', expires_at=timezone.now() - timedelta(seconds=1)
    )
    live = PasskeyManagementGrant.objects.create(
        user=user, action='register', expires_at=timezone.now() + timedelta(minutes=5)
    )
    cleanup_passkey_challenges()
    assert not PasskeyManagementGrant.objects.filter(pk=expired.pk).exists()
    assert PasskeyManagementGrant.objects.filter(pk=live.pk).exists()


def test_per_account_challenge_capacity(settings, user):
    settings.PASSKEY_MAX_USER_CHALLENGES = 1
    WebAuthnChallenge.create_challenge(user=user)
    with pytest.raises(PasskeyChallengeCapacityExceeded):
        WebAuthnChallenge.create_challenge(user=user)
    assert WebAuthnChallenge.objects.filter(user=user).count() == 1


@pytest.mark.django_db(transaction=True)
def test_challenge_capacity_is_exact_under_concurrent_issuance(settings):
    settings.PASSKEY_MAX_CHALLENGES = 1
    barrier = Barrier(2)

    def issue():
        try:
            barrier.wait(timeout=10)
            try:
                WebAuthnChallenge.create_challenge()
                return True
            except PasskeyChallengeCapacityExceeded:
                return False
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: issue(), range(2)))
    assert sum(attempts) == 1
    assert WebAuthnChallenge.objects.count() == 1
