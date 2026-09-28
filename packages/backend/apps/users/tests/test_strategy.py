import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.strategy import DjangoJWTStrategy
from config import settings as config_settings

pytestmark = pytest.mark.django_db


class _FakeSession(dict):
    def flush(self):
        self.clear()


def _strategy(session=None):
    strategy = DjangoJWTStrategy.__new__(DjangoJWTStrategy)
    strategy.session = _FakeSession(session or {})
    strategy.refresh_token = None
    strategy.otp_auth_token = None
    strategy.is_new_signup = False
    strategy.session_id = None
    return strategy


class TestConstructOtpValidateUrl:
    """Regression tests for a bug where the OTP redirect URL was built by appending
    onto the full "next" URL (including its existing path) instead of its origin,
    producing a malformed, doubled-up URL that matched no frontend route - meaning
    a 2FA-enabled user completing OAuth login landed nowhere useful.

    strategy.py reads settings via `from config import settings` (the raw settings
    module), not `django.conf.settings` - the pytest-django `settings` fixture
    patches the latter only, so it has no effect here. `monkeypatch.setattr` on the
    actual module object is what's needed to override a value for these tests.
    """

    def test_builds_url_from_origin_not_full_next_path(self, monkeypatch):
        monkeypatch.setattr(config_settings, "OTP_VALIDATE_PATH", "/auth/validate-otp")
        strategy = _strategy({"locale": "pl"})

        result = strategy._construct_otp_validate_url("https://klarvido.com/pl/auth/login")

        assert result == "https://klarvido.com/pl/auth/validate-otp"

    def test_defaults_to_english_locale_when_missing_from_session(self, monkeypatch):
        monkeypatch.setattr(config_settings, "OTP_VALIDATE_PATH", "/auth/validate-otp")
        strategy = _strategy({})

        result = strategy._construct_otp_validate_url("https://klarvido.com/en/auth/signup")

        assert result == "https://klarvido.com/en/auth/validate-otp"


class TestRedirectSetsNewSignupCookie:
    """The frontend needs a signal to show the welcome modal after a brand new
    OAuth signup - unlike the password-signup flow (a client-side mutation that
    can trigger it directly in its onCompleted callback), OAuth signup is a full
    backend redirect that can land on any page, so a short-lived cookie is used
    instead of a query param a client-side redirect could drop along the way."""

    def test_sets_cookie_on_new_signup(self, user):
        strategy = _strategy()
        strategy.set_jwt(RefreshToken.for_user(user))
        strategy.set_is_new_signup(True)

        response = strategy.redirect("https://klarvido.com/pl/auth/login")

        cookie = response.cookies.get(config_settings.NEW_SIGNUP_COOKIE)
        assert cookie is not None
        assert cookie.value == "1"

    def test_does_not_set_cookie_for_returning_user(self, user):
        strategy = _strategy()
        strategy.set_jwt(RefreshToken.for_user(user))
        strategy.set_is_new_signup(False)

        response = strategy.redirect("https://klarvido.com/pl/auth/login")

        assert config_settings.NEW_SIGNUP_COOKIE not in response.cookies

    def test_cookie_scoped_to_parent_domain_when_configured(self, monkeypatch, user):
        """Regression test: the cookie is set from a response on the API's own
        subdomain (api.klarvido.com) but must be readable by frontend JS running
        on the webapp's subdomain (klarvido.com) - without an explicit shared
        parent-domain scope, the browser accepts the cookie fine but the webapp's
        document.cookie can never see it, silently breaking the welcome modal."""
        monkeypatch.setattr(config_settings, "PARENT_HOST", "klarvido.com")
        strategy = _strategy()
        strategy.set_jwt(RefreshToken.for_user(user))
        strategy.set_is_new_signup(True)

        response = strategy.redirect("https://klarvido.com/pl/auth/login")

        cookie = response.cookies[config_settings.NEW_SIGNUP_COOKIE]
        assert cookie["domain"] == ".klarvido.com"

    def test_cookie_not_domain_scoped_in_local_dev(self, monkeypatch, user):
        monkeypatch.setattr(config_settings, "PARENT_HOST", "")
        strategy = _strategy()
        strategy.set_jwt(RefreshToken.for_user(user))
        strategy.set_is_new_signup(True)

        response = strategy.redirect("http://localhost:5001/en/auth/login")

        cookie = response.cookies[config_settings.NEW_SIGNUP_COOKIE]
        assert cookie["domain"] == ""
