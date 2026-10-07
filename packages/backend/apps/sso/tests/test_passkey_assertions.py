"""Signed assertions must satisfy RP, user verification and credential ownership checks."""

import base64
import hashlib
import json

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, SSOSession, WebAuthnChallenge
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
    client = APIClient()

    def build(mode='identified', change=None):
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
        auth_data = rp_hash + bytes([flags]) + (1).to_bytes(4, 'big')
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


@pytest.mark.parametrize('mode,omit_handle', [('identified', True), ('identified', False), ('discoverable', False)])
def test_valid_assertion_can_login(user, assertion, mode, omit_handle):
    client, passkey, build = assertion
    payload, challenge = build(mode)
    if omit_handle:
        payload.pop('userHandle')
    response = client.post('/api/sso/passkeys/authenticate/verify', payload, format='json')
    assert response.status_code == 200
    assert response.data['access'] and response.data['refresh']
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
