"""Signed assertions must satisfy RP, user verification and credential ownership checks."""

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, SSOSession, UserPasskey, WebAuthnChallenge
from apps.sso.services.webauthn import WebAuthnService
from apps.sso.tests.factories import UserPasskeyFactory


pytestmark = pytest.mark.django_db


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


@pytest.fixture
def assertion(user):
    cache.clear()
    private_key = ec.generate_private_key(ec.SECP256R1())
    numbers = private_key.public_key().public_numbers()
    public_key = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})
    passkey = UserPasskeyFactory(user=user, public_key=encode(public_key))
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/auth/csrf/').json()['csrfToken']
    client.credentials(HTTP_X_CSRFTOKEN=token)

    def build(mode='identified', change=None, sign_count=1):
        options = client.post(
            '/api/sso/passkeys/authenticate/options',
            {'email': user.email, 'userVerification': 'discouraged'} if mode == 'identified' else {},
            format='json',
        )
        assert options.status_code == 200
        assert options.data['userVerification'] == 'required'
        challenge = WebAuthnChallenge.objects.get(challenge=options.data['challenge'])
        assert challenge.user_verification == 'required'
        client_data = {'type': 'webauthn.get', 'challenge': challenge.challenge, 'origin': settings.WEB_APP_URL}
        flags = 0x05
        rp_hash = hashlib.sha256(WebAuthnService().rp_id.encode()).digest()
        if change == 'rp-hash':
            rp_hash = b'\x00' * 32
        elif change == 'missing-up':
            flags = 0x04
        elif change in {'missing-uv', 'legacy-policy'}:
            flags = 0x01
        elif change == 'backup-flags':
            flags = 0x15
        elif change in {'origin', 'challenge', 'type'}:
            client_data[change] = 'invalid'
        elif change == 'cross-origin':
            client_data['crossOrigin'] = True
        auth_data = rp_hash + bytes([flags]) + sign_count.to_bytes(4, 'big')
        if change == 'short-auth-data':
            auth_data = auth_data[:10]
        elif change == 'trailing-auth-data':
            auth_data += b'\x00'
        client_bytes = json.dumps(client_data).encode()
        signature = private_key.sign(auth_data + hashlib.sha256(client_bytes).digest(), ec.ECDSA(hashes.SHA256()))
        payload = {
            'challenge': challenge.challenge,
            'credentialId': passkey.credential_id,
            'authenticatorData': encode(auth_data),
            'clientDataJSON': encode(client_bytes),
            'signature': encode(signature),
            'userHandle': WebAuthnService(user)._encode_user_id(user),
        }
        if change == 'wrong-handle':
            payload['userHandle'] = encode(b'not-the-owner')
        elif change == 'invalid-handle':
            payload['userHandle'] = '!!!'
        elif change == 'empty-handle':
            payload['userHandle'] = ''
        elif change == 'missing-handle':
            payload.pop('userHandle')
        elif change == 'legacy-policy':
            challenge.user_verification = 'preferred'
            challenge.save(update_fields=['user_verification'])
        return payload, challenge

    return client, passkey, build


@pytest.mark.parametrize('mode,omit_handle', [('identified', False), ('discoverable', False)])
@pytest.mark.parametrize('otp_enabled', [False, True])
def test_valid_assertion_can_login(user, assertion, mode, omit_handle, otp_enabled):
    user.otp_enabled = otp_enabled
    user.otp_verified = otp_enabled
    user.save(update_fields=['otp_enabled', 'otp_verified'])
    client, passkey, build = assertion
    payload, challenge = build(mode)
    if omit_handle:
        payload.pop('userHandle')
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 200
    assert response.data == {'success': True}
    assert settings.ACCESS_TOKEN_COOKIE in response.cookies
    assert settings.REFRESH_TOKEN_COOKIE in response.cookies
    assert AccessToken(response.cookies[settings.ACCESS_TOKEN_COOKIE].value)['auth_method'] == 'passkey'
    assert settings.OTP_AUTH_TOKEN_COOKIE not in response.cookies
    passkey.refresh_from_db()
    challenge.refresh_from_db()
    assert challenge.used_at is not None
    assert passkey.sign_count == 1
    assert passkey.use_count == 1


@pytest.mark.parametrize(
    'mode,change',
    [
        ('identified', 'rp-hash'),
        ('identified', 'missing-up'),
        ('identified', 'missing-uv'),
        ('identified', 'legacy-policy'),
        ('identified', 'backup-flags'),
        ('identified', 'origin'),
        ('identified', 'challenge'),
        ('identified', 'type'),
        ('identified', 'cross-origin'),
        ('identified', 'short-auth-data'),
        ('identified', 'trailing-auth-data'),
        ('identified', 'wrong-handle'),
        ('identified', 'invalid-handle'),
        ('identified', 'empty-handle'),
        ('discoverable', 'wrong-handle'),
        ('discoverable', 'invalid-handle'),
        ('discoverable', 'empty-handle'),
        ('discoverable', 'missing-handle'),
        ('identified', 'missing-handle'),
        ('identified', 'challenge-owner'),
    ],
)
def test_signed_invalid_assertion_cannot_issue_tokens_or_update_credential(user, user_factory, assertion, mode, change):
    client, passkey, build = assertion
    payload, challenge = build(mode, change)
    if change == 'challenge-owner':
        challenge.user = user_factory()
        challenge.save(update_fields=['user'])
    tokens_before = OutstandingToken.objects.count()
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 400
    assert 'access' not in response.data and 'refresh' not in response.data
    assert not any(
        name in response.cookies
        for name in (
            settings.ACCESS_TOKEN_COOKIE,
            settings.REFRESH_TOKEN_COOKIE,
            settings.SESSION_ID_COOKIE,
        )
    )
    assert OutstandingToken.objects.count() == tokens_before
    assert not SSOSession.objects.filter(user=user).exists()
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.sign_count == 0 and passkey.use_count == 0
    assert passkey.is_active
    assert not SSOAuditLog.objects.filter(user=user, event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS).exists()


def test_service_bound_to_another_user_rejects_credential(user_factory, assertion):
    _, _, build = assertion
    payload, _ = build()
    with pytest.raises(ValueError, match='Credential owner does not match user'):
        WebAuthnService(user_factory()).verify_authentication(
            challenge=payload['challenge'],
            credential_id=payload['credentialId'],
            authenticator_data=payload['authenticatorData'],
            client_data_json=payload['clientDataJSON'],
            signature=payload['signature'],
            user_handle=payload['userHandle'],
        )


def authenticate(payload):
    return WebAuthnService().verify_authentication(
        challenge=payload['challenge'],
        credential_id=payload['credentialId'],
        authenticator_data=payload['authenticatorData'],
        client_data_json=payload['clientDataJSON'],
        signature=payload['signature'],
        user_handle=payload.get('userHandle'),
        browser_binding=WebAuthnChallenge.objects.get(challenge=payload['challenge']).browser_binding,
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('same_challenge', [True, False])
def test_concurrent_assertions_are_serialized(assertion, same_challenge, settings):
    settings.WEBAUTHN_STRICT_SIGN_COUNT = True
    _, passkey, build = assertion
    first, challenge = build()
    second, other_challenge = (first, challenge) if same_challenge else build()
    barrier = Barrier(2)

    def attempt(payload):
        try:
            barrier.wait(timeout=10)
            authenticate(payload)
            return 'success'
        except ValueError as exc:
            return str(exc)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [first, second]))
    assert results.count('success') == 1
    passkey.refresh_from_db()
    assert passkey.sign_count == 1
    assert passkey.use_count == 1
    assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS).count() == 1
    if same_challenge:
        assert 'Challenge expired or already used' in results
        assert passkey.is_active
    else:
        assert any('security anomaly' in result for result in results)
        assert not passkey.is_active
        assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.PASSKEY_CLONE_DETECTED).exists()
    challenge.refresh_from_db()
    other_challenge.refresh_from_db()
    assert sum(item.used_at is not None for item in {challenge, other_challenge}) == 1


@pytest.mark.parametrize('failure', ['counter', 'audit'])
def test_success_write_failure_rolls_back_challenge_and_counter(assertion, monkeypatch, failure):
    _, passkey, build = assertion
    payload, challenge = build()

    def fail(*args, **kwargs):
        raise ValueError('simulated storage failure')

    if failure == 'counter':
        monkeypatch.setattr(UserPasskey, 'record_use', fail)
    else:
        monkeypatch.setattr(SSOAuditLog, 'log_event', fail)
    with pytest.raises(ValueError, match='simulated storage failure'):
        authenticate(payload)
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.sign_count == 0 and passkey.use_count == 0
    assert passkey.last_used_at is None
    assert not SSOAuditLog.objects.filter(event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS).exists()
    monkeypatch.undo()
    authenticate(payload)
    challenge.refresh_from_db()
    assert challenge.used_at is not None


@pytest.mark.django_db(transaction=True)
def test_concurrent_zero_counter_assertions_preserve_usage_count(assertion):
    _, passkey, build = assertion
    payloads = [build(sign_count=0)[0] for _ in range(2)]
    barrier = Barrier(2)

    def attempt(payload):
        try:
            barrier.wait(timeout=10)
            authenticate(payload)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(attempt, payloads))
    passkey.refresh_from_db()
    assert passkey.is_active
    assert passkey.sign_count == 0
    assert passkey.use_count == 2
    assert WebAuthnChallenge.objects.filter(used_at__isnull=False).count() == 2
    assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS).count() == 2


@pytest.mark.parametrize('change', ['missing-uv', 'legacy-policy'])
def test_otp_enabled_account_cannot_login_with_unverified_passkey(user, assertion, change):
    user.otp_enabled = True
    user.otp_verified = True
    user.save(update_fields=['otp_enabled', 'otp_verified'])
    client, passkey, build = assertion
    payload, challenge = build(change=change)
    tokens_before = OutstandingToken.objects.count()
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 400
    assert 'access' not in response.data and 'refresh' not in response.data
    assert OutstandingToken.objects.count() == tokens_before
    assert not SSOSession.objects.filter(user=user).exists()
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.use_count == 0


@pytest.mark.parametrize('mode', ['identified', 'discoverable'])
@pytest.mark.parametrize('otp_enabled', [False, True])
def test_disabled_account_cannot_login_with_active_passkey(user, assertion, mode, otp_enabled):
    client, passkey, build = assertion
    payload, challenge = build(mode)
    # Disable after issuing the challenge: outstanding ceremonies must also fail.
    user.is_active = False
    user.otp_enabled = otp_enabled
    user.otp_verified = otp_enabled
    user.save(update_fields=['is_active', 'otp_enabled', 'otp_verified'])
    tokens_before = OutstandingToken.objects.count()
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 400
    assert response.data == {'error': 'Authentication failed', 'code': 'verification_failed'}
    assert not any(
        name in response.cookies
        for name in (settings.ACCESS_TOKEN_COOKIE, settings.REFRESH_TOKEN_COOKIE, settings.SESSION_ID_COOKIE)
    )
    assert OutstandingToken.objects.count() == tokens_before
    assert not SSOSession.objects.filter(user=user).exists()
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.sign_count == 0 and passkey.use_count == 0
    assert passkey.last_used_at is None
    assert passkey.is_active
    assert not SSOAuditLog.objects.filter(user=user, event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS).exists()
    assert SSOAuditLog.objects.filter(
        user=user, event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED, success=False
    ).exists()


def test_service_rejects_disabled_owner_even_with_stale_active_user(user, assertion):
    _, passkey, build = assertion
    payload, challenge = build()
    # The service can be constructed with an old active user instance.
    type(user).objects.filter(pk=user.pk).update(is_active=False)
    assert user.is_active
    with pytest.raises(ValueError, match='Authentication failed'):
        WebAuthnService(user).verify_authentication(
            challenge=payload['challenge'],
            credential_id=payload['credentialId'],
            authenticator_data=payload['authenticatorData'],
            client_data_json=payload['clientDataJSON'],
            signature=payload['signature'],
            user_handle=payload['userHandle'],
        )
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.use_count == 0


@pytest.mark.parametrize('endpoint', ['options', 'verify'])
@pytest.mark.parametrize('proof', ['missing', 'wrong', 'foreign-origin', 'malformed', 'bearer-only'])
def test_passkey_login_requires_browser_csrf_before_side_effects(user, assertion, endpoint, proof, settings):
    settings.CSRF_TRUSTED_ORIGINS = [settings.WEB_APP_URL]
    _, passkey, build = assertion
    payload, challenge = build()
    client = APIClient(enforce_csrf_checks=True)
    token = client.get('/api/auth/csrf/').json()['csrfToken']
    headers = {'HTTP_ORIGIN': settings.WEB_APP_URL}
    if proof == 'wrong':
        headers['HTTP_X_CSRFTOKEN'] = 'a' * 32
    elif proof == 'foreign-origin':
        headers.update(HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://attacker.example')
    elif proof == 'malformed':
        client.cookies.clear()
        headers['HTTP_X_CSRFTOKEN'] = 'invalid'
    elif proof == 'bearer-only':
        client.cookies.clear()
        headers['HTTP_AUTHORIZATION'] = f'Bearer {RefreshToken.for_user(user).access_token}'
    tokens_before = OutstandingToken.objects.count()
    challenges_before = WebAuthnChallenge.objects.count()
    response = client.post(
        f'/api/sso/passkeys/authenticate/{endpoint}',
        {'email': user.email} if endpoint == 'options' else payload,
        format='json',
        **headers,
    )
    assert response.status_code == 403
    assert response.json()['code'] == 'csrf_failed'
    assert OutstandingToken.objects.count() == tokens_before
    assert WebAuthnChallenge.objects.count() == challenges_before
    assert not SSOSession.objects.filter(user=user).exists()
    assert not any(
        name in response.cookies
        for name in (settings.ACCESS_TOKEN_COOKIE, settings.REFRESH_TOKEN_COOKIE, settings.SESSION_ID_COOKIE)
    )
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.use_count == 0


@pytest.mark.parametrize('cookies_blocked', [False, True])
def test_valid_assertion_from_another_browser_is_rejected(assertion, settings, cookies_blocked):
    settings.CSRF_TRUSTED_ORIGINS = [settings.WEB_APP_URL]
    client, passkey, build = assertion
    payload, challenge = build()
    other = APIClient(enforce_csrf_checks=True)
    token = other.get('/api/auth/csrf/').json()['csrfToken']
    if cookies_blocked:
        other.cookies.clear()
    tokens_before = OutstandingToken.objects.count()
    response = other.post(
        '/api/sso/passkeys/authenticate/verify',
        payload,
        format='json',
        HTTP_ORIGIN=settings.WEB_APP_URL,
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 400
    assert response.data == {'error': 'Authentication failed', 'code': 'verification_failed'}
    assert OutstandingToken.objects.count() == tokens_before
    assert not SSOSession.objects.filter(user=passkey.user).exists()
    challenge.refresh_from_db()
    passkey.refresh_from_db()
    assert challenge.used_at is None
    assert passkey.use_count == 0 and passkey.is_active
    assert SSOAuditLog.objects.filter(
        user=passkey.user, event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED, success=False
    ).exists()
    # A failed cross-browser attempt does not consume the original browser's challenge.
    assert client.post('/api/sso/passkeys/authenticate/verify', payload, format='json').status_code == 200


@pytest.mark.parametrize('cookies_blocked', [False, True])
def test_browser_bound_login_supports_cookie_and_cookie_blocked_flows(assertion, settings, cookies_blocked):
    settings.CSRF_TRUSTED_ORIGINS = [settings.WEB_APP_URL]
    client, _, build = assertion
    token = client.get('/api/auth/csrf/').json()['csrfToken']
    client.credentials(HTTP_ORIGIN=settings.WEB_APP_URL, HTTP_X_CSRFTOKEN=token)
    if cookies_blocked:
        client.cookies.clear()
    payload, challenge = build()
    assert len(challenge.browser_binding) == 64
    assert challenge.browser_binding != token
    if not cookies_blocked:
        # Django issues a new mask each time; the underlying browser secret is unchanged.
        refreshed = client.get('/api/auth/csrf/').json()['csrfToken']
        assert refreshed != token
        client.credentials(HTTP_ORIGIN=settings.WEB_APP_URL, HTTP_X_CSRFTOKEN=refreshed)
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 200
    assert response.data == {'success': True}
    assert settings.ACCESS_TOKEN_COOKIE in response.cookies
    assert settings.REFRESH_TOKEN_COOKIE in response.cookies


def test_legacy_unbound_challenge_cannot_login_over_http(assertion):
    client, _, build = assertion
    payload, challenge = build()
    challenge.browser_binding = ''
    challenge.save(update_fields=['browser_binding'])
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 400
    challenge.refresh_from_db()
    assert challenge.used_at is None


@pytest.mark.parametrize('account', ['with-passkey', 'without-passkey', 'inactive', 'unknown', 'omitted'])
def test_public_login_options_do_not_disclose_accounts_or_credentials(user, assertion, account):
    client, passkey, _ = assertion
    email = user.email
    if account == 'without-passkey':
        passkey.delete()
    elif account == 'inactive':
        user.is_active = False
        user.save(update_fields=['is_active'])
    elif account == 'unknown':
        email = 'unknown@example.com'
    response = client.post(
        '/api/sso/passkeys/authenticate/options',
        {} if account == 'omitted' else {'email': email},
        format='json',
    )
    assert response.status_code == 200
    assert set(response.data) == {'challenge', 'timeout', 'rpId', 'userVerification'}
    assert response.data['userVerification'] == 'required'
    assert response.data['rpId'] == WebAuthnService().rp_id
    challenge = WebAuthnChallenge.objects.get(challenge=response.data['challenge'])
    assert challenge.user_id is None
    assert 'allowCredentials' not in response.data
