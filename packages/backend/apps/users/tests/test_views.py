from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta

from unittest.mock import MagicMock, patch

import pytest
from django.db import DatabaseError, connections
from django.conf import settings
from django.http import HttpResponse, SimpleCookie
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, APIClient
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from apps.sso.models import SSOSession
from apps.users.serializers import CookieTokenRefreshSerializer
from rest_framework import status
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.tokens import RefreshToken, BlacklistedToken, AccessToken

from apps.sso.tests.factories import SSOSessionFactory

from .. import models

pytestmark = pytest.mark.django_db


def validate_jwt(response_data, user):
    AuthToken = jwt_api_settings.AUTH_TOKEN_CLASSES[0]
    token = AuthToken(response_data['access'])

    return token[jwt_api_settings.USER_ID_CLAIM] == user.id


class TestTokenRefresh:
    def test_return_error_if_no_cookie_or_payload_is_sent(self, api_client):
        response = api_client.post(reverse('jwt_token_refresh'))
        assert response.json() == {
            'non_field_errors': ["No valid token found in cookie 'refresh_token' or field 'refresh'"]
        }

    def test_return_error_for_invalid_refresh_token(self, api_client, user: models.User):
        refresh = RefreshToken.for_user(user)
        api_client.cookies = SimpleCookie(
            {
                settings.ACCESS_TOKEN_COOKIE: str(refresh.access_token),
                settings.REFRESH_TOKEN_COOKIE: 'invalid-token',
            }
        )

        response = api_client.post(
            reverse('jwt_token_refresh'),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.cookies[settings.ACCESS_TOKEN_COOKIE].value == ''
        assert response.cookies[settings.REFRESH_TOKEN_COOKIE].value == ''

    def test_refresh_cookie_auth(self, api_client, user: models.User):
        refresh = RefreshToken.for_user(user)
        SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        api_client.cookies = SimpleCookie(
            {
                settings.ACCESS_TOKEN_COOKIE: str(refresh.access_token),
                settings.REFRESH_TOKEN_COOKIE: str(refresh),
            }
        )

        response = api_client.post(reverse('jwt_token_refresh'))

        assert response.status_code == status.HTTP_200_OK
        new_access_token_raw = response.cookies[settings.ACCESS_TOKEN_COOKIE].value
        new_refresh_token_raw = response.cookies[settings.REFRESH_TOKEN_COOKIE].value
        assert AccessToken(new_access_token_raw), new_access_token_raw
        assert RefreshToken(new_refresh_token_raw), new_refresh_token_raw
        assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()

    def test_refresh_sent_in_payload(self, api_client, user: models.User):
        refresh = RefreshToken.for_user(user)
        SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])

        response = api_client.post(reverse('jwt_token_refresh'), data={'refresh': str(refresh)})

        assert response.status_code == status.HTTP_200_OK
        new_access_token_raw = response.cookies[settings.ACCESS_TOKEN_COOKIE].value
        new_refresh_token_raw = response.cookies[settings.REFRESH_TOKEN_COOKIE].value
        assert AccessToken(new_access_token_raw), new_access_token_raw
        assert RefreshToken(new_refresh_token_raw), new_refresh_token_raw
        assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()

    @pytest.mark.parametrize('state', ['missing', 'expired', 'wrong-owner'])
    def test_refresh_requires_valid_owned_session(self, api_client, user, user_factory, state):
        refresh = RefreshToken.for_user(user)
        if state != 'missing':
            SSOSessionFactory(
                user=user_factory() if state == 'wrong-owner' else user,
                refresh_token_jti=refresh['jti'],
                expires_at=timezone.now() - timedelta(seconds=1)
                if state == 'expired'
                else timezone.now() + timedelta(days=1),
            )
        before = OutstandingToken.objects.count()
        response = api_client.post(reverse('jwt_token_refresh'), data={'refresh': str(refresh)})
        assert response.status_code == 401
        assert response.cookies[settings.ACCESS_TOKEN_COOKIE].value == ''
        assert response.cookies[settings.REFRESH_TOKEN_COOKIE].value == ''
        assert OutstandingToken.objects.count() == before

    def test_session_rotation_failure_rolls_back_new_token_and_blacklist(self, user):
        refresh = RefreshToken.for_user(user)
        session = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        request = APIRequestFactory().post('/')
        serializer = CookieTokenRefreshSerializer(data={'refresh': str(refresh)}, context={'request': request})
        before = OutstandingToken.objects.count()
        with patch.object(SSOSession, 'extend', side_effect=RuntimeError('storage failure')), pytest.raises(
            RuntimeError
        ):
            serializer.is_valid(raise_exception=True)
        session.refresh_from_db()
        assert session.refresh_token_jti == refresh['jti']
        assert OutstandingToken.objects.count() == before
        assert not BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()
        assert RefreshToken(str(refresh))

    def test_refresh_database_failure_returns_no_cookies(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        session = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        before = OutstandingToken.objects.count()
        with patch.object(SSOSession, 'extend', side_effect=DatabaseError('private database detail')):
            response = api_client.post(reverse('jwt_token_refresh'), data={'refresh': str(refresh)})
        assert response.status_code == 503
        assert b'private database detail' not in response.content
        assert settings.ACCESS_TOKEN_COOKIE not in response.cookies
        assert settings.REFRESH_TOKEN_COOKIE not in response.cookies
        session.refresh_from_db()
        assert session.refresh_token_jti == refresh['jti']
        assert OutstandingToken.objects.count() == before
        assert RefreshToken(str(refresh))

    def test_revocation_uses_current_token_even_with_stale_session_instance(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        stale = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        response = api_client.post(reverse('jwt_token_refresh'), data={'refresh': str(refresh)})
        assert response.status_code == 200
        rotated = response.cookies[settings.REFRESH_TOKEN_COOKIE].value
        stale.revoke(reason='User requested')
        assert api_client.post(reverse('jwt_token_refresh'), data={'refresh': rotated}).status_code == 401

    def test_refresh_rejected_for_revoked_session(self, api_client, user: models.User):
        """A device whose session was revoked (e.g. "Sign out" from Active Sessions
        on another device) must not be able to mint new access tokens via /refresh."""
        from apps.sso.tests.factories import SSOSessionFactory

        refresh = RefreshToken.for_user(user)
        session = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        session.revoke(reason="User requested")

        api_client.cookies = SimpleCookie({settings.REFRESH_TOKEN_COOKIE: str(refresh)})
        response = api_client.post(reverse('jwt_token_refresh'))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_keeps_session_revocable_after_rotation(self, api_client, user: models.User):
        """Rotation mints a brand new refresh token (new jti) on every call - the
        session's link must follow it, or the session becomes unrevocable after
        its first refresh."""
        from apps.sso.models import SSOSession
        from apps.sso.tests.factories import SSOSessionFactory

        refresh = RefreshToken.for_user(user)
        session = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])

        api_client.cookies = SimpleCookie({settings.REFRESH_TOKEN_COOKIE: str(refresh)})
        response = api_client.post(reverse('jwt_token_refresh'))
        assert response.status_code == status.HTTP_200_OK
        rotated_refresh_raw = response.cookies[settings.REFRESH_TOKEN_COOKIE].value

        session.refresh_from_db()
        assert session.refresh_token_jti == RefreshToken(rotated_refresh_raw)['jti']
        assert session.refresh_token_jti != refresh['jti']

        # Revoking now (using the *new* jti) must still block a further refresh
        SSOSession.objects.get(pk=session.pk).revoke(reason="User requested")

        api_client.cookies = SimpleCookie({settings.REFRESH_TOKEN_COOKIE: rotated_refresh_raw})
        second_response = api_client.post(reverse('jwt_token_refresh'))
        assert second_response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_extends_session_and_records_activity(self, api_client, user: models.User):
        """Each refresh gives the device a new full-lifetime refresh token, so the session must live as long,
        and "last activity" in Active Sessions must move with it."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.sso.models import SSOSession
        from apps.sso.tests.factories import SSOSessionFactory

        refresh = RefreshToken.for_user(user)
        session = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        # Logged in a while ago, soon to expire
        stale = timezone.now() - timedelta(hours=3)
        SSOSession.objects.filter(pk=session.pk).update(
            last_activity_at=stale, expires_at=timezone.now() + timedelta(hours=1)
        )

        api_client.cookies = SimpleCookie({settings.REFRESH_TOKEN_COOKIE: str(refresh)})
        before = timezone.now()
        response = api_client.post(reverse('jwt_token_refresh'))
        assert response.status_code == status.HTTP_200_OK

        session.refresh_from_db()
        assert session.last_activity_at >= before
        lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
        assert before + lifetime <= session.expires_at <= timezone.now() + lifetime


class TestLogout:
    def test_graceful_logout_without_token(self, api_client):
        """Logout should succeed even without a valid token - it's a graceful operation."""
        response = api_client.post(reverse('logout'))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'ok': True}

    def test_clear_cookies(self, api_client, user: models.User):
        refresh = RefreshToken.for_user(user)
        api_client.cookies = SimpleCookie(
            {
                settings.REFRESH_TOKEN_LOGOUT_COOKIE: str(refresh),
            }
        )

        response = api_client.post(reverse('logout'))

        assert response.status_code == status.HTTP_200_OK
        assert not response.cookies[settings.ACCESS_TOKEN_COOKIE].value
        assert not response.cookies[settings.REFRESH_TOKEN_COOKIE].value
        assert not response.cookies[settings.REFRESH_TOKEN_LOGOUT_COOKIE].value

    def test_blacklist_old_token_with_cookie_auth(self, api_client, user: models.User):
        refresh = RefreshToken.for_user(user)
        api_client.cookies = SimpleCookie(
            {
                settings.REFRESH_TOKEN_LOGOUT_COOKIE: str(refresh),
            }
        )

        api_client.post(reverse('logout'))

        assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()

    def test_blacklist_old_token_with_refresh_in_payload(self, api_client, user: models.User):
        refresh = RefreshToken.for_user(user)
        api_client.post(reverse('logout'), data={'refresh': str(refresh)})
        assert BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists()

    def test_logout_marks_linked_session_inactive(self, api_client, user: models.User):
        """Without this, a logged-out device's session keeps showing as "active"
        in Active Sessions until it naturally expires."""
        from apps.sso.tests.factories import SSOSessionFactory

        refresh = RefreshToken.for_user(user)
        session = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'], is_active=True)

        api_client.post(reverse('logout'), data={'refresh': str(refresh)})

        session.refresh_from_db()
        assert session.is_active is False


class TestSocialAuthComplete:
    """Regression test for a bug where "Sign in with Google/Facebook" passed the
    ambient request.user into social-core's do_complete(). If the visitor already
    had a valid session in that browser, this made the flow silently re-associate
    and log back into that *existing* user regardless of which social account was
    picked, instead of resolving the account the chosen identity actually belongs
    to (confirmed in production: three distinct Google accounts all ended up
    mapped to the same Klarvido user)."""

    def test_complete_view_does_not_pass_ambient_request_user(self, api_client):
        with patch("apps.users.views.do_complete") as mock_do_complete:
            mock_do_complete.return_value = HttpResponse()
            api_client.get(reverse("social:complete", kwargs={"backend": "google-oauth2"}))

        assert mock_do_complete.called
        assert mock_do_complete.call_args.kwargs["user"] is None


class TestSocialAuthCreatesSession:
    """Regression test for a bug where signing in with Google/Facebook never
    created an SSOSession, so "Active Sessions" in Profile > Security stayed
    empty after an OAuth login even though it correctly showed a session for
    password login and SAML SSO login."""

    def _get_do_login_callback(self, api_client):
        with patch("apps.users.views.do_complete") as mock_do_complete:
            mock_do_complete.return_value = HttpResponse()
            api_client.get(reverse("social:complete", kwargs={"backend": "google-oauth2"}))
        # `complete()` calls do_complete(request.backend, _do_login, user=None, ...) -
        # the login callback is the 2nd positional arg.
        return mock_do_complete.call_args.args[1]

    def test_do_login_creates_session_for_completed_oauth_login(self, api_client, user_factory):
        from apps.sso.models import SSOSession

        user = user_factory(otp_enabled=False)
        do_login = self._get_do_login_callback(api_client)
        mock_backend = MagicMock()

        do_login(mock_backend, user, social_user=None)

        session = SSOSession.objects.get(user=user)
        mock_backend.strategy.set_session_id.assert_called_once_with(session.session_id)

    def test_oauth_session_failure_does_not_publish_tokens(self, api_client, user_factory):
        user = user_factory(otp_enabled=False)
        do_login = self._get_do_login_callback(api_client)
        backend = MagicMock()
        before = OutstandingToken.objects.count()
        with patch(
            'apps.sso.services.SessionService.create_session', side_effect=RuntimeError('private detail')
        ), pytest.raises(ValidationError, match='Unable to establish a session'):
            do_login(backend, user, social_user=None)
        backend.strategy.set_jwt.assert_not_called()
        backend.strategy.set_session_id.assert_not_called()
        assert OutstandingToken.objects.count() == before

    def test_do_login_does_not_create_session_when_otp_step_is_pending(self, api_client, user_factory):
        from apps.sso.models import SSOSession

        user = user_factory(otp_enabled=True, otp_verified=True)
        do_login = self._get_do_login_callback(api_client)
        mock_backend = MagicMock()

        do_login(mock_backend, user, social_user=None)

        assert not SSOSession.objects.filter(user=user).exists()
        mock_backend.strategy.set_session_id.assert_not_called()


class TestSocialAuthSetsAuthMethodClaim:
    """Regression test for a bug where the OAuth-issued JWT never got an
    `auth_method` claim (it was minted via a raw RefreshToken.for_user() instead
    of the create_jwt_tokens() helper every other login path uses). It isn't a
    live bypass on its own - get_auth_method_from_token() defaults a missing
    claim to 'password', and should_enforce_sso_for_session() (see
    apps/sso/enforcement.py) enforces against 'password' the same as any other
    non-'sso' method - but it does mean OAuth sessions are indistinguishable
    from password ones to any code that inspects auth_method, and it's exactly
    the kind of gap that would silently become a real SSO-enforcement bypass
    if that check were ever narrowed to literally `== 'password'` instead of
    `!= 'sso'`."""

    def _get_do_login_callback(self, api_client):
        with patch("apps.users.views.do_complete") as mock_do_complete:
            mock_do_complete.return_value = HttpResponse()
            api_client.get(reverse("social:complete", kwargs={"backend": "google-oauth2"}))
        return mock_do_complete.call_args.args[1]

    def test_oauth_token_carries_oauth_auth_method_claim(self, api_client, user_factory):
        user = user_factory(otp_enabled=False)
        do_login = self._get_do_login_callback(api_client)
        mock_backend = MagicMock()

        do_login(mock_backend, user, social_user=None)

        token = mock_backend.strategy.set_jwt.call_args.args[0]
        assert token['auth_method'] == 'oauth'
        assert token.access_token['auth_method'] == 'oauth'


@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_and_revocation_cannot_leave_a_usable_refresh_token(user):
    refresh = RefreshToken.for_user(user)
    stale = SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
    barrier = Barrier(2)

    def rotate():
        try:
            barrier.wait(timeout=10)
            response = APIClient().post(reverse('jwt_token_refresh'), data={'refresh': str(refresh)})
            return response.status_code, response.cookies.get(settings.REFRESH_TOKEN_COOKIE)
        finally:
            connections.close_all()

    def revoke():
        try:
            barrier.wait(timeout=10)
            stale.revoke(reason='Concurrent user revocation')
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        rotation = pool.submit(rotate)
        revocation = pool.submit(revoke)
        code, cookie = rotation.result(timeout=20)
        revocation.result(timeout=20)
    stale.refresh_from_db()
    assert not stale.is_active
    assert BlacklistedToken.objects.filter(token__jti=stale.refresh_token_jti).exists()
    assert APIClient().post(reverse('jwt_token_refresh'), data={'refresh': str(refresh)}).status_code == 401
    assert code in (200, 401)
    if code == 200:
        assert APIClient().post(reverse('jwt_token_refresh'), data={'refresh': cookie.value}).status_code == 401
