"""
The KSeF encryption key can come from a file (Docker secret) instead of the environment. The file takes precedence,
and an unreadable or malformed file fails closed without revealing key material.
"""

import base64
import os

import pytest

from apps.ksef import crypto

pytestmark = pytest.mark.django_db


@pytest.fixture
def key_text():
    return base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def key_file(tmp_path, key_text):
    path = tmp_path / "ksef_encryption_keys"
    path.write_text(key_text + "\n")
    return path


def test_round_trip_with_key_from_file(settings, key_file):
    settings.KSEF_ENCRYPTION_KEYS = ""
    settings.KSEF_ENCRYPTION_KEYS_FILE = str(key_file)

    payload = crypto.encrypt_token(7, "token-from-file")

    assert crypto.decrypt_token(7, payload) == "token-from-file"


def test_file_takes_precedence_over_environment_value(settings, key_file):
    other_key = base64.b64encode(os.urandom(32)).decode()
    settings.KSEF_ENCRYPTION_KEYS = other_key
    settings.KSEF_ENCRYPTION_KEYS_FILE = str(key_file)

    payload = crypto.encrypt_token(7, "token")

    settings.KSEF_ENCRYPTION_KEYS = ""
    assert crypto.decrypt_token(7, payload) == "token"


def test_missing_file_fails_closed_without_revealing_path_contents(settings, tmp_path):
    settings.KSEF_ENCRYPTION_KEYS = ""
    settings.KSEF_ENCRYPTION_KEYS_FILE = str(tmp_path / "does-not-exist")

    with pytest.raises(crypto.KsefEncryptionNotConfigured):
        crypto.encrypt_token(7, "token")
    with pytest.raises(crypto.KsefEncryptionNotConfigured):
        crypto.ensure_encryption_configured()


def test_malformed_file_fails_closed_without_echoing_its_content(settings, tmp_path):
    secret_looking = "not-base64-but-secret-material!!"
    path = tmp_path / "keys"
    path.write_text(secret_looking)
    settings.KSEF_ENCRYPTION_KEYS = ""
    settings.KSEF_ENCRYPTION_KEYS_FILE = str(path)

    with pytest.raises(crypto.KsefEncryptionNotConfigured) as error:
        crypto.encrypt_token(7, "token")

    assert secret_looking not in str(error.value)


def test_environment_variable_still_works_without_file(settings, key_text):
    settings.KSEF_ENCRYPTION_KEYS = key_text
    settings.KSEF_ENCRYPTION_KEYS_FILE = ""

    payload = crypto.encrypt_token(7, "token")

    assert crypto.decrypt_token(7, payload) == "token"
