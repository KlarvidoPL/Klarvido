"""
Encryption of OIDC client secrets at rest.

AES-256-GCM with a key from SSO_ENCRYPTION_KEYS (comma-separated base64 32-byte keys, newest first), or from the file
named by SSO_ENCRYPTION_KEYS_FILE. Stored payload: key_id (4 bytes) || nonce (12 bytes) || ciphertext+tag.

- The key_id is a fingerprint of the key, so rotation is safe: add a new key in front, re-encrypt, then drop the old
  one.
- The connection id is bound as associated data, so a ciphertext copied onto another connection fails to decrypt.
- Fails closed: without a configured key nothing is stored, and there is no plaintext fallback for new secrets.
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


class SSOEncryptionNotConfigured(Exception):
    """SSO_ENCRYPTION_KEYS is missing or malformed."""


class SSODecryptionError(Exception):
    """The stored payload cannot be decrypted with any configured key."""


def _raw_keys() -> str:
    key_file = getattr(settings, "SSO_ENCRYPTION_KEYS_FILE", "") or ""
    if key_file:
        try:
            with open(key_file, encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            # The message names the path only, never the key material
            raise SSOEncryptionNotConfigured(f"SSO_ENCRYPTION_KEYS_FILE cannot be read: {key_file}") from e
    return getattr(settings, "SSO_ENCRYPTION_KEYS", "") or ""


def _load_keys() -> list[bytes]:
    keys = []
    for item in _raw_keys().split(","):
        item = item.strip()
        if not item:
            continue
        try:
            key = base64.b64decode(item, validate=True)
        except (binascii.Error, ValueError) as e:
            raise SSOEncryptionNotConfigured("SSO_ENCRYPTION_KEYS contains invalid base64") from e
        if len(key) != KEY_SIZE:
            raise SSOEncryptionNotConfigured("Each SSO_ENCRYPTION_KEYS entry must decode to 32 bytes")
        keys.append(key)
    if not keys:
        raise SSOEncryptionNotConfigured("SSO_ENCRYPTION_KEYS is not set")
    return keys


def _key_id(key: bytes) -> bytes:
    return hashlib.sha256(key).digest()[:KEY_ID_SIZE]


def _associated_data(connection_id) -> bytes:
    return f"sso-oidc-client-secret:{connection_id}".encode()


def ensure_encryption_configured() -> None:
    """Raise SSOEncryptionNotConfigured unless a usable key is configured."""
    _load_keys()


def encrypt_client_secret(connection_id, secret: str) -> bytes:
    key = _load_keys()[0]
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, secret.encode(), _associated_data(connection_id))
    return _key_id(key) + nonce + ciphertext


def decrypt_client_secret(connection_id, payload: bytes) -> str:
    payload = bytes(payload)
    nonce_end = KEY_ID_SIZE + NONCE_SIZE
    key_id, nonce, ciphertext = payload[:KEY_ID_SIZE], payload[KEY_ID_SIZE:nonce_end], payload[nonce_end:]
    keys_by_id = {_key_id(key): key for key in _load_keys()}
    key = keys_by_id.get(key_id)
    if key is None:
        raise SSODecryptionError("No configured key matches the stored payload")
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, _associated_data(connection_id)).decode()
    except InvalidTag as e:
        raise SSODecryptionError("Authentication failed (wrong connection or corrupted payload)") from e
