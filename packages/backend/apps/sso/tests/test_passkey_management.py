"""Exercise fresh-authentication barriers through REST and GraphQL."""

import hashlib
import json
from datetime import timedelta

import pyotp
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from graphql_relay import to_global_id
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.sso.models import PasskeyManagementGrant, SSOSession, WebAuthnChallenge, SSOAuditLog
from apps.sso.constants import SSOAuditEventType
from apps.sso.services.webauthn import WebAuthnService
from apps.sso.tests.factories import UserPasskeyFactory
from apps.sso.tests import test_passkey_assertions, test_passkey_registration
from apps.sso.views import PasskeyDeleteView


assertion = test_passkey_assertions.assertion
enrollment = test_passkey_registration.enrollment
encode = test_passkey_assertions.encode

pytestmark = pytest.mark.django_db
PASSWORD = 'Fresh-authentication-password-42!'
ENROLLMENT_PASSWORD = 'Enrollment-password-42!'
VERIFY = '/api/sso/passkeys/reauthenticate/verify'
OPTIONS = '/api/sso/passkeys/register/options'


@pytest.fixture
def manager(user):
    cache.clear()
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    client = APIClient()
    client.force_authenticate(user)
    return client


def proof(client, action='register', passkey=None, **extra):
    data = {'action': action, 'password': PASSWORD, **extra}
    if passkey:
        data['passkeyId'] = to_global_id('PasskeyType', passkey.pk)
    response = client.post(VERIFY, data, format='json')
    assert response.status_code == 200, response.data
    assert response['Cache-Control'] == 'no-store'
    return response.data['authorization']


def delete(client, passkey, token=None):
    client.credentials(HTTP_X_PASSKEY_AUTHORIZATION=token or '', HTTP_AUTHORIZATION='Bearer test')
    return client.post(
        '/api/graphql/',
        {
            'query': 'mutation($id: String!) { deletePasskey(input: {id: $id}) {deletedIds} }',
            'variables': {'id': to_global_id('PasskeyType', passkey.pk)},
        },
        format='json',
    ).json()


@pytest.mark.parametrize('endpoint', [OPTIONS, '/api/sso/passkeys/register/verify'])
def test_session_alone_cannot_register(manager, user, endpoint):
    response = manager.post(endpoint, {}, format='json')
    assert response.status_code == 403
    assert not WebAuthnChallenge.objects.filter(user=user).exists()
    assert not user.passkeys.exists()


@pytest.mark.parametrize('password', ['', 'incorrect', None, 42])
def test_wrong_password_cannot_issue_authorization(manager, password):
    response = manager.post(VERIFY, {'action': 'register', 'password': password}, format='json')
    assert response.status_code == 403
    assert not PasskeyManagementGrant.objects.exists()


def test_password_grant_is_hashed_and_bound_to_one_registration(manager, user):
    token = proof(manager)
    grant = PasskeyManagementGrant.objects.get()
    assert grant.token_hash == hashlib.sha256(token.encode()).hexdigest()
    manager.credentials(HTTP_X_PASSKEY_AUTHORIZATION=token)
    assert manager.post(OPTIONS, {}, format='json').status_code == 200
    assert manager.post(OPTIONS, {}, format='json').status_code == 403
    assert SSOSession.objects.count() == 0


@pytest.mark.parametrize('state', ['expired', 'used', 'other-user', 'wrong-action', 'random'])
def test_invalid_proof_cannot_start_registration(manager, user_factory, state):
    token = proof(manager)
    grant = PasskeyManagementGrant.objects.get()
    if state == 'expired':
        grant.expires_at = timezone.now() - timedelta(seconds=1)
    elif state == 'used':
        grant.used_at = timezone.now()
    elif state == 'other-user':
        grant.user = user_factory()
    elif state == 'wrong-action':
        grant.action = 'delete'
    elif state == 'random':
        token = 'random'
    grant.save()
    manager.credentials(HTTP_X_PASSKEY_AUTHORIZATION=token)
    assert manager.post(OPTIONS, {}, format='json').status_code == 403


def test_registration_consumes_grant(enrollment):
    client, challenge, _, _, payload = enrollment
    assert client.post('/api/sso/passkeys/register/verify', payload(), format='json').status_code == 200
    assert PasskeyManagementGrant.objects.get(registration_challenge__challenge=challenge).used_at is not None
    assert client.post('/api/sso/passkeys/register/verify', payload(), format='json').status_code == 403


def test_registration_cannot_use_another_challenges_proof(enrollment):
    client, _, _, _, payload = enrollment
    client.credentials(HTTP_X_PASSKEY_AUTHORIZATION=proof(client, password=ENROLLMENT_PASSWORD))
    assert client.post('/api/sso/passkeys/register/verify', payload(), format='json').status_code == 403


def test_graphql_delete_requires_matching_one_use_proof(manager, user):
    first = UserPasskeyFactory(user=user)
    second = UserPasskeyFactory(user=user)
    assert delete(manager, first).get('errors')
    token = proof(manager, 'delete', first)
    assert delete(manager, second, token).get('errors')
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_active and second.is_active
    assert not delete(manager, first, token).get('errors')
    first.refresh_from_db()
    assert not first.is_active
    assert PasskeyManagementGrant.objects.get().used_at is not None
    assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.PASSKEY_REMOVED, user=user).exists()
    assert delete(manager, first, token).get('errors')


def test_otp_is_required_and_failed_attempts_persist(manager, user):
    user.otp_enabled = user.otp_verified = True
    user.otp_base32 = pyotp.random_base32()
    user.save()
    response = manager.post(VERIFY, {'action': 'register', 'password': PASSWORD}, format='json')
    assert response.status_code == 403
    user.refresh_from_db()
    assert user.otp_failed_attempts == 1
    assert not PasskeyManagementGrant.objects.exists()
    token = proof(manager, otpToken=pyotp.TOTP(user.otp_base32).now())
    assert token


def test_social_only_account_cannot_use_empty_password(manager, user):
    user.set_unusable_password()
    user.save()
    assert manager.post(VERIFY, {'action': 'register', 'password': PASSWORD}, format='json').status_code == 403


def test_password_attempts_are_throttled_per_account(manager):
    for _ in range(10):
        assert manager.post(VERIFY, {'action': 'register', 'password': 'wrong'}, format='json').status_code == 403
    assert manager.post(VERIFY, {'action': 'register', 'password': PASSWORD}, format='json').status_code == 429


def test_ordinary_login_challenge_cannot_issue_management_grant(assertion, user):
    client, _, build = assertion
    payload, _ = build()
    client.force_authenticate(user)
    assert client.post(VERIFY, payload, format='json').status_code == 403
    assert not PasskeyManagementGrant.objects.exists()


@pytest.mark.parametrize('change', [None, 'forged', 'missing-uv', 'wrong-owner', 'counter-rollback'])
def test_existing_passkey_can_authorize_change_only_with_valid_proof(enrollment, user, user_factory, change, settings):
    settings.WEBAUTHN_STRICT_SIGN_COUNT = True
    client, _, private_key, _, registration_payload = enrollment
    assert client.post('/api/sso/passkeys/register/verify', registration_payload(), format='json').status_code == 200
    client.credentials()
    passkey = user.passkeys.get()
    options = client.post(
        '/api/sso/passkeys/reauthenticate/options', {'action': 'delete', 'passkeyId': str(passkey.pk)}, format='json'
    )
    assert options.status_code == 200
    challenge = options.data['challenge']
    client_data = json.dumps({'type': 'webauthn.get', 'challenge': challenge, 'origin': settings.WEB_APP_URL}).encode()
    auth_data = (
        hashlib.sha256(WebAuthnService().rp_id.encode()).digest()
        + bytes([1 if change == 'missing-uv' else 5])
        + (8 if change == 'counter-rollback' else 10).to_bytes(4, 'big')
    )
    signature = private_key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
    if change == 'forged':
        signature = b'forged'
    elif change == 'wrong-owner':
        passkey.user = user_factory()
        passkey.save()
    payload = {
        'challenge': challenge,
        'credentialId': passkey.credential_id,
        'authenticatorData': encode(auth_data),
        'clientDataJSON': encode(client_data),
        'signature': encode(signature),
    }
    # Management challenges cannot be used for the ordinary login endpoint.
    assert client.post('/api/sso/passkeys/authenticate/verify', payload, format='json').status_code == 400
    response = client.post(VERIFY, payload, format='json')
    grant = PasskeyManagementGrant.objects.get(authentication_challenge__challenge=challenge)
    if change:
        assert response.status_code == 403
        assert grant.token_hash is None
        assert not WebAuthnChallenge.objects.get(challenge=challenge).used_at
        if change == 'counter-rollback':
            passkey.refresh_from_db()
            assert not passkey.is_active
            assert SSOAuditLog.objects.filter(event_type=SSOAuditEventType.PASSKEY_CLONE_DETECTED).exists()
    else:
        assert response.status_code == 200
        assert 'access' not in response.data and 'refresh' not in response.data
        assert not response.cookies
        assert not SSOSession.objects.exists()
        assert grant.token_hash
        assert client.post(VERIFY, payload, format='json').status_code == 403
        assert not delete(client, passkey, response.data['authorization']).get('errors')


def test_rest_delete_is_also_protected(manager, user):
    passkey = UserPasskeyFactory(user=user)
    factory = APIRequestFactory()
    request = factory.delete('/unused')
    force_authenticate(request, user)
    assert PasskeyDeleteView.as_view()(request, passkey_id=str(passkey.pk)).status_code == 403
    token = proof(manager, 'delete', passkey)
    request = factory.delete('/unused', HTTP_X_PASSKEY_AUTHORIZATION=token)
    force_authenticate(request, user)
    assert PasskeyDeleteView.as_view()(request, passkey_id=str(passkey.pk)).status_code == 204
    passkey.refresh_from_db()
    assert not passkey.is_active


def test_cross_origin_clients_can_send_the_authorization_header(settings):
    settings.CORS_ALLOWED_ORIGINS = ['https://app.example.com']
    response = APIClient().options(
        OPTIONS,
        HTTP_ORIGIN='https://app.example.com',
        HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type,x-passkey-authorization,x-csrftoken',
    )
    assert response.status_code == 200
    assert response['Access-Control-Allow-Origin'] == 'https://app.example.com'
    assert 'x-passkey-authorization' in response['Access-Control-Allow-Headers'].lower()
