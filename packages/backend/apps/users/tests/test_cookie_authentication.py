"""Browser login and refresh must never expose bearer tokens to application scripts."""

from unittest.mock import patch

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.sso.models import SSOSession
from apps.users.models import User
from apps.users.services.otp_login import begin_otp_login
from apps.users import tokens

pytestmark = pytest.mark.django_db


def test_cookie_only_login_refresh_and_logout(user):
    user.set_password('Cookie-only-password-123!')
    user.save(update_fields=['password'])
    client = APIClient(enforce_csrf_checks=True)
    proof = client.get('/api/auth/csrf/').json()['csrfToken']
    client.credentials(HTTP_X_CSRFTOKEN=proof)
    query = """mutation($input: ObtainTokenMutationInput!) {
      tokenAuth(input: $input) { authenticated otpRequired leakedAccess: access leakedRefresh: refresh otpAuthToken }
    }"""
    response = client.post(
        '/api/graphql/',
        {'query': query, 'variables': {'input': {'email': user.email, 'password': 'Cookie-only-password-123!'}}},
        format='json',
    )
    assert response.status_code == 200
    assert not response.json().get('errors'), response.content
    assert response.json()['data']['tokenAuth'] == {
        'authenticated': True,
        'otpRequired': False,
        'leakedAccess': None,
        'leakedRefresh': None,
        'otpAuthToken': None,
    }
    assert response['Cache-Control'] == 'no-store'
    assert 'X-Auth-Token' not in response
    for name in (settings.ACCESS_TOKEN_COOKIE, settings.REFRESH_TOKEN_COOKIE, settings.SESSION_ID_COOKIE):
        assert response.cookies[name]['httponly']
    assert AccessToken(response.cookies[settings.ACCESS_TOKEN_COOKIE].value)['user_id'] == str(user.pk)
    assert SSOSession.objects.filter(user=user, is_active=True).exists()
    # Real browsers honor cookie paths; do not send the access token on refresh.
    client.cookies.pop(settings.ACCESS_TOKEN_COOKIE, None)
    response = client.post('/api/auth/token-refresh/', {}, format='json')
    assert response.status_code == 200, response.content
    assert response.json() == {'success': True}
    assert response['Cache-Control'] == 'no-store'
    assert response.cookies[settings.ACCESS_TOKEN_COOKIE]['httponly']
    assert response.cookies[settings.REFRESH_TOKEN_COOKIE]['httponly']
    assert RefreshToken(response.cookies[settings.REFRESH_TOKEN_COOKIE].value)['user_id'] == str(user.pk)
    response = client.post('/api/auth/logout/', {}, format='json')
    assert response.status_code == 200
    assert response.cookies[settings.ACCESS_TOKEN_COOKIE].value == ''


def test_password_login_session_failure_returns_no_tokens(user):
    user.set_password('Cookie-only-password-123!')
    user.save(update_fields=['password'])
    before = OutstandingToken.objects.count()
    client = APIClient()
    with patch('apps.sso.services.SessionService.create_session', side_effect=RuntimeError('private database detail')):
        response = client.post(
            '/api/graphql/',
            {
                'query': 'mutation($input: ObtainTokenMutationInput!) { tokenAuth(input: $input) { authenticated } }',
                'variables': {'input': {'email': user.email, 'password': 'Cookie-only-password-123!'}},
            },
            format='json',
        )
    assert response.json().get('errors')
    assert b'private database detail' not in response.content
    assert settings.ACCESS_TOKEN_COOKIE not in response.cookies
    assert settings.REFRESH_TOKEN_COOKIE not in response.cookies
    assert OutstandingToken.objects.count() == before
    assert not SSOSession.objects.filter(user=user).exists()


@pytest.mark.parametrize('method', ['signup', 'otp', 'password-change', 'password-reset-confirm'])
def test_other_authentication_session_failures_roll_back(method, user, totp_mock):
    client = APIClient()
    password = 'Cookie-only-password-123!'
    user.set_password(password)
    user.save(update_fields=['password'])
    if method == 'signup':
        field, input_type = 'signUp', 'SingUpMutationInput'
        payload = {'email': 'session-failure@example.com', 'password': password}
    elif method == 'otp':
        user.otp_enabled = user.otp_verified = True
        user.save(update_fields=['otp_enabled', 'otp_verified'])
        totp_mock(verify=True)
        client.cookies[settings.OTP_AUTH_TOKEN_COOKIE] = begin_otp_login(user, 'password')
        field, input_type = 'validateOtp', 'ValidateOTPMutationInput'
        payload = {'otpToken': '123456'}
    elif method == 'password-reset-confirm':
        field, input_type = 'passwordResetConfirm', 'PasswordResetConfirmationMutationInput'
        payload = {
            'user': str(user.pk),
            'token': tokens.password_reset_token.make_token(user),
            'newPassword': 'Changed-password-987!',
        }
    else:
        client.force_authenticate(user=user)
        field, input_type = 'changePassword', 'ChangePasswordMutationInput'
        payload = {'oldPassword': password, 'newPassword': 'Changed-password-987!'}
    before = OutstandingToken.objects.count()
    with patch('apps.sso.services.SessionService.create_session', side_effect=RuntimeError('private detail')):
        response = client.post(
            '/api/graphql/',
            {
                'query': f'mutation($input: {input_type}!) {{ {field}(input: $input) {{ authenticated }} }}',
                'variables': {'input': payload},
            },
            format='json',
        )
    assert response.json().get('errors'), response.content
    assert b'private detail' not in response.content
    assert settings.ACCESS_TOKEN_COOKIE not in response.cookies
    assert settings.REFRESH_TOKEN_COOKIE not in response.cookies
    assert OutstandingToken.objects.count() == before
    assert not SSOSession.objects.filter(user=user).exists()
    if method == 'signup':
        assert not User.objects.filter(email=payload['email']).exists()
    elif method in ('password-change', 'password-reset-confirm'):
        user.refresh_from_db()
        assert user.check_password(password)


class TestPasswordChangeSessionContinuity:
    """E04/E05/E06 follow-up: completing a password reset/change must leave the browser that
    completed it signed in with a fresh, working session (not relying on a now-poisoned old
    access token and a blacklisted refresh token that only breaks on the next page load), and
    must properly revoke every *other* session rather than leaving it displayed as still
    active while its refresh token silently stops working."""

    MUTATION = (
        'mutation($input: PasswordResetConfirmationMutationInput!) { '
        'passwordResetConfirm(input: $input) { authenticated } }'
    )

    def test_reset_confirm_signs_the_completing_browser_in(self, user_factory):
        user = user_factory()
        user.set_unusable_password()
        user.save()
        client = APIClient()

        token = tokens.password_reset_token.make_token(user)
        response = client.post(
            '/api/graphql/',
            {
                'query': self.MUTATION,
                'variables': {'input': {'user': str(user.pk), 'token': token, 'newPassword': 'Brand-new-pass-1!'}},
            },
            format='json',
        )

        body = response.json()
        assert not body.get('errors'), body
        assert body['data']['passwordResetConfirm']['authenticated'] is True
        assert AccessToken(response.cookies[settings.ACCESS_TOKEN_COOKIE].value)['user_id'] == str(user.pk)

        # The fresh cookies actually work immediately - no broken "looks logged in" window.
        current_user = client.post('/api/graphql/', {'query': 'query { currentUser { id } }'}, format='json')
        assert current_user.json()['data']['currentUser']['id'] == user.id.hashid

    def test_reset_confirm_revokes_other_sessions_without_leaving_a_ghost_entry(self, user_factory, faker):
        password = 'Old-password-42!'
        user = user_factory(password=password)
        other_browser = APIClient()
        login = other_browser.post(
            '/api/graphql/',
            {
                'query': ('mutation($input: ObtainTokenMutationInput!) { tokenAuth(input: $input) { authenticated } }'),
                'variables': {'input': {'email': user.email, 'password': password}},
            },
            format='json',
        )
        assert not login.json().get('errors'), login.json()
        other_refresh_token = other_browser.cookies[settings.REFRESH_TOKEN_COOKIE].value
        assert SSOSession.objects.filter(user=user, is_active=True).count() == 1

        token = tokens.password_reset_token.make_token(user)
        reset_browser = APIClient()
        reset_resp = reset_browser.post(
            '/api/graphql/',
            {
                'query': self.MUTATION,
                'variables': {'input': {'user': str(user.pk), 'token': token, 'newPassword': 'Brand-new-pass-1!'}},
            },
            format='json',
        )
        assert not reset_resp.json().get('errors'), reset_resp.json()

        # The other browser's session is marked inactive - not left showing as active while its
        # refresh token silently stops working - while the reset-completing browser's own fresh
        # session is untouched.
        assert SSOSession.objects.filter(user=user, is_active=True).count() == 1
        assert SSOSession.objects.filter(user=user, is_active=False).exists()

        # ...and its refresh token genuinely no longer works, not just hidden from the list.
        other_browser.cookies[settings.REFRESH_TOKEN_COOKIE] = other_refresh_token
        refresh_resp = other_browser.post('/api/auth/token-refresh/', {}, format='json')
        assert refresh_resp.status_code == 401

    def test_change_password_also_revokes_other_sessions(self, user_factory):
        password = 'Old-password-42!'
        user = user_factory(password=password)
        other_browser = APIClient()
        other_browser.post(
            '/api/graphql/',
            {
                'query': ('mutation($input: ObtainTokenMutationInput!) { tokenAuth(input: $input) { authenticated } }'),
                'variables': {'input': {'email': user.email, 'password': password}},
            },
            format='json',
        )
        other_refresh_token = other_browser.cookies[settings.REFRESH_TOKEN_COOKIE].value

        changing_browser = APIClient()
        changing_browser.force_authenticate(user)
        mutation = 'mutation($input: ChangePasswordMutationInput!) { changePassword(input: $input) { authenticated } }'
        resp = changing_browser.post(
            '/api/graphql/',
            {
                'query': mutation,
                'variables': {'input': {'oldPassword': password, 'newPassword': 'Changed-password-987!'}},
            },
            format='json',
        )
        assert not resp.json().get('errors'), resp.json()

        other_browser.cookies[settings.REFRESH_TOKEN_COOKIE] = other_refresh_token
        refresh_resp = other_browser.post('/api/auth/token-refresh/', {}, format='json')
        assert refresh_resp.status_code == 401
