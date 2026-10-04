import base64
import os
from unittest.mock import patch

import pytest

from apps.ksef import crypto

pytestmark = pytest.mark.django_db


def _key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def test_round_trip(settings):
    settings.KSEF_ENCRYPTION_KEYS = _key()

    payload = crypto.encrypt_token(7, "abc-secret-token")

    assert crypto.decrypt_token(7, payload) == "abc-secret-token"
    assert b"abc-secret-token" not in payload


def test_ciphertext_is_bound_to_tenant(settings):
    settings.KSEF_ENCRYPTION_KEYS = _key()
    payload = crypto.encrypt_token(7, "abc-secret-token")

    with pytest.raises(crypto.KsefDecryptionError):
        crypto.decrypt_token(8, payload)


def test_rotation_keeps_old_payloads_readable(settings):
    old_key, new_key = _key(), _key()
    settings.KSEF_ENCRYPTION_KEYS = old_key
    old_payload = crypto.encrypt_token(1, "old-token")

    settings.KSEF_ENCRYPTION_KEYS = f"{new_key},{old_key}"

    assert crypto.decrypt_token(1, old_payload) == "old-token"
    assert crypto.decrypt_token(1, crypto.encrypt_token(1, "new-token")) == "new-token"


def test_unknown_key_cannot_decrypt(settings):
    settings.KSEF_ENCRYPTION_KEYS = _key()
    payload = crypto.encrypt_token(1, "token")

    settings.KSEF_ENCRYPTION_KEYS = _key()

    with pytest.raises(crypto.KsefDecryptionError):
        crypto.decrypt_token(1, payload)


def test_fails_closed_without_key(settings):
    settings.KSEF_ENCRYPTION_KEYS = ""

    with pytest.raises(crypto.KsefEncryptionNotConfigured):
        crypto.encrypt_token(1, "token")


@pytest.mark.parametrize("value", ["not base64!!", base64.b64encode(b"short").decode()])
def test_rejects_malformed_key(settings, value):
    settings.KSEF_ENCRYPTION_KEYS = value

    with pytest.raises(crypto.KsefEncryptionNotConfigured):
        crypto.ensure_encryption_configured()
