"""Real HTTP tests: cookie proof is required before any GraphQL/auth side effects."""

import json

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken, BlacklistedToken

pytestmark = pytest.mark.django_db
ORIGIN = 'https://klarvido.example'
UPDATE = 'mutation { updateCurrentUser(input: {firstName: "Updated"}) { userProfile { id } } }'


@pytest.fixture(autouse=True)
def production_config(settings):
    settings.DEBUG = False
    settings.CSRF_TRUSTED_ORIGINS = [ORIGIN]
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]


def client_for(user=None, refresh=False):
    client = APIClient(enforce_csrf_checks=True)
    if user:
        token = RefreshToken.for_user(user)
        client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(token.access_token)
        if refresh:
            client.cookies[settings.REFRESH_TOKEN_COOKIE] = str(token)
    return client


def bootstrap(client):
    response = client.get('/api/auth/csrf/', HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 200
    assert 'no-store' in response['Cache-Control']
    assert settings.CSRF_COOKIE_NAME in response.cookies
    return response.json()['csrfToken']


@pytest.mark.parametrize('encoding', ['json', 'multipart'])
@pytest.mark.parametrize('proof', ['none', 'wrong', 'foreign', 'valid', 'mixed'])
def test_graphql_cookie_csrf(encoding, proof, user_factory):
    user = user_factory(profile__first_name='Original')
    client = client_for(user)
    headers = {'HTTP_ORIGIN': ORIGIN}
    if proof != 'none':
        headers['HTTP_X_CSRFTOKEN'] = bootstrap(client) if proof != 'wrong' else 'x' * 64
    if proof == 'foreign':
        headers['HTTP_ORIGIN'] = 'https://attacker.example'
    if proof == 'mixed':
        headers['HTTP_AUTHORIZATION'] = f'Bearer {RefreshToken.for_user(user).access_token}'
        headers.pop('HTTP_X_CSRFTOKEN')
    data = {'query': UPDATE} if encoding == 'json' else {'operations': json.dumps({'query': UPDATE}), 'map': '{}'}
    response = client.post('/api/graphql/', data, format=encoding, **headers)
    if proof == 'valid':
        assert response.status_code == 200, response.content
        assert not response.json().get('errors'), response.content
    else:
        assert response.status_code == 403, response.content
        assert response.json()['code'] == 'csrf_failed'
    user.profile.refresh_from_db()
    assert user.profile.first_name == ('Updated' if proof == 'valid' else 'Original')


def test_bearer_only_graphql_needs_no_cookie_proof(user_factory):
    user = user_factory()
    client = client_for()
    response = client.post(
        '/api/graphql/',
        {'query': UPDATE},
        format='json',
        HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}',
    )
    assert response.status_code == 200
    assert not response.json().get('errors'), response.content


@pytest.mark.parametrize('path', ['/api/auth/token-refresh/', '/api/auth/logout/'])
@pytest.mark.parametrize('valid', [False, True])
def test_cookie_refresh_logout_require_csrf(path, valid, user_factory):
    user = user_factory()
    client = client_for(user, refresh=True)
    old_token = client.cookies[settings.REFRESH_TOKEN_COOKIE].value
    headers = {'HTTP_ORIGIN': ORIGIN}
    if valid:
        headers['HTTP_X_CSRFTOKEN'] = bootstrap(client)
    response = client.post(path, {}, format='json', **headers)
    assert response.status_code == (200 if valid else 403), response.content
    assert BlacklistedToken.objects.filter(token__token=old_token).exists() is valid
    if not valid:
        assert settings.ACCESS_TOKEN_COOKIE not in response.cookies  # No deletion/rotation before CSRF proof.


@pytest.mark.parametrize('path', ['/api/auth/token-refresh/', '/api/auth/logout/'])
def test_explicit_refresh_token_without_cookies_remains_supported(path, user_factory):
    user = user_factory()
    client = client_for()
    response = client.post(path, {'refresh': str(RefreshToken.for_user(user))}, format='json')
    assert response.status_code == 200, response.content


@pytest.mark.parametrize('origin', [ORIGIN, 'https://attacker.example', None])
def test_anonymous_cookie_blocked_login_requires_trusted_origin_and_custom_header(origin):
    client = client_for()
    token = bootstrap(client)
    client.cookies.clear()  # Safari blocks API cookies; the bootstrap token is still readable in the response.
    headers = {'HTTP_X_CSRFTOKEN': token}
    if origin:
        headers['HTTP_ORIGIN'] = origin
    response = client.post('/api/graphql/', {'query': 'query { __typename }'}, format='json', **headers)
    assert response.status_code == (200 if origin == ORIGIN else 403), response.content


def test_anonymous_login_form_is_csrf_protected():
    client = client_for()
    response = client.post('/api/graphql/', {'query': 'query { __typename }'}, format='multipart', HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 403


def test_cookie_without_csrf_cookie_cannot_use_cookie_blocked_fallback(user_factory):
    client = client_for(user_factory())
    response = client.post(
        '/api/graphql/', {'query': UPDATE}, format='json', HTTP_ORIGIN=ORIGIN, HTTP_X_CSRFTOKEN='x' * 64
    )
    assert response.status_code == 403


@pytest.mark.parametrize('cookies_blocked', [False, True])
def test_actual_login_with_csrf_bootstrap(cookies_blocked, user_factory, faker):
    password = faker.password()
    user = user_factory()
    user.set_password(password)
    user.save()
    client = client_for()
    token = bootstrap(client)
    if cookies_blocked:
        client.cookies.clear()
    query = 'mutation($input: ObtainTokenMutationInput!) { tokenAuth(input: $input) { access refresh } }'
    response = client.post(
        '/api/graphql/',
        {'query': query, 'variables': {'input': {'email': user.email, 'password': password}}},
        format='json',
        HTTP_ORIGIN=ORIGIN,
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    assert not response.json().get('errors'), response.content
    assert response.json()['data']['tokenAuth']['access'] is None
    assert response.json()['data']['tokenAuth']['refresh'] is None
    assert response.cookies[settings.ACCESS_TOKEN_COOKIE].value
