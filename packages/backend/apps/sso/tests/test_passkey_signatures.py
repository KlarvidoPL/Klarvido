"""Passkey login must prove possession of the private key, including with legacy configuration."""

import base64
import hashlib
import json
from contextlib import nullcontext

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, SSOSession, WebAuthnChallenge
from apps.sso.services.webauthn import WebAuthnService
from apps.sso.tests.factories import UserPasskeyFactory


pytestmark = pytest.mark.django_db


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


@pytest.fixture(params=[None, False, True], ids=['default', 'legacy-false', 'legacy-true'])
def signature_policy(request):
    context = (
        nullcontext()
        if request.param is None
        else override_settings(WEBAUTHN_SKIP_SIGNATURE_VERIFICATION=request.param)
    )
    with context:
        yield


@pytest.fixture
def signing_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def public_key_cose(signing_key):
    numbers = signing_key.public_key().public_numbers()
    return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})


@pytest.fixture
def signed_assertion(signing_key):
    def build(challenge):
        service = WebAuthnService()
        auth_data = hashlib.sha256(service.rp_id.encode()).digest() + b'\x05' + (1).to_bytes(4, 'big')
        client_data = json.dumps(
            {'type': 'webauthn.get', 'challenge': challenge, 'origin': settings.WEB_APP_URL}
        ).encode()
        signature = signing_key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return auth_data, client_data, signature

    return build


def test_valid_signature_is_verified(signature_policy, public_key_cose, signed_assertion):
    auth_data, client_data, signature = signed_assertion('test-challenge')
    assert WebAuthnService()._verify_webauthn_signature(
        public_key_cose, auth_data, hashlib.sha256(client_data).digest(), signature
    )


@pytest.mark.parametrize('tamper', ['signature', 'authenticator-data', 'client-data', 'signing-key', 'public-key'])
def test_invalid_signature_is_rejected(signature_policy, public_key_cose, signed_assertion, tamper):
    auth_data, client_data, signature = signed_assertion('test-challenge')
    if tamper == 'signature':
        signature = b'forged-signature'
    elif tamper == 'authenticator-data':
        auth_data = auth_data[:-1] + b'\x02'
    elif tamper == 'client-data':
        client_data += b' '
    elif tamper == 'signing-key':
        signature = ec.generate_private_key(ec.SECP256R1()).sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
    else:
        public_key_cose = cbor2.dumps('not a COSE key')

    with pytest.raises(ValueError, match='Signature verification failed|Invalid public key format'):
        WebAuthnService()._verify_webauthn_signature(
            public_key_cose, auth_data, hashlib.sha256(client_data).digest(), signature
        )


@pytest.mark.parametrize('valid_signature', [False, True], ids=['forged', 'valid'])
def test_login_requires_valid_signature(signature_policy, user, public_key_cose, signed_assertion, valid_signature):
    cache.clear()
    client = APIClient()
    token = client.get('/api/auth/csrf/').json()['csrfToken']
    client.credentials(HTTP_X_CSRFTOKEN=token)
    passkey = UserPasskeyFactory(user=user, public_key=encode(public_key_cose))
    options = client.post('/api/sso/passkeys/authenticate/options', {'email': user.email}, format='json')
    assert options.status_code == 200
    assert options.data['allowCredentials'][0]['id'] == passkey.credential_id
    challenge = options.data['challenge']
    auth_data, client_data, signature = signed_assertion(challenge)
    tokens_before = OutstandingToken.objects.filter(user=user).count()

    response = client.post(
        '/api/sso/passkeys/authenticate/verify',
        {
            'challenge': challenge,
            'credentialId': passkey.credential_id,
            'authenticatorData': encode(auth_data),
            'clientDataJSON': encode(client_data),
            'signature': encode(signature if valid_signature else b'forged-signature'),
        },
        format='json',
    )
    passkey.refresh_from_db()
    challenge_record = WebAuthnChallenge.objects.get(challenge=challenge)

    if valid_signature:
        assert response.status_code == 200
        assert response.data['access'] and response.data['refresh']
        assert settings.ACCESS_TOKEN_COOKIE in response.cookies
        assert settings.REFRESH_TOKEN_COOKIE in response.cookies
        assert OutstandingToken.objects.filter(user=user).count() == tokens_before + 1
        assert SSOSession.objects.filter(user=user, is_active=True).exists()
        assert challenge_record.used_at is not None
        assert passkey.use_count == 1
    else:
        assert response.status_code == 400
        assert response.data['code'] == 'verification_failed'
        assert 'access' not in response.data and 'refresh' not in response.data
        assert not any(
            name in response.cookies
            for name in (settings.ACCESS_TOKEN_COOKIE, settings.REFRESH_TOKEN_COOKIE, settings.SESSION_ID_COOKIE)
        )
        assert OutstandingToken.objects.filter(user=user).count() == tokens_before
        assert not SSOSession.objects.filter(user=user).exists()
        assert challenge_record.used_at is None
        assert passkey.use_count == 0
        assert SSOAuditLog.objects.filter(
            user=user, event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED, success=False
        ).exists()
