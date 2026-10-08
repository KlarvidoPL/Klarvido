"""Verify enrollment from actual authenticator data and round-trip through signed login."""

import base64
import hashlib
import json
import secrets
from datetime import timedelta

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, UserPasskey, WebAuthnChallenge
from apps.sso.services.webauthn import WebAuthnService
from apps.sso.tests.factories import UserPasskeyFactory


pytestmark = pytest.mark.django_db


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


@pytest.fixture
def enrollment(user):
    cache.clear()
    client = APIClient()
    client.force_authenticate(user)
    user.set_password('Enrollment-password-42!')
    user.save(update_fields=['password'])
    proof = client.post(
        '/api/sso/passkeys/reauthenticate/verify',
        {
            'action': 'register',
            'password': 'Enrollment-password-42!',
        },
        format='json',
    )
    assert proof.status_code == 200
    client.credentials(HTTP_X_PASSKEY_AUTHORIZATION=proof.data['authorization'])
    response = client.post('/api/sso/passkeys/register/options', {'userVerification': 'required'}, format='json')
    assert response.status_code == 200
    assert response.data['pubKeyCredParams'] == [{'type': 'public-key', 'alg': -7}]
    challenge = response.data['challenge']
    assert WebAuthnChallenge.objects.get(challenge=challenge).user_verification == 'required'
    private_key = ec.generate_private_key(ec.SECP256R1())
    numbers = private_key.public_key().public_numbers()
    cose = {1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')}
    credential_id = secrets.token_bytes(32)

    def payload(change=None):
        client_data = {'type': 'webauthn.create', 'challenge': challenge, 'origin': settings.WEB_APP_URL}
        rp_hash = hashlib.sha256(WebAuthnService().rp_id.encode()).digest()
        flags = 0x45
        key = dict(cose)
        if change in {'origin', 'challenge', 'type'}:
            client_data[change] = 'invalid'
        elif change == 'cross-origin':
            client_data['crossOrigin'] = True
        elif change == 'rp-hash':
            rp_hash = b'\x00' * 32
        elif change == 'missing-up':
            flags &= ~0x01
        elif change == 'missing-uv':
            flags &= ~0x04
        elif change == 'missing-at':
            flags &= ~0x40
        elif change == 'algorithm':
            key[3] = -257
        elif change == 'curve':
            key[-1] = 2
        elif change == 'point':
            key[-2] = b'\x00' * 32
        auth_data = (
            rp_hash
            + bytes([flags])
            + (9).to_bytes(4, 'big')
            + b'\x00' * 16
            + len(credential_id).to_bytes(2, 'big')
            + credential_id
            + cbor2.dumps(key)
        )
        attestation = cbor2.dumps({'fmt': 'none', 'attStmt': {}, 'authData': auth_data})
        if change == 'attestation':
            attestation = b'invalid-cbor'
        return {
            'challenge': challenge,
            'credentialId': encode(b'wrong-id' if change == 'credential-id' else credential_id),
            'attestationObject': encode(attestation),
            'clientDataJSON': encode(json.dumps(client_data).encode()),
            'name': 'Touch ID',
            'transports': ['internal'],
        }

    return client, challenge, private_key, cose, payload


@pytest.mark.parametrize('legacy_key', ['omitted', 'spki', 'attacker'])
def test_enrollment_stores_verified_cose_key_and_can_login(user, enrollment, legacy_key):
    client, challenge, private_key, cose, payload = enrollment
    request = payload()
    if legacy_key == 'spki':
        request['publicKey'] = encode(
            private_key.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    elif legacy_key == 'attacker':
        request['publicKey'] = 'attacker-chosen-key'
    response = client.post('/api/sso/passkeys/register/verify', request, format='json')
    assert response.status_code == 200
    passkey = UserPasskey.objects.get(user=user)
    assert cbor2.loads(base64.urlsafe_b64decode(passkey.public_key + '=' * (-len(passkey.public_key) % 4))) == cose
    assert passkey.credential_id == request['credentialId']
    assert passkey.sign_count == 9
    assert WebAuthnChallenge.objects.get(challenge=challenge).used_at is not None
    assert SSOAuditLog.objects.filter(user=user, event_type=SSOAuditEventType.PASSKEY_REGISTERED).exists()

    anonymous_client = APIClient()
    token = anonymous_client.get('/api/auth/csrf/').json()['csrfToken']
    anonymous_client.credentials(HTTP_X_CSRFTOKEN=token)
    options = anonymous_client.post('/api/sso/passkeys/authenticate/options', {}, format='json')
    assert options.status_code == 200
    auth_data = hashlib.sha256(WebAuthnService().rp_id.encode()).digest() + b'\x05' + (10).to_bytes(4, 'big')
    client_data = json.dumps(
        {'type': 'webauthn.get', 'challenge': options.data['challenge'], 'origin': settings.WEB_APP_URL}
    ).encode()
    signature = private_key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
    login = anonymous_client.post(
        '/api/sso/passkeys/authenticate/verify',
        {
            'challenge': options.data['challenge'],
            'credentialId': passkey.credential_id,
            'authenticatorData': encode(auth_data),
            'clientDataJSON': encode(client_data),
            'signature': encode(signature),
            'userHandle': WebAuthnService(user)._encode_user_id(user),
        },
        format='json',
    )
    assert login.status_code == 200
    assert login.data == {'success': True}
    assert settings.ACCESS_TOKEN_COOKIE in login.cookies
    assert settings.REFRESH_TOKEN_COOKIE in login.cookies


@pytest.mark.parametrize(
    'change',
    [
        'origin',
        'challenge',
        'type',
        'cross-origin',
        'rp-hash',
        'missing-up',
        'missing-uv',
        'missing-at',
        'algorithm',
        'curve',
        'point',
        'attestation',
        'credential-id',
    ],
)
def test_invalid_registration_creates_no_credential_and_keeps_challenge(user, enrollment, change):
    client, challenge, _, _, payload = enrollment
    response = client.post('/api/sso/passkeys/register/verify', payload(change), format='json')
    assert response.status_code == 400
    assert response.data['error'] == 'Passkey registration verification failed'
    assert not UserPasskey.objects.filter(user=user).exists()
    assert WebAuthnChallenge.objects.get(challenge=challenge).used_at is None
    assert not SSOAuditLog.objects.filter(user=user, event_type=SSOAuditEventType.PASSKEY_REGISTERED).exists()


@pytest.mark.parametrize('state', ['expired', 'used', 'other-user', 'duplicate'])
def test_registration_rejects_invalid_challenges_and_duplicate_credentials(user, user_factory, enrollment, state):
    client, challenge, _, _, payload = enrollment
    challenge_record = WebAuthnChallenge.objects.get(challenge=challenge)
    request = payload()
    if state == 'expired':
        challenge_record.expires_at = timezone.now() - timedelta(seconds=1)
    elif state == 'used':
        challenge_record.used_at = timezone.now()
    elif state == 'other-user':
        challenge_record.user = user_factory()
    else:
        UserPasskeyFactory(user=user_factory(), credential_id=request['credentialId'])
    challenge_record.save()
    response = client.post('/api/sso/passkeys/register/verify', request, format='json')
    assert response.status_code == 400
    assert not UserPasskey.objects.filter(user=user).exists()
    if state == 'duplicate':
        assert response.data['error'] == 'Passkey is already registered'
        challenge_record.refresh_from_db()
        assert challenge_record.used_at is None


def test_owner_can_replace_incompatible_existing_key(user, enrollment):
    passkey = UserPasskeyFactory(user=user, public_key='legacy-SPKI-or-invalid-key')
    service = WebAuthnService(user)
    service.delete_passkey(str(passkey.id))
    passkey.refresh_from_db()
    assert passkey.public_key == 'legacy-SPKI-or-invalid-key'
    assert not passkey.is_active
    client, _, _, _, payload = enrollment
    response = client.post('/api/sso/passkeys/register/verify', payload(), format='json')
    assert response.status_code == 200
    assert UserPasskey.objects.filter(user=user, is_active=True).count() == 1


def test_invalid_registration_policy_is_rejected_before_creating_challenge(user):
    cache.clear()
    client = APIClient()
    client.force_authenticate(user)
    user.set_password('Enrollment-password-42!')
    user.save(update_fields=['password'])
    proof = client.post(
        '/api/sso/passkeys/reauthenticate/verify',
        {
            'action': 'register',
            'password': 'Enrollment-password-42!',
        },
        format='json',
    )
    client.credentials(HTTP_X_PASSKEY_AUTHORIZATION=proof.data['authorization'])
    response = client.post('/api/sso/passkeys/register/options', {'userVerification': 'invalid'}, format='json')
    assert response.status_code == 400
    assert not WebAuthnChallenge.objects.filter(user=user).exists()


@pytest.mark.parametrize(
    'field,value',
    [
        ('credentialId', 123),
        ('clientDataJSON', []),
        ('attestationObject', {'secret': 'private-proof'}),
        ('name', 'x' * 256),
        ('transports', 'internal'),
        ('transports', ['invalid']),
        ('attestationObject', 'x' * 65537),
    ],
)
def test_registration_fields_are_bounded_and_not_coerced(user, enrollment, field, value):
    client, challenge, _, _, payload = enrollment
    data = payload()
    data[field] = value
    response = client.post('/api/sso/passkeys/register/verify', data, format='json')
    assert response.status_code == 400
    assert b'private-proof' not in response.content
    assert not UserPasskey.objects.filter(user=user).exists()
    assert WebAuthnChallenge.objects.get(challenge=challenge).used_at is None
    event = SSOAuditLog.objects.get(user=user, event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED)
    assert event.metadata['operation'] == 'registration'


@pytest.mark.parametrize('value', [False, 'true', 1, []])
def test_registration_options_require_boolean_resident_key_policy(enrollment, value):
    client, _, _, _, _ = enrollment
    before = WebAuthnChallenge.objects.count()
    response = client.post('/api/sso/passkeys/register/options', {'requireResidentKey': value}, format='json')
    assert response.status_code == 400
    assert WebAuthnChallenge.objects.count() == before
