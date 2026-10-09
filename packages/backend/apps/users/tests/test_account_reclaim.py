from datetime import timedelta
from unittest.mock import patch

import pyotp
import pytest
from django.conf import settings
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from social_django.models import UserSocialAuth

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import PasskeyManagementGrant, SSOAuditLog, WebAuthnChallenge
from apps.sso.services.sessions import SessionService
from apps.users.models import PendingSocialAccountLink
from apps.users.authentication import SupportedJWTAuthentication
from apps.users.services.account_reclaim import reclaim_unconfirmed_account

pytestmark = pytest.mark.django_db


def _unconfirmed_account_with_everything(user_factory, user_passkey_factory):
    account = user_factory(
        is_confirmed=False,
        otp_enabled=True,
        otp_verified=True,
        otp_base32=pyotp.random_base32(),
    )
    session, _ = SessionService(account).create_session(RequestFactory().get("/"))
    passkey = user_passkey_factory(user=account)
    UserSocialAuth.objects.create(user=account, provider="attacker-provider", uid="attacker-uid")
    PendingSocialAccountLink.objects.create(
        user=account,
        token_hash="x" * 64,
        provider="google-oauth2",
        uid="x",
        credential_version="x",
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    challenge = WebAuthnChallenge.objects.create(
        user=account,
        challenge="attacker-registration-challenge",
        challenge_type="registration",
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    grant = PasskeyManagementGrant.objects.create(
        user=account,
        action="register",
        token_hash="y" * 64,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    return account, session, passkey, challenge, grant


class TestReclaimUnconfirmedAccount:
    def test_only_superuser_can_reclaim(self, user_factory):
        account = user_factory(is_confirmed=False)
        non_superuser = user_factory(is_superuser=False)
        with pytest.raises(PermissionDenied):
            reclaim_unconfirmed_account(account, non_superuser)
        account.refresh_from_db()
        assert account.has_usable_password()

    def test_confirmed_account_cannot_be_reclaimed(self, user_factory):
        account = user_factory(is_confirmed=True)
        superuser = user_factory(is_superuser=True)
        with pytest.raises(ValidationError):
            reclaim_unconfirmed_account(account, superuser)
        account.refresh_from_db()
        assert account.has_usable_password()

    @patch("apps.users.services.account_reclaim.notifications.PasswordResetEmail.send")
    def test_reclaim_strips_credentials_and_keeps_identity(
        self, mock_send, user_factory, user_passkey_factory, django_capture_on_commit_callbacks
    ):
        account, session, passkey, challenge, grant = _unconfirmed_account_with_everything(
            user_factory, user_passkey_factory
        )
        superuser = user_factory(is_superuser=True)
        original_email = account.email

        with django_capture_on_commit_callbacks(execute=True):
            reclaimed = reclaim_unconfirmed_account(account, superuser)

        reclaimed.refresh_from_db()
        assert reclaimed.email == original_email
        assert not reclaimed.has_usable_password()
        assert reclaimed.otp_enabled is False
        assert reclaimed.otp_verified is False
        assert reclaimed.otp_base32 == ""
        assert not reclaimed.is_confirmed

        passkey.refresh_from_db()
        assert passkey.is_active is False

        session.refresh_from_db()
        assert session.is_active is False

        assert not WebAuthnChallenge.objects.filter(pk=challenge.pk).exists()
        assert not PasskeyManagementGrant.objects.filter(pk=grant.pk).exists()

        assert not UserSocialAuth.objects.filter(user=reclaimed).exists()
        assert not PendingSocialAccountLink.objects.filter(user=reclaimed).exists()

        mock_send.assert_called_once()

    def test_reclaim_is_audit_logged_with_actor(self, user_factory, user_passkey_factory):
        account = user_factory(is_confirmed=False)
        superuser = user_factory(is_superuser=True)

        reclaim_unconfirmed_account(account, superuser)

        event = SSOAuditLog.objects.get(event_type=SSOAuditEventType.ACCOUNT_RECLAIMED, user=account)
        assert event.metadata["actor_id"] == str(superuser.pk)
        assert event.metadata["actor_email"] == superuser.email

    def test_reclaim_keeps_profile(self, user_factory):
        account = user_factory(is_confirmed=False)
        account.profile.first_name = "Real"
        account.profile.save(update_fields=["first_name"])
        superuser = user_factory(is_superuser=True)

        reclaimed = reclaim_unconfirmed_account(account, superuser)

        reclaimed.profile.refresh_from_db()
        assert reclaimed.profile.first_name == "Real"


class TestOutstandingProofsFailAfterReclaim:
    """Prove the implicit revocation mechanisms documented in account_reclaim.py's
    module docstring actually work end to end, not just by reading the code."""

    def test_access_token_issued_before_reclaim_is_rejected_afterward(self, user_factory):
        account = user_factory(is_confirmed=False)
        superuser = user_factory(is_superuser=True)
        client = APIClient()
        login_response = client.post(
            '/api/graphql/',
            {
                'query': ('mutation($input: ObtainTokenMutationInput!) { tokenAuth(input: $input) { authenticated } }'),
                'variables': {'input': {'email': account.email, 'password': account._faker_password}},
            },
            format='json',
        )
        assert login_response.json()['data']['tokenAuth']['authenticated'], login_response.json()
        access_cookie = login_response.cookies[settings.ACCESS_TOKEN_COOKIE].value

        reclaim_unconfirmed_account(account, superuser)

        # JWT parsing verifies signature/expiry; password revocation is checked when
        # authentication loads the current account, not when constructing AccessToken.
        with pytest.raises(AuthenticationFailed) as failure:
            SupportedJWTAuthentication().get_user(AccessToken(access_cookie))
        assert failure.value.detail['code'] == 'password_changed'

        stale_client = APIClient()
        stale_client.cookies[settings.ACCESS_TOKEN_COOKIE] = access_cookie
        response = stale_client.post(
            '/api/graphql/',
            {
                'query': 'mutation($input: GenerateOTPMutationInput!) { generateOtp(input: $input) { base32 } }',
                'variables': {'input': {}},
            },
            format='json',
        )
        assert response.json()['errors'], response.json()

    def test_pending_otp_login_proof_fails_after_reclaim(self, user_factory):
        account = user_factory(
            is_confirmed=False, otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32()
        )
        superuser = user_factory(is_superuser=True)
        client = APIClient()
        login_response = client.post(
            '/api/graphql/',
            {
                'query': (
                    'mutation($input: ObtainTokenMutationInput!) { '
                    'tokenAuth(input: $input) { authenticated otpRequired } }'
                ),
                'variables': {'input': {'email': account.email, 'password': account._faker_password}},
            },
            format='json',
        )
        assert login_response.json()['data']['tokenAuth']['otpRequired'], login_response.json()
        otp_auth_cookie = login_response.cookies[settings.OTP_AUTH_TOKEN_COOKIE].value

        reclaim_unconfirmed_account(account, superuser)

        stale_client = APIClient()
        stale_client.cookies[settings.OTP_AUTH_TOKEN_COOKIE] = otp_auth_cookie
        response = stale_client.post(
            '/api/graphql/',
            {
                'query': 'mutation($input: ValidateOTPMutationInput!) { validateOtp(input: $input) { authenticated } }',
                'variables': {'input': {'otpToken': '000000'}},
            },
            format='json',
        )
        assert response.json()['errors'], response.json()


class TestReclaimNotificationResilience:
    @patch(
        "apps.users.services.account_reclaim.notifications.PasswordResetEmail.send",
        side_effect=RuntimeError("broker unreachable"),
    )
    def test_reclaim_succeeds_even_if_notification_send_fails(
        self, mock_send, user_factory, django_capture_on_commit_callbacks
    ):
        account = user_factory(is_confirmed=False)
        superuser = user_factory(is_superuser=True)

        with django_capture_on_commit_callbacks(execute=True):
            reclaimed = reclaim_unconfirmed_account(account, superuser)

        reclaimed.refresh_from_db()
        assert not reclaimed.has_usable_password()
        mock_send.assert_called_once()
