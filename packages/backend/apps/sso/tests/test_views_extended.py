"""Shared security view helper tests; enterprise tests are archived in .disabled."""

from unittest.mock import MagicMock

import pytest

from apps.sso.views import get_client_ip


pytestmark = pytest.mark.django_db


class TestGetClientIp:
    def test_returns_x_forwarded_for_when_present(self):
        request = MagicMock()
        request.META = {"HTTP_X_FORWARDED_FOR": "192.168.1.1, 10.0.0.1", "REMOTE_ADDR": "127.0.0.1"}
        assert get_client_ip(request) == "192.168.1.1"

    def test_returns_remote_addr_when_no_forwarded_for(self):
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "127.0.0.1"}
        assert get_client_ip(request) == "127.0.0.1"
