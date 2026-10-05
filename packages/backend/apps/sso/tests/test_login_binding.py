"""
Login requests are bound to the browser that started them (login CSRF), SAML responses must answer
exactly that request, be addressed to this SP and come from the configured IdP, and OIDC logins need
a verified email.
"""

import base64
from unittest import mock

import pytest
from django.core.cache import cache

from apps.sso import constants
from apps.sso.services import OIDCService, SAMLService
from apps.sso.views import OIDC_STATE_COOKIE, SAML_REQUEST_COOKIE

pytestmark = pytest.mark.django_db

SAML_PROTOCOL_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"


def _saml_response(service, in_response_to="_req", audience=True, destination=None, recipient=None, issuer=None):
    """A SAML response that is correct unless a value is overridden. An empty string leaves that value out."""
    acs_url = service.get_acs_url()
    destination = acs_url if destination is None else destination
    recipient = acs_url if recipient is None else recipient
    issuer = service.connection.saml_entity_id if issuer is None else issuer

    irt = f' InResponseTo="{in_response_to}"' if in_response_to else ""
    dest_attr = f' Destination="{destination}"' if destination else ""
    recipient_attr = f' Recipient="{recipient}"' if recipient else ""
    issuer_xml = f"<saml:Issuer>{issuer}</saml:Issuer>" if issuer else ""
    audience_xml = (
        "<saml:AudienceRestriction>"
        f"<saml:Audience>{service.get_sp_entity_id()}</saml:Audience>"
        "</saml:AudienceRestriction>"
        if audience
        else ""
    )
    return (
        f'<samlp:Response xmlns:samlp="{SAML_PROTOCOL_NS}" xmlns:saml="{SAML_ASSERTION_NS}" '
        f'ID="_resp"{irt}{dest_attr} Version="2.0">'
        f"{issuer_xml}"
        '<samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>'
        '<saml:Assertion ID="_assertion" Version="2.0">'
        f"{issuer_xml}"
        "<saml:Subject><saml:SubjectConfirmation>"
        f"<saml:SubjectConfirmationData{recipient_attr}{irt}/>"
        "</saml:SubjectConfirmation></saml:Subject>"
        f"<saml:Conditions>{audience_xml}</saml:Conditions>"
        "</saml:Assertion>"
        "</samlp:Response>"
    )


def _parse_with_signature_skipped(service, xml, request_id):
    """Run parse_saml_response past the certificate and signature steps, which are covered elsewhere."""
    encoded = base64.b64encode(xml.encode()).decode()
    with mock.patch.object(SAMLService, "_load_idp_certificate", return_value=object()), mock.patch.object(
        SAMLService, "_verify_xml_signature", return_value=None
    ):
        return service.parse_saml_response(encoded, request_id=request_id)


class TestSamlLoginBinding:
    def test_login_binds_the_request_to_this_browser(self, api_client, tenant_sso_connection):
        tenant_sso_connection.status = constants.SSOConnectionStatus.ACTIVE
        tenant_sso_connection.save()

        with mock.patch.object(
            SAMLService, "create_authn_request", return_value=("https://idp.example.com/sso", "_req-abc")
        ):
            response = api_client.get(f"/api/sso/saml/{tenant_sso_connection.id}/login")

        assert response.status_code == 302
        cookie = response.cookies[SAML_REQUEST_COOKIE]
        assert cookie.value == "_req-abc"
        assert cookie["path"] == f"/api/sso/saml/{tenant_sso_connection.id}/acs"
        assert cookie["samesite"] == "None"
        assert cookie["secure"] is True
        assert cookie["httponly"] is True

    def test_acs_without_the_login_cookie_is_rejected(self, api_client, tenant_sso_connection):
        response = api_client.post(
            f"/api/sso/saml/{tenant_sso_connection.id}/acs",
            {"SAMLResponse": "PHNhbWw+PC9zYW1sPg=="},
        )

        assert response.status_code == 302
        assert "code=sso_request_expired" in response["Location"]

    def test_acs_rejects_a_request_started_by_someone_else(self, api_client, tenant_sso_connection):
        """An attacker's own pending request, found in the shared cache, must not be accepted without the cookie."""
        cache.set(
            "saml_request__attacker",
            {"connection_id": str(tenant_sso_connection.id), "relay_state": "/", "login_hint": None},
            timeout=600,
        )

        response = api_client.post(
            f"/api/sso/saml/{tenant_sso_connection.id}/acs",
            {"SAMLResponse": "PHNhbWw+PC9zYW1sPg=="},
        )

        assert "code=sso_request_expired" in response["Location"]

    def test_acs_rejects_a_request_stored_for_another_connection(self, api_client, tenant_sso_connection):
        cache.set(
            "saml_request__other",
            {"connection_id": "some-other-connection", "relay_state": "/", "login_hint": None},
            timeout=600,
        )
        api_client.cookies[SAML_REQUEST_COOKIE] = "_other"

        response = api_client.post(
            f"/api/sso/saml/{tenant_sso_connection.id}/acs",
            {"SAMLResponse": "PHNhbWw+PC9zYW1sPg=="},
        )

        assert "code=sso_request_expired" in response["Location"]

    def test_acs_clears_the_login_cookie(self, api_client, tenant_sso_connection):
        response = api_client.post(f"/api/sso/saml/{tenant_sso_connection.id}/acs", {"SAMLResponse": "x"})

        assert response.cookies[SAML_REQUEST_COOKIE]["max-age"] == 0


class TestSamlStrictResponseChecks:
    @pytest.fixture
    def saml_service(self, tenant_sso_connection):
        return SAMLService(tenant_sso_connection)

    def test_response_without_in_response_to_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="")

        with pytest.raises(ValueError, match="Request ID missing"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-1")

    def test_response_answering_another_request_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-other")

        with pytest.raises(ValueError, match="Request ID mismatch"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-1")

    def test_assertion_without_audience_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-2", audience=False)

        with pytest.raises(ValueError, match="audience mismatch"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-2")

    def test_assertion_for_another_service_provider_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-3", audience=False).replace(
            "</saml:Conditions>",
            "<saml:AudienceRestriction><saml:Audience>https://other-sp.example.com</saml:Audience>"
            "</saml:AudienceRestriction></saml:Conditions>",
        )

        with pytest.raises(ValueError, match="audience mismatch"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-3")

    def test_wrong_destination_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-5", destination="https://evil.example.com/acs")

        with pytest.raises(ValueError, match="Destination"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-5")

    def test_missing_destination_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-6", destination="")

        with pytest.raises(ValueError, match="Destination"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-6")

    def test_wrong_recipient_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-7", recipient="https://evil.example.com/acs")

        with pytest.raises(ValueError, match="Recipient"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-7")

    def test_wrong_issuer_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-8", issuer="https://another-idp.example.com")

        with pytest.raises(ValueError, match="Issuer"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-8")

    def test_missing_issuer_is_rejected(self, saml_service):
        xml = _saml_response(saml_service, in_response_to="_req-9", issuer="")

        with pytest.raises(ValueError, match="Issuer"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-9")

    def test_already_consumed_request_is_rejected(self, saml_service):
        cache.add("saml_request_consumed__req-4", True, timeout=60)
        xml = _saml_response(saml_service, in_response_to="_req-4")

        with pytest.raises(ValueError, match="already processed"):
            _parse_with_signature_skipped(saml_service, xml, request_id="_req-4")


class TestOidcEmailVerified:
    def _process(self, connection, claims):
        service = OIDCService(connection)
        with mock.patch.object(
            OIDCService, "exchange_code_for_tokens", return_value={"id_token": "token"}
        ), mock.patch.object(OIDCService, "validate_id_token", return_value=claims):
            return service.process_callback(
                code="code",
                state="state",
                stored_state="state",
                stored_nonce="nonce",
                code_verifier="verifier",
            )

    def test_missing_email_verified_is_refused(self, oidc_sso_connection):
        with pytest.raises(ValueError, match="not verified"):
            self._process(oidc_sso_connection, {"sub": "u1", "email": "ceo@example.com"})

    def test_false_email_verified_is_refused(self, oidc_sso_connection):
        with pytest.raises(ValueError, match="not verified"):
            self._process(oidc_sso_connection, {"sub": "u1", "email": "ceo@example.com", "email_verified": False})

    def test_true_email_verified_is_accepted(self, oidc_sso_connection):
        attrs = self._process(oidc_sso_connection, {"sub": "u1", "email": "ceo@example.com", "email_verified": True})

        assert attrs["email"] == "ceo@example.com"

    def test_string_true_email_verified_is_accepted(self, oidc_sso_connection):
        attrs = self._process(oidc_sso_connection, {"sub": "u1", "email": "ceo@example.com", "email_verified": "true"})

        assert attrs["email"] == "ceo@example.com"

    def test_admin_opt_in_accepts_missing_email_verified(self, oidc_sso_connection):
        oidc_sso_connection.oidc_trust_unverified_email = True
        oidc_sso_connection.save()

        attrs = self._process(oidc_sso_connection, {"sub": "u1", "email": "ceo@example.com"})

        assert attrs["email"] == "ceo@example.com"


class TestOidcStateBinding:
    def test_login_binds_the_state_to_this_browser(self, api_client, oidc_sso_connection):
        oidc_sso_connection.status = constants.SSOConnectionStatus.ACTIVE
        oidc_sso_connection.save()

        with mock.patch.object(OIDCService, "generate_pkce", return_value=("verifier", "challenge")), mock.patch.object(
            OIDCService,
            "create_authorization_url",
            return_value=("https://idp.example.com/auth", {"state": "state-1", "nonce": "nonce-1"}),
        ):
            response = api_client.get(f"/api/sso/oidc/{oidc_sso_connection.id}/login")

        assert response.status_code == 302
        cookie = response.cookies[OIDC_STATE_COOKIE]
        assert cookie.value == "state-1"
        assert cookie["path"] == f"/api/sso/oidc/{oidc_sso_connection.id}/callback"
        assert cookie["samesite"] == "Lax"
        assert cookie["httponly"] is True

    def test_callback_without_the_state_cookie_is_rejected(self, api_client, oidc_sso_connection):
        cache.set("oidc_state_state-2", {"connection_id": str(oidc_sso_connection.id)}, timeout=600)

        response = api_client.get(
            f"/api/sso/oidc/{oidc_sso_connection.id}/callback", {"code": "code", "state": "state-2"}
        )

        assert response.status_code == 400

    def test_callback_with_a_different_state_cookie_is_rejected(self, api_client, oidc_sso_connection):
        cache.set("oidc_state_state-3", {"connection_id": str(oidc_sso_connection.id)}, timeout=600)
        api_client.cookies[OIDC_STATE_COOKIE] = "some-other-state"

        response = api_client.get(
            f"/api/sso/oidc/{oidc_sso_connection.id}/callback", {"code": "code", "state": "state-3"}
        )

        assert response.status_code == 400
