"""Versioned, account/purpose-bound OTP encryption. No plaintext fallback."""
import base64
import binascii
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class OTPDecryptionError(Exception):
    pass


def load_keys():
    raw = settings.OTP_ENCRYPTION_KEYS
    if settings.OTP_ENCRYPTION_KEYS_FILE:
        try:
            with open(settings.OTP_ENCRYPTION_KEYS_FILE, encoding='utf-8') as stream:
                raw = stream.read()
        except OSError:
            raise ImproperlyConfigured('Cannot read OTP encryption key file') from None
    try:
        keys = [base64.b64decode(item.strip(), validate=True) for item in raw.split(',') if item.strip()]
    except (ValueError, binascii.Error):
        raise ImproperlyConfigured('Invalid OTP encryption key configuration') from None
    if not keys or any(len(key) != 32 for key in keys):
        raise ImproperlyConfigured('OTP_ENCRYPTION_KEYS requires base64-encoded 32-byte keys')
    if len({key_id(key) for key in keys}) != len(keys):
        raise ImproperlyConfigured('Duplicate OTP encryption key identifiers')
    return keys


def key_id(key):
    return hashlib.sha256(key).digest()[:8]


def associated_data(user_id, purpose):
    # Use the numeric DB identity, not the hashid representation (which depends on another deployment secret).
    return f'otp:v1:{int(user_id)}:{purpose}'.encode()


def encrypt_seed(user_id, purpose, seed):
    if not seed:
        return ''
    key = load_keys()[0]
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, seed.encode(), associated_data(user_id, purpose))
    return 'v1:' + base64.b64encode(key_id(key) + nonce + ciphertext).decode()


def decrypt_seed(user_id, purpose, value):
    if not value:
        return ''
    keys = {key_id(key): key for key in load_keys()}
    try:
        if not value.startswith('v1:'):
            raise ValueError
        payload = base64.b64decode(value[3:], validate=True)
        key = keys[payload[:8]]
        return AESGCM(key).decrypt(payload[8:20], payload[20:], associated_data(user_id, purpose)).decode()
    except (ValueError, KeyError, InvalidTag, UnicodeError, binascii.Error):
        raise OTPDecryptionError('Unable to decrypt OTP credential') from None
