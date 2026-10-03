"""
Live check of a KSeF token against the KSeF 2.0 API (authentication with a KSeF token).

Flow (see https://github.com/CIRFMF/ksef-docs):
  1. GET  /security/public-key-certificates      -> certificate with usage KsefTokenEncryption
  2. POST /auth/challenge                         -> challenge + timestampMs
  3. POST /auth/ksef-token                        -> encryptedToken = RSA-OAEP-SHA256("<token>|<timestampMs>")
  4. GET  /auth/{referenceNumber}                 -> poll until status 200 (success) or a failure code
  5. POST /auth/token/redeem                      -> proves the token works; the session is then closed again

The token is only ever held in memory for the duration of this call and is never logged.
"""

import base64
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .constants import KSEF_BASE_URLS, KsefCredentialStatus, KsefEnvironment, KsefErrorCode

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = httpx.Timeout(10.0)
POLL_ATTEMPTS = 10
POLL_INTERVAL_SECONDS = 1.0

# Status codes of GET /auth/{referenceNumber} (KSeF "StatusInfo")
STATUS_IN_PROGRESS = 100
STATUS_SUCCESS = 200
STATUS_NO_PERMISSIONS = 415
STATUS_REVOKED = 425
STATUS_UNAVAILABLE = {500, 550}


@dataclass(frozen=True)
class TokenCheck:
    status: str  # KsefCredentialStatus value
    error_code: str = ""  # KsefErrorCode value, empty when valid
    token_name: str = ""  # the name given to the token in KSeF (its "description"), when readable


class _Rejected(Exception):
    """KSeF definitively rejected the token."""

    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


class _Unavailable(Exception):
    """KSeF could not give an answer (network, 5xx, 429, timeout)."""


def _base_url() -> str:
    try:
        environment = KsefEnvironment(getattr(settings, "KSEF_ENVIRONMENT", "test"))
    except ValueError as e:
        raise ImproperlyConfigured("KSEF_ENVIRONMENT must be one of: test, demo, prod") from e
    return KSEF_BASE_URLS[environment]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _request(http: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    response = http.request(method, path, **kwargs)
    if response.status_code == 429 or response.status_code >= 500:
        raise _Unavailable(f"{method} {path} answered {response.status_code}")
    return response


def _has_usage(entry: dict, usage: str) -> bool:
    # The production API returns "usage" as a list (["KsefTokenEncryption"]); accept a plain string too.
    value = entry.get("usage")
    values = value if isinstance(value, list) else [value]
    return usage in values


def _encryption_certificate_key(http: httpx.Client):
    response = _request(http, "GET", "/security/public-key-certificates")
    if response.status_code != 200:
        raise _Unavailable(f"public key certificates answered {response.status_code}")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    # validTo is ISO-8601 with 7 fractional digits, so compare on the first 19 characters (seconds precision).
    candidates = [
        entry
        for entry in response.json()
        if _has_usage(entry, "KsefTokenEncryption") and entry.get("validTo", "")[:19] > now
    ]
    if not candidates:
        raise _Unavailable("no active KsefTokenEncryption certificate")
    entry = max(candidates, key=lambda item: item.get("validFrom", ""))
    certificate = x509.load_der_x509_certificate(base64.b64decode(entry["certificate"]))
    return entry["publicKeyId"], certificate.public_key()


def _encrypt_token(public_key, token: str, timestamp_ms: int) -> str:
    plaintext = f"{token}|{timestamp_ms}".encode()
    encrypted = public_key.encrypt(
        plaintext,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return base64.b64encode(encrypted).decode()


def _wait_for_authentication(http: httpx.Client, reference_number: str, auth_token: str) -> None:
    for _ in range(POLL_ATTEMPTS):
        response = _request(http, "GET", f"/auth/{reference_number}", headers=_bearer(auth_token))
        if response.status_code >= 400:
            raise _Rejected(KsefErrorCode.INVALID_TOKEN)
        code = response.json().get("status", {}).get("code")
        if code == STATUS_SUCCESS:
            return
        if code == STATUS_IN_PROGRESS:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if code == STATUS_NO_PERMISSIONS:
            raise _Rejected(KsefErrorCode.NO_PERMISSIONS)
        if code in STATUS_UNAVAILABLE:
            raise _Unavailable(f"authentication status {code}")
        # Any other failure code (450 bad token, 425 revoked, 460 certificate, 480 blocked, ...) is a rejection.
        logger.info("KSeF authentication failed with status code %s", code)
        raise _Rejected(KsefErrorCode.INVALID_TOKEN)
    raise _Unavailable("authentication still in progress after polling")


def _fetch_token_name(http: httpx.Client, access_token: str) -> str:
    """
    Name of the token used to log in. A caller without CredentialsRead only sees the token it authenticated with,
    so the list holds exactly our token. Best effort: failure just means no name.
    """
    try:
        response = _request(http, "GET", "/tokens", headers=_bearer(access_token))
        if response.status_code != 200:
            return ""
        tokens = response.json().get("tokens", [])
        if len(tokens) != 1:
            return ""
        return (tokens[0].get("description") or "").strip()[:255]
    except (httpx.HTTPError, _Unavailable, ValueError, KeyError, TypeError, AttributeError):
        logger.info("Could not read the KSeF token name; continuing without it")
        return ""


def _close_session(http: httpx.Client, access_token: str) -> None:
    """Best effort: end the session opened by the check so it does not linger."""
    try:
        _request(http, "DELETE", "/auth/sessions/current", headers=_bearer(access_token))
    except (httpx.HTTPError, _Unavailable):
        logger.warning("Could not close the KSeF check session; it will expire on its own")


def verify_token(nip: str, token: str, http_client: Optional[httpx.Client] = None) -> TokenCheck:
    """
    Check that a KSeF token authenticates for the given NIP.

    Returns VALID, INVALID (KSeF said no, nothing should be stored) or UNVERIFIED (KSeF could not be reached).
    """
    base_url = _base_url()
    owns_client = http_client is None
    http = http_client or httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT)
    try:
        public_key_id, public_key = _encryption_certificate_key(http)

        challenge_response = _request(http, "POST", "/auth/challenge")
        if challenge_response.status_code != 200:
            raise _Unavailable(f"challenge answered {challenge_response.status_code}")
        challenge = challenge_response.json()

        init_response = _request(
            http,
            "POST",
            "/auth/ksef-token",
            json={
                "challenge": challenge["challenge"],
                "contextIdentifier": {"type": "Nip", "value": nip},
                "encryptedToken": _encrypt_token(public_key, token, challenge["timestampMs"]),
                "publicKeyId": public_key_id,
            },
        )
        if init_response.status_code >= 400:
            raise _Rejected(KsefErrorCode.INVALID_TOKEN)
        init_body = init_response.json()
        reference_number = init_body["referenceNumber"]
        auth_token = init_body["authenticationToken"]["token"]

        _wait_for_authentication(http, reference_number, auth_token)

        redeem_response = _request(http, "POST", "/auth/token/redeem", headers=_bearer(auth_token))
        if redeem_response.status_code != 200:
            raise _Unavailable(f"redeem answered {redeem_response.status_code}")
        access_token = redeem_response.json()["accessToken"]["token"]
        token_name = _fetch_token_name(http, access_token)
        _close_session(http, access_token)

        return TokenCheck(status=KsefCredentialStatus.VALID, token_name=token_name)
    except _Rejected as e:
        return TokenCheck(status=KsefCredentialStatus.INVALID, error_code=e.error_code)
    except (_Unavailable, httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        # Log the exception type only: messages from httpx can echo request details.
        logger.warning("KSeF token check unavailable: %s", type(e).__name__)
        return TokenCheck(status=KsefCredentialStatus.UNVERIFIED, error_code=KsefErrorCode.SERVICE_UNAVAILABLE)
    finally:
        if owns_client:
            http.close()
