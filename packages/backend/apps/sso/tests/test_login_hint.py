"""
The account signed in at the identity provider must be the email the user entered on the SSO login page.
"""

import pytest

from apps.sso.views import _ensure_matches_login_hint, _normalize_login_hint

pytestmark = pytest.mark.django_db


class TestNormalizeLoginHint:
    def test_trims_and_lowercases(self):
        assert _normalize_login_hint("  Test@Example.com ") == "test@example.com"

    def test_empty_becomes_none(self):
        assert _normalize_login_hint("") is None
        assert _normalize_login_hint("   ") is None
        assert _normalize_login_hint(None) is None


class TestEnsureMatchesLoginHint:
    def test_without_hint_any_account_is_accepted(self):
        _ensure_matches_login_hint(None, "anyone@example.com")

    def test_same_email_ignoring_case_is_accepted(self):
        _ensure_matches_login_hint("test23@example.com", "Test23@Example.com")

    def test_different_account_is_rejected(self):
        with pytest.raises(ValueError, match="does not match"):
            _ensure_matches_login_hint("test23@example.com", "test@example.com")

    def test_missing_email_is_rejected_when_hint_given(self):
        with pytest.raises(ValueError, match="does not match"):
            _ensure_matches_login_hint("test23@example.com", None)


class TestAccountMismatchErrorCode:
    def test_mismatch_maps_to_account_mismatch_code(self):
        from apps.sso.security import get_safe_error_code

        error = ValueError("Signed-in account does not match the email entered for SSO login")

        assert get_safe_error_code(error) == "account_mismatch"

    def test_error_redirect_points_at_the_translated_error_page(self, settings):
        from apps.sso.views import _sso_error_redirect

        settings.WEB_APP_URL = "http://localhost:3000/"

        response = _sso_error_redirect("account_mismatch")

        assert response.status_code == 302
        assert response["Location"] == "http://localhost:3000/en/auth/sso/error?code=account_mismatch"


class TestIdentityProviderLogoutUrls:
    def test_oidc_logout_url_carries_the_id_token_hint(self):
        from unittest import mock

        from apps.sso.services.oidc import OIDCService

        connection = mock.Mock(oidc_client_id="klarvido")
        service = OIDCService(connection)
        with mock.patch.object(
            service, "discover_configuration", return_value={"end_session_endpoint": "https://idp/logout"}
        ):
            url = service.build_logout_url("https://app/login", id_token_hint="token-123")

        assert url.startswith("https://idp/logout?")
        assert "id_token_hint=token-123" in url
        assert "client_id=klarvido" in url

    def test_saml_logout_url_is_empty_when_idp_has_no_logout_endpoint(self):
        from unittest import mock

        from apps.sso.services.saml import SAMLService

        connection = mock.Mock(saml_entity_id="https://idp/realms/x", tenant=None)
        service = SAMLService(connection)
        response = mock.Mock()
        response.json.return_value = {}
        with mock.patch("apps.sso.services.saml.requests.get", return_value=response):
            assert service.build_logout_url("https://app/login") == ""
