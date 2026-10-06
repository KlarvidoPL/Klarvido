"""
Tests for SSO models.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.sso import models, constants
from . import factories


pytestmark = pytest.mark.django_db


class TestSSOSession:
    """Tests for SSOSession model."""

    def test_create_session(self, user):
        """Test creating SSO session."""
        session = models.SSOSession.objects.create(
            user=user,
            session_id=models.SSOSession.generate_session_id(),
            device_name="MacBook Pro",
            browser="Chrome",
            expires_at=timezone.now() + timedelta(days=7),
        )

        assert session.is_active is True
        assert session.is_valid is True

    def test_session_expiration(self, sso_session):
        """Test session expiration."""
        assert sso_session.is_expired is False

        sso_session.expires_at = timezone.now() - timedelta(hours=1)
        sso_session.save()

        assert sso_session.is_expired is True
        assert sso_session.is_valid is False

    def test_revoke_session(self, sso_session):
        """Test revoking session."""
        assert sso_session.is_active is True

        sso_session.revoke(reason="User requested")

        assert sso_session.is_active is False
        assert sso_session.revoked_at is not None
        assert sso_session.revoked_reason == "User requested"

    def test_revoke_session_blacklists_linked_refresh_token(self, user):
        """Revoking a session must blacklist its refresh token, not just flag the row -
        otherwise the device it belongs to can keep minting new access tokens forever."""
        refresh = RefreshToken.for_user(user)
        session = factories.SSOSessionFactory(user=user, refresh_token_jti=refresh["jti"])

        session.revoke(reason="User requested")

        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()

    def test_revoke_session_without_linked_token_does_not_error(self, sso_session):
        """Older/unlinked sessions (empty refresh_token_jti) must still revoke cleanly."""
        assert sso_session.refresh_token_jti == ""

        sso_session.revoke(reason="User requested")

        assert sso_session.is_active is False


class TestUserDevice:
    """Tests for UserDevice model."""

    def test_trust_device(self, user_device):
        """Test trusting a device."""
        assert user_device.is_trusted is False

        user_device.trust()

        assert user_device.is_trusted is True
        assert user_device.trusted_at is not None

    def test_untrust_device(self, user_device):
        """Test removing trust from device."""
        user_device.trust()
        user_device.untrust()

        assert user_device.is_trusted is False
        assert user_device.trusted_at is None

    def test_block_device(self, user_device):
        """Test blocking a device."""
        user_device.block(reason="Suspicious activity")

        assert user_device.is_blocked is True
        assert user_device.blocked_reason == "Suspicious activity"


class TestUserPasskey:
    """Tests for UserPasskey model."""

    def test_record_use(self, passkey):
        """Test recording passkey use."""
        assert passkey.use_count == 0

        passkey.record_use(new_sign_count=1)

        assert passkey.use_count == 1
        assert passkey.sign_count == 1
        assert passkey.last_used_at is not None

    def test_deactivate(self, passkey):
        """Test deactivating passkey."""
        assert passkey.is_active is True

        passkey.deactivate()

        assert passkey.is_active is False


class TestWebAuthnChallenge:
    """Tests for WebAuthnChallenge model."""

    def test_create_challenge(self, user):
        """Test creating challenge."""
        challenge = models.WebAuthnChallenge.create_challenge(
            user=user,
            challenge_type='registration',
        )

        assert challenge.challenge is not None
        assert challenge.is_valid is True
        assert len(challenge.challenge) > 30

    def test_challenge_expiration(self, webauthn_challenge):
        """Test challenge expiration."""
        assert webauthn_challenge.is_valid is True

        webauthn_challenge.expires_at = timezone.now() - timedelta(minutes=1)
        webauthn_challenge.save()

        assert webauthn_challenge.is_expired is True
        assert webauthn_challenge.is_valid is False

    def test_mark_used(self, webauthn_challenge):
        """Test marking challenge as used."""
        assert webauthn_challenge.used_at is None

        webauthn_challenge.mark_used()

        assert webauthn_challenge.used_at is not None
        assert webauthn_challenge.is_valid is False


class TestSSOAuditLog:
    """Tests for SSOAuditLog model."""

    def test_log_event(self, tenant, user):
        """Test logging an event."""
        log = models.SSOAuditLog.log_event(
            event_type=constants.SSOAuditEventType.SESSION_CREATED,
            tenant=tenant,
            user=user,
            description="User logged in",
            ip_address="192.168.1.1",
        )

        assert log.id is not None
        assert log.event_type == constants.SSOAuditEventType.SESSION_CREATED
        assert log.success is True

    def test_log_failed_event(self, tenant):
        """Test logging a failed event."""
        log = models.SSOAuditLog.log_event(
            event_type=constants.SSOAuditEventType.PASSKEY_AUTH_FAILED,
            tenant=tenant,
            description="Login failed",
            success=False,
            error_message="Invalid passkey",
        )

        assert log.success is False
        assert log.error_message == "Invalid passkey"
