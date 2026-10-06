"""
Integration tests for shared passkey and session security.
"""

import pytest
from datetime import timedelta
from django.utils import timezone

from apps.sso import models

from . import factories


pytestmark = pytest.mark.django_db


class TestSessionManagementFlow:
    """Integration tests for session management."""

    def test_session_creation_on_login(self, user):
        """Test session creation for a supported login."""
        # Simulate session creation after a supported login
        session = models.SSOSession.objects.create(
            user=user,
            session_id=models.SSOSession.generate_session_id(),
            device_name="Chrome on macOS",
            browser="Chrome",
            operating_system="macOS",
            ip_address="192.168.1.100",
            expires_at=timezone.now() + timedelta(days=7),
        )

        assert session.is_active is True

        # Verify user can see the session
        user_sessions = models.SSOSession.objects.get_active_for_user(user)
        assert session in user_sessions

    def test_session_revocation(self, user, sso_session):
        """Test session revocation."""
        assert sso_session.is_active is True

        sso_session.revoke(reason="User requested")

        assert sso_session.is_active is False
        assert sso_session.revoked_at is not None
        assert sso_session.revoked_reason == "User requested"

        # Verify session no longer appears in active sessions
        active_sessions = models.SSOSession.objects.get_active_for_user(user)
        assert sso_session not in active_sessions

    def test_revoke_all_other_sessions(self, user):
        """Test revoking all sessions except current."""
        # Create multiple sessions
        session1 = factories.SSOSessionFactory(user=user)
        session2 = factories.SSOSessionFactory(user=user)
        current_session = factories.SSOSessionFactory(user=user)

        # Revoke all except current
        revoked_count = (
            models.SSOSession.objects.filter(
                user=user,
                is_active=True,
            )
            .exclude(id=current_session.id)
            .update(
                is_active=False,
                revoked_at=timezone.now(),
                revoked_reason="User logged out all other sessions",
            )
        )

        assert revoked_count == 2

        # Verify current session still active
        current_session.refresh_from_db()
        assert current_session.is_active is True


class TestPasskeyFlow:
    """Integration tests for passkey/WebAuthn flow."""

    def test_passkey_registration_flow(self, user):
        """Test passkey registration flow."""
        # 1. Generate registration challenge
        challenge = models.WebAuthnChallenge.create_challenge(
            user=user,
            challenge_type='registration',
        )

        assert challenge.is_valid is True

        # 2. Simulate successful registration verification
        passkey = models.UserPasskey.objects.create(
            user=user,
            credential_id='test_credential_id',
            name='My MacBook Touch ID',
            public_key='mock_public_key_data',
            sign_count=0,
            authenticator_type='platform',
            is_active=True,
        )

        # 3. Mark challenge as used
        challenge.mark_used()

        assert challenge.is_valid is False
        assert passkey.is_active is True

    def test_passkey_authentication_flow(self, user, user_passkey):
        """Test passkey authentication flow."""
        passkey = user_passkey
        initial_use_count = passkey.use_count

        # 1. Generate authentication challenge
        challenge = models.WebAuthnChallenge.create_challenge(
            user=user,
            challenge_type='authentication',
        )

        # 2. Simulate successful authentication
        passkey.record_use(new_sign_count=passkey.sign_count + 1)

        # 3. Mark challenge as used
        challenge.mark_used()

        assert passkey.use_count == initial_use_count + 1
        assert passkey.last_used_at is not None
