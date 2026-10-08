"""Browser login and refresh must never expose bearer tokens to application scripts."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.sso.models import SSOSession

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
