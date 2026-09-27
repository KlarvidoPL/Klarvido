import pytest

from apps.users.strategy import DjangoJWTStrategy

pytestmark = pytest.mark.django_db


def _strategy(session):
    strategy = DjangoJWTStrategy.__new__(DjangoJWTStrategy)
    strategy.session = session
    return strategy


class TestConstructOtpValidateUrl:
    """Regression tests for a bug where the OTP redirect URL was built by appending
    onto the full "next" URL (including its existing path) instead of its origin,
    producing a malformed, doubled-up URL that matched no frontend route - meaning
    a 2FA-enabled user completing OAuth login landed nowhere useful."""

    def test_builds_url_from_origin_not_full_next_path(self, settings):
        settings.OTP_VALIDATE_PATH = "/auth/validate-otp"
        strategy = _strategy({"locale": "pl"})

        result = strategy._construct_otp_validate_url("https://klarvido.com/pl/auth/login")

        assert result == "https://klarvido.com/pl/auth/validate-otp"

    def test_defaults_to_english_locale_when_missing_from_session(self, settings):
        settings.OTP_VALIDATE_PATH = "/auth/validate-otp"
        strategy = _strategy({})

        result = strategy._construct_otp_validate_url("https://klarvido.com/en/auth/signup")

        assert result == "https://klarvido.com/en/auth/validate-otp"
