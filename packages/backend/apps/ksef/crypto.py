"""
Encryption of KSeF tokens at rest.

AES-256-GCM with a key from KSEF_ENCRYPTION_KEYS (comma-separated base64 32-byte keys, newest first).
Stored payload: key_id (4 bytes) || nonce (12 bytes) || ciphertext+tag.

- The key_id is a fingerprint of the key, so rotation is safe: add a new key in front, re-encrypt, then drop the old
  one.
- The tenant id is bound as associated data, so a ciphertext copied onto another organization's row fails to decrypt.
- Fails closed: without a configured key nothing is stored, and no plaintext fallback exists.
"""

import base64
import binascii
import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

KEY_SIZE = 32
KEY_ID_SIZE = 4
NONCE_SIZE = 12


class KsefEncryptionNotConfigured(Exception):
    """KSEF_ENCRYPTION_KEYS is missing or malformed."""


class KsefDecryptionError(Exception):
    """The stored payload cannot be decrypted with any configured key."""


def _load_keys() -> list[bytes]:
    raw = getattr(settings, "KSEF_ENCRYPTION_KEYS", "") or ""
    keys = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            key = base64.b64decode(item, validate=True)
        except (binascii.Error, ValueError) as e:
            raise KsefEncryptionNotConfigured("KSEF_ENCRYPTION_KEYS contains invalid base64") from e
        if len(key) != KEY_SIZE:
            raise KsefEncryptionNotConfigured("Each KSEF_ENCRYPTION_KEYS entry must decode to 32 bytes")
        keys.append(key)
    if not keys:
        raise KsefEncryptionNotConfigured("KSEF_ENCRYPTION_KEYS is not set")
    return keys


def _key_id(key: bytes) -> bytes:
    return hashlib.sha256(key).digest()[:KEY_ID_SIZE]


def _associated_data(tenant_id) -> bytes:
    return f"ksef-credential:{tenant_id}".encode()


def ensure_encryption_configured() -> None:
    """Raise KsefEncryptionNotConfigured unless a usable key is configured. Call before any network work."""
    _load_keys()


def encrypt_token(tenant_id, token: str) -> bytes:
    key = _load_keys()[0]
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, token.encode(), _associated_data(tenant_id))
    return _key_id(key) + nonce + ciphertext


def decrypt_token(tenant_id, payload: bytes) -> str:
    payload = bytes(payload)
    nonce_end = KEY_ID_SIZE + NONCE_SIZE
    key_id, nonce, ciphertext = payload[:KEY_ID_SIZE], payload[KEY_ID_SIZE:nonce_end], payload[nonce_end:]
    keys_by_id = {_key_id(key): key for key in _load_keys()}
    key = keys_by_id.get(key_id)
    if key is None:
        raise KsefDecryptionError("No configured key matches the stored payload")
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, _associated_data(tenant_id)).decode()
    except InvalidTag as e:
        raise KsefDecryptionError("Authentication failed (wrong tenant or corrupted payload)") from e
