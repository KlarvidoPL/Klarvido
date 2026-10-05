"""
OIDC client secrets are encrypted at rest. Without a configured key they cannot be saved.
"""

import base64
import os
from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.multitenancy.tests.factories import TenantFactory
from apps.sso import constants
from apps.sso.crypto import (
    SSODecryptionError,
    SSOEncryptionNotConfigured,
    decrypt_client_secret,
    encrypt_client_secret,
)
from apps.sso.serializers import TenantSSOConnectionSerializer, UpdateTenantSSOConnectionSerializer
from apps.sso.services import outbound
from apps.sso.services.oidc import OIDCService

pytestmark = pytest.mark.django_db


def _new_key():
    return base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def encryption_keys(settings):
    settings.SSO_ENCRYPTION_KEYS = _new_key()
    settings.SSO_ENCRYPTION_KEYS_FILE = ""
    return settings.SSO_ENCRYPTION_KEYS


@pytest.fixture
def no_keys(settings):
    settings.SSO_ENCRYPTION_KEYS = ""
    settings.SSO_ENCRYPTION_KEYS_FILE = ""


@pytest.fixture
def public_idp(settings):
    """The example issuer does not resolve in the sandbox. Treat it as a public address."""
    with mock.patch.object(outbound, "_resolve_addresses", return_value=["93.184.216.34"]):
        yield


class TestEncryption:
    def test_round_trip(self, encryption_keys):
        payload = encrypt_client_secret("conn-1", "s3cret-value")

        assert decrypt_client_secret("conn-1", payload) == "s3cret-value"

    def test_payload_does_not_contain_the_plaintext(self, encryption_keys):
        assert b"s3cret-value" not in encrypt_client_secret("conn-1", "s3cret-value")

    def test_payload_is_bound_to_its_connection(self, encryption_keys):
        payload = encrypt_client_secret("conn-1", "s3cret-value")

        with pytest.raises(SSODecryptionError):
            decrypt_client_secret("conn-2", payload)

    def test_refuses_to_encrypt_without_a_key(self, no_keys):
        with pytest.raises(SSOEncryptionNotConfigured):
            encrypt_client_secret("conn-1", "s3cret-value")

    def test_rejects_a_malformed_key(self, settings):
        settings.SSO_ENCRYPTION_KEYS = "not-base64!!"

        with pytest.raises(SSOEncryptionNotConfigured):
            encrypt_client_secret("conn-1", "s3cret-value")

    def test_key_rotation_keeps_old_secrets_readable(self, settings):
        old_key = _new_key()
        settings.SSO_ENCRYPTION_KEYS = old_key
        payload = encrypt_client_secret("conn-1", "v")

        settings.SSO_ENCRYPTION_KEYS = f"{_new_key()},{old_key}"

        assert decrypt_client_secret("conn-1", payload) == "v"


class TestConnectionSecret:
    def test_model_stores_only_the_encrypted_value(self, encryption_keys, tenant_sso_connection):
        tenant_sso_connection.set_oidc_client_secret("s3cret")
        tenant_sso_connection.save()
        tenant_sso_connection.refresh_from_db()

        assert tenant_sso_connection.oidc_client_secret == ""
        assert b"s3cret" not in bytes(tenant_sso_connection.oidc_client_secret_encrypted)
        assert tenant_sso_connection.get_oidc_client_secret() == "s3cret"

    def test_legacy_plaintext_is_still_read(self, tenant_sso_connection):
        tenant_sso_connection.oidc_client_secret = "legacy"
        tenant_sso_connection.save()

        assert tenant_sso_connection.get_oidc_client_secret() == "legacy"

    def test_oidc_service_returns_the_decrypted_secret(self, encryption_keys, tenant_sso_connection):
        tenant_sso_connection.set_oidc_client_secret("s3cret")
        tenant_sso_connection.save()

        with mock.patch("apps.sso.services.oidc.get_secrets_service"):
            service = OIDCService(tenant_sso_connection)

        assert service.get_client_secret() == "s3cret"


class TestSerializersEncryptTheSecret:
    def _oidc_data(self, tenant, secret="s3cret"):
        return {
            "tenant_id": str(tenant.pk),
            "name": "Entra",
            "connection_type": constants.IdentityProviderType.OIDC,
            "allowed_domains": ["client.pl"],
            "oidc_issuer": "https://idp.example.test",
            "oidc_client_id": "client-id",
            "oidc_client_secret": secret,
        }

    def test_creating_a_connection_stores_the_secret_encrypted(self, encryption_keys, public_idp):
        tenant = TenantFactory()
        serializer = TenantSSOConnectionSerializer(data=self._oidc_data(tenant))
        serializer.is_valid(raise_exception=True)

        connection = serializer.save()
        connection.refresh_from_db()

        assert connection.oidc_client_secret == ""
        assert b"s3cret" not in bytes(connection.oidc_client_secret_encrypted)
        assert connection.get_oidc_client_secret() == "s3cret"

    def test_creating_with_a_secret_is_refused_without_a_key(self, no_keys, public_idp):
        tenant = TenantFactory()
        serializer = TenantSSOConnectionSerializer(data=self._oidc_data(tenant))

        assert not serializer.is_valid()
        assert "oidc_client_secret" in serializer.errors

    def test_updating_replaces_the_encrypted_secret(self, encryption_keys, tenant_sso_connection):
        tenant_sso_connection.set_oidc_client_secret("old")
        tenant_sso_connection.save()
        serializer = UpdateTenantSSOConnectionSerializer(
            instance=tenant_sso_connection, data={"oidc_client_secret": "new"}, partial=True
        )
        serializer.is_valid(raise_exception=True)

        serializer.save()
        tenant_sso_connection.refresh_from_db()

        assert tenant_sso_connection.get_oidc_client_secret() == "new"


class TestEncryptLegacySecretsCommand:
    def test_encrypts_plaintext_rows_and_clears_them(self, encryption_keys, tenant_sso_connection):
        tenant_sso_connection.oidc_client_secret = "legacy"
        tenant_sso_connection.save()
        out = StringIO()

        call_command("encrypt_oidc_client_secrets", stdout=out)
        tenant_sso_connection.refresh_from_db()

        assert "Encrypted 1" in out.getvalue()
        assert tenant_sso_connection.oidc_client_secret == ""
        assert tenant_sso_connection.get_oidc_client_secret() == "legacy"

    def test_running_twice_changes_nothing(self, encryption_keys, tenant_sso_connection):
        tenant_sso_connection.oidc_client_secret = "legacy"
        tenant_sso_connection.save()
        call_command("encrypt_oidc_client_secrets", stdout=StringIO())
        tenant_sso_connection.refresh_from_db()
        first = bytes(tenant_sso_connection.oidc_client_secret_encrypted)

        out = StringIO()
        call_command("encrypt_oidc_client_secrets", stdout=out)
        tenant_sso_connection.refresh_from_db()

        assert "Encrypted 0" in out.getvalue()
        assert bytes(tenant_sso_connection.oidc_client_secret_encrypted) == first

    def test_refuses_to_run_without_a_key(self, no_keys):
        with pytest.raises(CommandError):
            call_command("encrypt_oidc_client_secrets", stdout=StringIO())
