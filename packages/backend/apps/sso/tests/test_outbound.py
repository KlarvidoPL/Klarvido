"""
Identity provider URLs are checked before the server calls them, and discovery reveals no organization.
"""

import socket
from unittest import mock

import pytest
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
        with _resolves_to(PUBLIC_ADDRESS), mock.patch.object(
            outbound.requests, "request", return_value=redirect
        ) as request:
            response = safe_request("GET", "https://idp.example.com/.well-known")

        assert response is redirect
        assert request.call_args.kwargs["allow_redirects"] is False

    def test_private_target_is_never_requested(self):
        with _resolves_to("169.254.169.254"), mock.patch.object(outbound.requests, "request") as request:
            with pytest.raises(UnsafeOutboundURL):
                safe_request("GET", "https://idp.example.com/latest/meta-data")

        request.assert_not_called()

    def test_timeout_defaults_when_not_given(self):
        with _resolves_to(PUBLIC_ADDRESS), mock.patch.object(outbound.requests, "request") as request:
            safe_request("POST", "https://idp.example.com/token", data={"grant_type": "authorization_code"})

        assert request.call_args.kwargs["timeout"] == outbound.REQUEST_TIMEOUT_SECONDS


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
