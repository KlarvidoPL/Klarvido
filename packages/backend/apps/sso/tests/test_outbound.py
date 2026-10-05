"""
Identity provider URLs are checked before the server calls them, and discovery reveals no organization.
"""

import datetime
import http.server
import socket
import ssl
import threading
from unittest import mock

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from rest_framework import serializers

from apps.sso.schema import SSODiscoveryConnectionType
from apps.sso.serializers import TenantSSOConnectionSerializer, _validate_outbound_urls
from apps.sso.services import outbound
from apps.sso.services.outbound import UnsafeOutboundURL, safe_request, validate_public_url

pytestmark = pytest.mark.django_db

PUBLIC_ADDRESS = "93.184.216.34"


def _resolves_to(*addresses):
    return mock.patch.object(outbound, "_resolve_addresses", return_value=list(addresses))


@pytest.fixture(autouse=True)
def production_settings(settings):
    settings.DEBUG = False


class TestValidatePublicUrl:
    def test_https_to_a_public_address_is_allowed(self):
        with _resolves_to(PUBLIC_ADDRESS):
            assert validate_public_url("https://idp.example.com/.well-known") == "https://idp.example.com/.well-known"

    def test_plain_http_is_refused_for_a_remote_host(self):
        with pytest.raises(UnsafeOutboundURL, match="https"):
            validate_public_url("http://idp.example.com/")

    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.5",
            "172.16.4.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
            "::1",
            "fc00::1",
            "fe80::1",
            "::ffff:169.254.169.254",
        ],
    )
    def test_private_and_internal_addresses_are_refused(self, address):
        with _resolves_to(address):
            with pytest.raises(UnsafeOutboundURL, match="private or internal"):
                validate_public_url("https://idp.example.com/")

    def test_host_that_also_resolves_to_a_private_address_is_refused(self):
        with _resolves_to(PUBLIC_ADDRESS, "10.0.0.5"):
            with pytest.raises(UnsafeOutboundURL, match="private or internal"):
                validate_public_url("https://idp.example.com/")

    def test_unresolvable_host_is_refused(self):
        with mock.patch.object(outbound.socket, "getaddrinfo", side_effect=socket.gaierror):
            with pytest.raises(UnsafeOutboundURL, match="cannot be resolved"):
                validate_public_url("https://no-such-host.invalid/")

    def test_localhost_over_http_is_allowed_in_debug_only(self, settings):
        settings.DEBUG = True
        assert validate_public_url("http://localhost:8180/realms/klarvido") == "http://localhost:8180/realms/klarvido"

        settings.DEBUG = False
        with pytest.raises(UnsafeOutboundURL, match="https"):
            validate_public_url("http://localhost:8180/realms/klarvido")

    def test_url_without_host_is_refused(self):
        with pytest.raises(UnsafeOutboundURL, match="no host"):
            validate_public_url("https:///path")


class TestSafeRequest:
    def test_redirect_is_returned_not_followed(self):
        redirect = mock.Mock(status_code=302, is_redirect=True)
        with _resolves_to(PUBLIC_ADDRESS), mock.patch.object(outbound.requests, "Session") as session_class:
            session_class.return_value.request.return_value = redirect
            response = safe_request("GET", "https://idp.example.com/.well-known")

        assert response is redirect
        assert session_class.return_value.request.call_args.kwargs["allow_redirects"] is False

    def test_private_target_is_never_requested(self):
        with _resolves_to("169.254.169.254"), mock.patch.object(outbound.requests, "Session") as session_class:
            with pytest.raises(UnsafeOutboundURL):
                safe_request("GET", "https://idp.example.com/latest/meta-data")

        session_class.assert_not_called()

    def test_timeout_defaults_when_not_given(self):
        with _resolves_to(PUBLIC_ADDRESS), mock.patch.object(outbound.requests, "Session") as session_class:
            safe_request("POST", "https://idp.example.com/token", data={"grant_type": "authorization_code"})

        request = session_class.return_value.request
        assert request.call_args.kwargs["timeout"] == outbound.REQUEST_TIMEOUT_SECONDS

    def test_connection_is_pinned_to_the_checked_address(self):
        with _resolves_to(PUBLIC_ADDRESS), mock.patch.object(outbound.requests, "Session") as session_class:
            safe_request("GET", "https://idp.example.com/.well-known")

        mount_prefix, adapter = session_class.return_value.mount.call_args.args
        assert mount_prefix == "https://"
        assert adapter.address == PUBLIC_ADDRESS


def _self_signed_certificate(tmp_path, hostname):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / f"{hostname}.pem"
    key_path = tmp_path / f"{hostname}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        )
    )
    return cert_path, key_path


@pytest.fixture
def tls_server(tmp_path):
    """A local HTTPS server. Its certificate is issued for idp.example.test, a name that does not resolve."""
    cert_path, key_path = _self_signed_certificate(tmp_path, "idp.example.test")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, cert_path
    finally:
        server.shutdown()
        server.server_close()


class TestPinnedConnection:
    def test_connects_to_the_checked_address_and_checks_the_hostname(self, tls_server):
        port, cert_path = tls_server
        session = requests.Session()
        session.trust_env = False
        session.mount("https://", outbound.PinnedAddressAdapter("127.0.0.1"))
        try:
            # idp.example.test does not resolve, so the only way this succeeds is through the pinned address
            response = session.get(f"https://idp.example.test:{port}/", verify=str(cert_path), timeout=10)
        finally:
            session.close()

        assert response.status_code == 200
        assert response.text == "ok"

    def test_certificate_for_another_name_is_refused(self, tls_server):
        port, cert_path = tls_server
        session = requests.Session()
        session.trust_env = False
        session.mount("https://", outbound.PinnedAddressAdapter("127.0.0.1"))
        try:
            with pytest.raises(requests.exceptions.SSLError):
                session.get(f"https://localhost:{port}/", verify=str(cert_path), timeout=10)
        finally:
            session.close()


class TestSerializerRejectsInternalUrls:
    def test_private_issuer_is_rejected_on_save(self):
        with _resolves_to("169.254.169.254"):
            with pytest.raises(serializers.ValidationError) as exc:
                TenantSSOConnectionSerializer().validate({"oidc_issuer": "https://169.254.169.254/"})

        assert "oidc_issuer" in exc.value.detail

    def test_urn_entity_id_is_not_resolved(self):
        with mock.patch.object(outbound, "_resolve_addresses") as resolve:
            _validate_outbound_urls({"saml_entity_id": "urn:example:idp"})

        resolve.assert_not_called()


class TestDiscoveryExposesNoOrganization:
    def test_discovery_connection_has_only_login_fields(self):
        assert set(SSODiscoveryConnectionType._meta.fields) == {"id", "name", "type", "login_url"}
