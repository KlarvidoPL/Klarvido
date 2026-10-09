"""Shared security view helper tests; enterprise tests are archived in .disabled."""

import pytest
from rest_framework.test import APIRequestFactory

from apps.sso.views import get_client_ip


pytestmark = pytest.mark.django_db


class TestGetClientIp:
    """E06: X-Forwarded-For is only trusted through hops configured in TRUSTED_PROXIES - an
    attacker-controlled browser can set this header to anything, so without an explicit trust
    chain it must be ignored (see common.ratelimiting.utils.get_client_ip, which this delegates
    to)."""

    def test_ignores_forwarded_for_without_trusted_proxy_config(self, settings):
        settings.TRUSTED_PROXIES = []
        request = APIRequestFactory().get("/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="192.168.1.1, 10.0.0.1")
        assert get_client_ip(request) == "127.0.0.1"

    def test_trusts_forwarded_for_through_a_configured_proxy(self, settings):
        settings.TRUSTED_PROXIES = ["127.0.0.0/8"]
        request = APIRequestFactory().get("/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="192.168.1.1, 10.0.0.1")
        assert get_client_ip(request) == "10.0.0.1"

    def test_returns_remote_addr_when_no_forwarded_for(self):
        request = APIRequestFactory().get("/", REMOTE_ADDR="127.0.0.1")
        assert get_client_ip(request) == "127.0.0.1"
