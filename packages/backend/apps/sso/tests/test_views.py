"""
Tests for the retained shared security endpoints.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status

from apps.sso import models, constants

from . import factories


pytestmark = pytest.mark.django_db


class TestSharedSecurityEndpointBasics:
    """Basic tests for shared security endpoint structure."""

    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_sso_app_urls_load(self):
        """Test that SSO app URLs are properly configured."""
        from apps.sso import urls

        # Verify urlpatterns exist
        assert hasattr(urls, 'urlpatterns')
        assert len(urls.urlpatterns) > 0

    def test_passkey_registration_requires_auth(self, api_client):
        """Test passkey registration requires authentication."""
        url = "/api/sso/passkeys/register/options"

        response = api_client.post(url)

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
