"""
Tests for SSO services.
"""

import pytest
from datetime import timedelta
from django.conf import settings
from django.test import RequestFactory
from django.utils import timezone

from apps.sso.services.sessions import SessionService
from apps.sso.tasks import cleanup_expired_sessions
from apps.sso import models

from . import factories


pytestmark = pytest.mark.django_db


class TestSSOSessionManager:
    """Tests for SSO session manager."""

    def test_get_active_for_user(self, user):
        """Test getting active sessions for a user."""
        active_session = factories.SSOSessionFactory(
            user=user,
            is_active=True,
            expires_at=timezone.now() + timedelta(days=7),
        )
        inactive_session = factories.SSOSessionFactory(
            user=user,
            is_active=False,
        )

        active_sessions = models.SSOSession.objects.get_active_for_user(user)

        assert active_session in active_sessions
        assert inactive_session not in active_sessions

    def test_revoke_all_for_user(self, user):
        """Test revoking all sessions for a user."""
        session1 = factories.SSOSessionFactory(user=user)
        session2 = factories.SSOSessionFactory(user=user)

        revoked_count = models.SSOSession.objects.revoke_all_for_user(user)

        assert revoked_count == 2

        session1.refresh_from_db()
        session2.refresh_from_db()

        assert session1.is_active is False
        assert session2.is_active is False


class TestSessionLifetime:
    """A session lives exactly as long as the device's refresh token, and is deleted once expired."""

    def test_new_session_expires_with_the_refresh_token(self, user):
        before = timezone.now()
        session, _ = SessionService(user).create_session(RequestFactory().get("/"))

        lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
        assert before + lifetime <= session.expires_at <= timezone.now() + lifetime

    def test_explicit_ttl_still_wins(self, user):
        session, _ = SessionService(user).create_session(RequestFactory().get("/"), ttl_days=1)

        assert session.expires_at <= timezone.now() + timedelta(days=1)

    def test_cleanup_task_deletes_only_expired_sessions(self, user):
        expired = factories.SSOSessionFactory(user=user, expires_at=timezone.now() - timedelta(minutes=1))
        valid = factories.SSOSessionFactory(user=user)

        assert cleanup_expired_sessions() == 1

        assert not models.SSOSession.objects.filter(pk=expired.pk).exists()
        assert models.SSOSession.objects.filter(pk=valid.pk).exists()


class TestUserPasskeyManager:
    """Tests for user passkey manager."""

    def test_get_active_for_user(self, user):
        """Test getting active passkeys for a user."""
        active_passkey = factories.UserPasskeyFactory(user=user, is_active=True)
        inactive_passkey = factories.UserPasskeyFactory(user=user, is_active=False)

        active_passkeys = models.UserPasskey.objects.get_active_for_user(user)

        assert active_passkey in active_passkeys
        assert inactive_passkey not in active_passkeys

    def test_get_by_credential_id(self, user):
        """Test finding passkey by credential ID."""
        passkey = factories.UserPasskeyFactory(user=user)

        found = models.UserPasskey.objects.get_by_credential_id(passkey.credential_id)

        assert found == passkey
