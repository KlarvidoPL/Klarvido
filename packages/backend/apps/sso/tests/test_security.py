"""WebAuthn security tests; enterprise SSO security tests are archived in .disabled."""

import pytest
import base64
import json
from unittest.mock import patch
from django.test import override_settings


pytestmark = pytest.mark.django_db


class TestWebAuthnOriginValidation:
    """Tests for WebAuthn origin validation."""

    def test_webauthn_service_verifies_origin(self):
        """WebAuthn service should verify origin against expected value."""
        from apps.sso.services.webauthn import WebAuthnService
        from apps.users.tests.factories import UserFactory

        user = UserFactory()
        service = WebAuthnService(user)

        # Valid origin should pass
        with override_settings(WEB_APP_URL='https://app.example.com'):
            service_with_settings = WebAuthnService(user)
            assert service_with_settings._verify_origin('https://app.example.com') is True

    def test_webauthn_service_rejects_invalid_origin(self):
        """WebAuthn service should reject invalid origins."""
        from apps.sso.services.webauthn import WebAuthnService
        from apps.users.tests.factories import UserFactory

        user = UserFactory()

        # Invalid origin should fail
        with override_settings(
            WEB_APP_URL='https://app.example.com',
            WEBAUTHN_ALLOW_ORIGIN_MISMATCH=False,
        ):
            service = WebAuthnService(user)
            with pytest.raises(ValueError) as exc_info:
                service._verify_origin('https://evil.com')

            assert 'origin' in str(exc_info.value).lower()

    def test_webauthn_origin_mismatch_allowed_when_configured(self):
        """WebAuthn should allow origin mismatch only when explicitly configured."""
        from apps.sso.services.webauthn import WebAuthnService
        from apps.users.tests.factories import UserFactory

        user = UserFactory()

        # With explicit override, mismatch should be allowed (for development)
        with override_settings(
            WEB_APP_URL='https://app.example.com',
            WEBAUTHN_ALLOW_ORIGIN_MISMATCH=True,
        ):
            service = WebAuthnService(user)
            # Should not raise
            assert service._verify_origin('http://localhost:3000') is True


class TestWebAuthnSignCountEnforcement:
    """Tests for WebAuthn sign count enforcement."""

    def test_webauthn_detects_sign_count_anomaly(self):
        """WebAuthn should detect sign count regression (possible cloned authenticator)."""
        from apps.sso.services.webauthn import WebAuthnService
        from apps.sso.tests.factories import UserPasskeyFactory, WebAuthnChallengeFactory
        from apps.users.tests.factories import UserFactory

        user = UserFactory()

        # Create passkey with sign count of 10
        passkey = UserPasskeyFactory(
            user=user,
            sign_count=10,
            is_active=True,
        )

        # Create a valid challenge
        challenge = WebAuthnChallengeFactory(
            user=user,
            challenge_type='authentication',
        )

        service = WebAuthnService(user)

        # Mock the signature verification to pass
        with patch.object(service, '_verify_webauthn_signature', return_value=True):
            with patch.object(service, '_verify_origin', return_value=True):
                # Create mock auth data with sign count of 5 (less than stored 10)
                auth_data = b'\x00' * 33 + (5).to_bytes(4, 'big')  # Sign count at bytes 33-36
                client_data = json.dumps(
                    {
                        'type': 'webauthn.get',
                        'challenge': challenge.challenge,
                        'origin': 'https://app.example.com',
                    }
                ).encode()

                # With strict mode, should raise error
                with override_settings(WEBAUTHN_STRICT_SIGN_COUNT=True):
                    with pytest.raises(ValueError) as exc_info:
                        service.verify_authentication(
                            challenge=challenge.challenge,
                            credential_id=passkey.credential_id,
                            authenticator_data=base64.urlsafe_b64encode(auth_data).decode().rstrip('='),
                            client_data_json=base64.urlsafe_b64encode(client_data).decode().rstrip('='),
                            signature=base64.urlsafe_b64encode(b'mock_signature').decode().rstrip('='),
                        )

                    assert 'security anomaly' in str(exc_info.value).lower()
