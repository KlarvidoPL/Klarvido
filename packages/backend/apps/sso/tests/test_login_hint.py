"""
The account signed in at the identity provider must be the email the user entered on the SSO login page.
"""

import base64

import pytest

from apps.sso.views import _ensure_matches_login_hint, _normalize_login_hint, _saml_in_response_to

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


class TestSamlInResponseTo:
    def test_reads_in_response_to_from_response(self):
        xml = b'<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" InResponseTo="_req123"/>'

        assert _saml_in_response_to(base64.b64encode(xml).decode()) == "_req123"

    def test_invalid_response_returns_none(self):
        assert _saml_in_response_to("not-base64-xml!!") is None
