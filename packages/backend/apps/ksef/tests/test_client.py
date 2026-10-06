import base64
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from apps.ksef import client
from apps.ksef.constants import KsefCredentialStatus, KsefErrorCode

pytestmark = pytest.mark.django_db

NIP = "5252344078"
TOKEN = "secret-token-value"
TIMESTAMP_MS = 1700000000000


def _certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "KSeF test")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    der = base64.b64encode(certificate.public_bytes(serialization.Encoding.DER)).decode()
    return key, der


def _mock_ksef(
    private_key,
    der_certificate,
    *,
    auth_codes=(200,),
    redeem_status=200,
    fail=None,
    captured=None,
    tokens_status=200,
    token_description="KlarvidoTest",
    invoices_status=200,
):
    """Mock KSeF endpoints. auth_codes is the sequence of StatusInfo codes returned by GET /auth/{ref}."""
    codes = list(auth_codes)

    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise fail
        path = request.url.path
        if request.method == "GET" and path == "/v2/security/public-key-certificates":
            return httpx.Response(
                200,
                json=[
                    {
                        "certificate": der_certificate,
                        "certificateId": "AAAA",
                        "publicKeyId": "K" * 44,
                        "usage": "KsefTokenEncryption",
                        "validFrom": "2020-01-01T00:00:00.0000000",
                        "validTo": "2999-01-01T00:00:00.0000000",
                    }
                ],
            )
        if request.method == "POST" and path == "/v2/auth/challenge":
            return httpx.Response(
                200, json={"challenge": "c" * 36, "timestamp": "x", "timestampMs": TIMESTAMP_MS, "clientIp": "1.2.3.4"}
            )
        if request.method == "POST" and path == "/v2/auth/ksef-token":
            body = json.loads(request.content)
            if captured is not None:
                captured["body"] = body
            return httpx.Response(
                202, json={"referenceNumber": "REF", "authenticationToken": {"token": "AUTH", "validUntil": "x"}}
            )
        if request.method == "GET" and path == "/v2/auth/REF":
            return httpx.Response(200, json={"status": {"code": codes.pop(0), "description": "x"}})
        if request.method == "POST" and path == "/v2/auth/token/redeem":
            if redeem_status != 200:
                return httpx.Response(redeem_status, json={})
            return httpx.Response(
                200,
                json={
                    "accessToken": {"token": "ACCESS", "validUntil": "x"},
                    "refreshToken": {"token": "R", "validUntil": "x"},
                },
            )
        if request.method == "GET" and path == "/v2/tokens":
            if tokens_status != 200:
                return httpx.Response(tokens_status, json={})
            return httpx.Response(
                200,
                json={
                    "tokens": [{"referenceNumber": "T1", "description": token_description, "status": "Active"}],
                    "continuationToken": None,
                },
            )
        if request.method == "POST" and path == "/v2/invoices/query/metadata":
            if captured is not None:
                captured["invoice_query"] = json.loads(request.content)
                captured["invoice_authorization"] = request.headers["Authorization"]
                captured["invoice_page_size"] = request.url.params["pageSize"]
            return httpx.Response(invoices_status, json={"invoices": [], "hasMore": False, "isTruncated": False})
        if request.method == "DELETE" and path == "/v2/auth/sessions/current":
            if captured is not None:
                captured["closed_with"] = request.headers["Authorization"]
            return httpx.Response(204)
        return httpx.Response(404, json={})

    return httpx.Client(base_url="https://api-test.ksef.mf.gov.pl/v2", transport=httpx.MockTransport(handler))


@pytest.fixture
def certificate():
    return _certificate()


@pytest.fixture(autouse=True)
def no_polling_sleep(monkeypatch):
    monkeypatch.setattr(client, "POLL_INTERVAL_SECONDS", 0)


def test_valid_token_sends_encrypted_token_in_expected_format(certificate):
    private_key, der = certificate
    captured = {}

    result = client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, captured=captured))

    assert result.status == KsefCredentialStatus.VALID
    assert result.error_code == ""
    body = captured["body"]
    assert body["contextIdentifier"] == {"type": "Nip", "value": NIP}
    assert body["publicKeyId"] == "K" * 44
    plaintext = private_key.decrypt(
        base64.b64decode(body["encryptedToken"]),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    assert plaintext == f"{TOKEN}|{TIMESTAMP_MS}".encode()
    assert captured["closed_with"] == "Bearer ACCESS"
    assert captured["invoice_authorization"] == "Bearer ACCESS"
    assert captured["invoice_page_size"] == "10"
    assert captured["invoice_query"]["subjectType"] == "Subject1"
    assert captured["invoice_query"]["dateRange"]["dateType"] == "PermanentStorage"


@pytest.mark.parametrize(
    "http_status,status,error_code",
    [
        (403, KsefCredentialStatus.INVALID, KsefErrorCode.INVOICE_READ_MISSING),
        (401, KsefCredentialStatus.INVALID, KsefErrorCode.INVALID_TOKEN),
        (429, KsefCredentialStatus.UNVERIFIED, KsefErrorCode.SERVICE_UNAVAILABLE),
        (503, KsefCredentialStatus.UNVERIFIED, KsefErrorCode.SERVICE_UNAVAILABLE),
        (400, KsefCredentialStatus.UNVERIFIED, KsefErrorCode.SERVICE_UNAVAILABLE),
    ],
)
def test_invoice_read_check_failure_never_marks_token_valid_and_closes_session(
    certificate, http_status, status, error_code
):
    private_key, der = certificate
    captured = {}
    result = client.verify_token(
        NIP, TOKEN, http_client=_mock_ksef(private_key, der, captured=captured, invoices_status=http_status)
    )
    assert result.status == status
    assert result.error_code == error_code
    assert captured["closed_with"] == "Bearer ACCESS"


def test_accepts_usage_returned_as_list(certificate):
    # Production returns "usage" as a list; the test mock above uses a string.
    private_key, der = certificate
    http = _mock_ksef(private_key, der)
    original = http._transport.handler

    def list_usage(request):
        response = original(request)
        if request.url.path == "/v2/security/public-key-certificates":
            body = json.loads(response.content)
            body[0]["usage"] = ["KsefTokenEncryption"]
            return httpx.Response(200, json=body)
        return response

    http._transport = httpx.MockTransport(list_usage)

    result = client.verify_token(NIP, TOKEN, http_client=http)

    assert result.status == KsefCredentialStatus.VALID


def test_returns_token_name_from_ksef(certificate):
    private_key, der = certificate

    result = client.verify_token(
        NIP, TOKEN, http_client=_mock_ksef(private_key, der, token_description="Klarvido prod")
    )

    assert result.status == KsefCredentialStatus.VALID
    assert result.token_name == "Klarvido prod"


def test_token_list_failure_still_verifies_without_name(certificate):
    private_key, der = certificate

    result = client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, tokens_status=403))

    assert result.status == KsefCredentialStatus.VALID
    assert result.token_name == ""


def test_polls_while_in_progress(certificate):
    private_key, der = certificate

    result = client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, auth_codes=(100, 100, 200)))

    assert result.status == KsefCredentialStatus.VALID


@pytest.mark.parametrize("code", [450, 425, 460, 480])
def test_failure_codes_reject_token(certificate, code):
    private_key, der = certificate

    result = client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, auth_codes=(code,)))

    assert result.status == KsefCredentialStatus.INVALID
    assert result.error_code == KsefErrorCode.INVALID_TOKEN


def test_no_permissions_is_reported_as_such(certificate):
    private_key, der = certificate

    result = client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, auth_codes=(415,)))

    assert result.status == KsefCredentialStatus.INVALID
    assert result.error_code == KsefErrorCode.NO_PERMISSIONS


def test_server_error_is_unverified_not_invalid(certificate):
    private_key, der = certificate
    http = _mock_ksef(private_key, der)

    def unavailable(request):
        return httpx.Response(503, json={})

    http._transport = httpx.MockTransport(unavailable)

    result = client.verify_token(NIP, TOKEN, http_client=http)

    assert result.status == KsefCredentialStatus.UNVERIFIED
    assert result.error_code == KsefErrorCode.SERVICE_UNAVAILABLE


def test_network_error_is_unverified(certificate):
    private_key, der = certificate

    result = client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, fail=httpx.ConnectError("down")))

    assert result.status == KsefCredentialStatus.UNVERIFIED
    assert result.error_code == KsefErrorCode.SERVICE_UNAVAILABLE


def test_token_is_never_logged(certificate, caplog):
    private_key, der = certificate
    caplog.set_level("DEBUG")

    client.verify_token(NIP, TOKEN, http_client=_mock_ksef(private_key, der, auth_codes=(450,)))

    assert TOKEN not in caplog.text
