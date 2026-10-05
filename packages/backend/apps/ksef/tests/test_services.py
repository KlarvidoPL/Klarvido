import base64
import os
from unittest.mock import patch

import pytest

from apps.ksef import crypto, services
from apps.ksef.client import TokenCheck
from apps.ksef.constants import KsefCredentialStatus, KsefErrorCode
from apps.ksef.models import KsefCredential
from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog

pytestmark = pytest.mark.django_db

VALID = TokenCheck(status=KsefCredentialStatus.VALID)
INVALID = TokenCheck(status=KsefCredentialStatus.INVALID, error_code=KsefErrorCode.INVALID_TOKEN)
UNAVAILABLE = TokenCheck(status=KsefCredentialStatus.UNVERIFIED, error_code=KsefErrorCode.SERVICE_UNAVAILABLE)


@pytest.fixture(autouse=True)
def encryption_key(settings):
    settings.KSEF_ENCRYPTION_KEYS = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def polish_tenant(tenant_factory):
    return tenant_factory(nip="5252344078")


def test_rejects_company_without_nip(tenant_factory):
    tenant = tenant_factory(nip="")

    with patch.object(services, "verify_token") as verify:
        result = services.save_token(tenant, None, "token")

    assert result.error_code == KsefErrorCode.NIP_MISSING
    verify.assert_not_called()


def test_rejects_non_polish_company(polish_tenant):
    polish_tenant.country = "DE"

    with patch.object(services, "verify_token") as verify:
        result = services.save_token(polish_tenant, None, "token")

    assert result.error_code == KsefErrorCode.COUNTRY_NOT_SUPPORTED
    verify.assert_not_called()


def test_invalid_token_is_never_stored(polish_tenant):
    with patch.object(services, "verify_token", return_value=INVALID):
        result = services.save_token(polish_tenant, None, "wrong-token")

    assert result.error_code == KsefErrorCode.INVALID_TOKEN
    assert not KsefCredential.objects.filter(tenant=polish_tenant).exists()


def test_valid_token_is_stored_encrypted(polish_tenant):
    with patch.object(services, "verify_token", return_value=VALID):
        result = services.save_token(polish_tenant, None, "  real-token-1234  ")

    assert result.error_code == ""
    credential = KsefCredential.objects.get(tenant=polish_tenant)
    assert credential.status == KsefCredentialStatus.VALID
    assert credential.token_hint == "1234"
    assert credential.last_verified_at is not None
    assert b"real-token-1234" not in bytes(credential.encrypted_token)
    assert crypto.decrypt_token(polish_tenant.pk, credential.encrypted_token) == "real-token-1234"


def test_token_name_is_stored_and_refreshed(polish_tenant):
    named = TokenCheck(status=KsefCredentialStatus.VALID, token_name="KlarvidoTest")
    with patch.object(services, "verify_token", return_value=named):
        services.save_token(polish_tenant, None, "named-token-0003")
    assert KsefCredential.objects.get(tenant=polish_tenant).token_name == "KlarvidoTest"

    renamed = TokenCheck(status=KsefCredentialStatus.VALID, token_name="Renamed")
    with patch.object(services, "verify_token", return_value=renamed):
        services.retest_token(polish_tenant, None)
    assert KsefCredential.objects.get(tenant=polish_tenant).token_name == "Renamed"

    # A check that cannot read the name keeps the last known one
    with patch.object(services, "verify_token", return_value=VALID):
        services.retest_token(polish_tenant, None)
    assert KsefCredential.objects.get(tenant=polish_tenant).token_name == "Renamed"


def test_ksef_outage_saves_as_unverified(polish_tenant):
    with patch.object(services, "verify_token", return_value=UNAVAILABLE):
        result = services.save_token(polish_tenant, None, "token-abcd")

    assert result.error_code == KsefErrorCode.SERVICE_UNAVAILABLE
    credential = KsefCredential.objects.get(tenant=polish_tenant)
    assert credential.status == KsefCredentialStatus.UNVERIFIED
    assert credential.last_verified_at is None


def test_replacing_token_updates_the_single_row(polish_tenant):
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, "first-token-0001")
        services.save_token(polish_tenant, None, "second-token-0002")

    assert KsefCredential.objects.filter(tenant=polish_tenant).count() == 1
    assert KsefCredential.objects.get(tenant=polish_tenant).token_hint == "0002"


def test_fails_closed_without_encryption_key(polish_tenant, settings):
    settings.KSEF_ENCRYPTION_KEYS = ""

    with patch.object(services, "verify_token") as verify:
        result = services.save_token(polish_tenant, None, "token")

    assert result.error_code == KsefErrorCode.ENCRYPTION_NOT_CONFIGURED
    verify.assert_not_called()
    assert not KsefCredential.objects.filter(tenant=polish_tenant).exists()


def test_retest_marks_revoked_token_invalid_and_keeps_it(polish_tenant):
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, "token-to-revoke")

    with patch.object(services, "verify_token", return_value=INVALID):
        result = services.retest_token(polish_tenant, None)

    assert result.credential.status == KsefCredentialStatus.INVALID
    assert result.error_code == KsefErrorCode.INVALID_TOKEN
    stored = KsefCredential.objects.get(tenant=polish_tenant)
    assert crypto.decrypt_token(polish_tenant.pk, stored.encrypted_token) == "token-to-revoke"


def test_retest_reencrypts_with_newest_key(polish_tenant, settings):
    old_key = settings.KSEF_ENCRYPTION_KEYS
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, "rotating-token")
    old_payload = bytes(KsefCredential.objects.get(tenant=polish_tenant).encrypted_token)

    settings.KSEF_ENCRYPTION_KEYS = f"{base64.b64encode(os.urandom(32)).decode()},{old_key}"
    with patch.object(services, "verify_token", return_value=VALID):
        services.retest_token(polish_tenant, None)

    new_payload = bytes(KsefCredential.objects.get(tenant=polish_tenant).encrypted_token)
    assert new_payload[:4] != old_payload[:4]
    assert crypto.decrypt_token(polish_tenant.pk, new_payload) == "rotating-token"


def test_retest_without_token_reports_not_configured(polish_tenant):
    result = services.retest_token(polish_tenant, None)

    assert result.credential is None
    assert result.error_code == KsefErrorCode.NOT_CONFIGURED


def test_delete_removes_token(polish_tenant):
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, "token-to-delete")

    assert services.delete_token(polish_tenant, None) is True
    assert not KsefCredential.objects.filter(tenant=polish_tenant).exists()
    assert services.delete_token(polish_tenant, None) is False


def _security_events(tenant, event_type):
    return list(SSOAuditLog.objects.filter(tenant=tenant, event_type=event_type))


def test_saving_token_adds_security_log_entry_without_token(polish_tenant):
    token = "secret-token-9876"
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, token)

    [event] = _security_events(polish_tenant, SSOAuditEventType.KSEF_TOKEN_SAVED)
    assert event.success is True
    assert event.metadata["token_hint"] == "9876"
    assert event.metadata["created"] is True
    assert token not in str(event.metadata) and token not in event.event_description


def test_checking_revoked_token_adds_failed_security_log_entry(polish_tenant):
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, "token-to-check")
    with patch.object(services, "verify_token", return_value=INVALID):
        services.retest_token(polish_tenant, None)

    [event] = _security_events(polish_tenant, SSOAuditEventType.KSEF_TOKEN_TESTED)
    assert event.success is False
    assert event.error_message == KsefErrorCode.INVALID_TOKEN
    assert "token-to-check" not in str(event.metadata)


def test_deleting_token_adds_security_log_entry(polish_tenant):
    with patch.object(services, "verify_token", return_value=VALID):
        services.save_token(polish_tenant, None, "token-to-remove")
    services.delete_token(polish_tenant, None)

    [event] = _security_events(polish_tenant, SSOAuditEventType.KSEF_TOKEN_DELETED)
    assert event.success is True
    assert event.metadata["token_hint"] == "move"


def test_security_log_entries_include_token_name(polish_tenant):
    named = TokenCheck(status=KsefCredentialStatus.VALID, token_name="KlarvidoTest")
    with patch.object(services, "verify_token", return_value=named):
        services.save_token(polish_tenant, None, "named-token-7777")
    with patch.object(services, "verify_token", return_value=named):
        services.retest_token(polish_tenant, None)
    services.delete_token(polish_tenant, None)

    [saved] = _security_events(polish_tenant, SSOAuditEventType.KSEF_TOKEN_SAVED)
    [tested] = _security_events(polish_tenant, SSOAuditEventType.KSEF_TOKEN_TESTED)
    [deleted] = _security_events(polish_tenant, SSOAuditEventType.KSEF_TOKEN_DELETED)
    assert saved.metadata["token_name"] == "KlarvidoTest"
    assert tested.metadata["token_name"] == "KlarvidoTest"
    assert deleted.metadata["token_name"] == "KlarvidoTest"
