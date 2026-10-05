"""
Cookie-authenticated writes must carry the CSRF token. The auth cookie is attached to cross-site requests too
(depending on SameSite), so the cookie alone does not prove the request came from the web app.
"""

import pytest
from django.conf import settings
from django.middleware.csrf import _get_new_csrf_string
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.users.authentication import JSONWebTokenCookieAuthentication
from apps.users.jwt import create_jwt_tokens

pytestmark = pytest.mark.django_db


@api_view(["GET", "POST", "DELETE"])
@authentication_classes([JSONWebTokenCookieAuthentication, JWTAuthentication])
@permission_classes([IsAuthenticated])
def probe(request):
    return Response({"ok": True})


@pytest.fixture
def csrf_secret():
    return _get_new_csrf_string()


@pytest.fixture
def access_token(user):
    return create_jwt_tokens(user)["access"]


def _cookie_header(access_token, csrf_secret=None):
    cookies = f"{settings.ACCESS_TOKEN_COOKIE}={access_token}"
    if csrf_secret:
        cookies += f"; csrftoken={csrf_secret}"
    return cookies


class TestCookieAuthenticatedWrites:
    def _factory(self):
        return APIRequestFactory(enforce_csrf_checks=True)

    def test_write_with_cookie_and_no_token_is_refused(self, access_token):
        request = self._factory().post("/probe/", {}, format="json", HTTP_COOKIE=_cookie_header(access_token))

        response = probe(request)

        assert response.status_code == 403
        assert "CSRF" in str(response.data)

    def test_write_with_cookie_and_matching_token_is_allowed(self, access_token, csrf_secret):
        request = self._factory().post(
            "/probe/",
            {},
            format="json",
            HTTP_COOKIE=_cookie_header(access_token, csrf_secret),
            HTTP_X_CSRFTOKEN=csrf_secret,
        )

        response = probe(request)

        assert response.status_code == 200

    def test_write_with_a_mismatched_token_is_refused(self, access_token, csrf_secret):
        request = self._factory().post(
            "/probe/",
            {},
            format="json",
            HTTP_COOKIE=_cookie_header(access_token, csrf_secret),
            HTTP_X_CSRFTOKEN=_get_new_csrf_string(),
        )

        response = probe(request)

        assert response.status_code == 403

    def test_delete_with_cookie_and_no_token_is_refused(self, access_token):
        request = self._factory().delete("/probe/", HTTP_COOKIE=_cookie_header(access_token))

        assert probe(request).status_code == 403

    def test_read_with_cookie_needs_no_token(self, access_token):
        request = self._factory().get("/probe/", HTTP_COOKIE=_cookie_header(access_token))

        assert probe(request).status_code == 200

    def test_header_authentication_needs_no_token(self, access_token):
        """Safari with blocked cookies sends only the Authorization header. There is no cookie to forge."""
        request = self._factory().post("/probe/", {}, format="json", HTTP_AUTHORIZATION=f"Bearer {access_token}")

        assert probe(request).status_code == 200

    def test_invalid_cookie_is_anonymous_not_a_csrf_error(self):
        request = self._factory().post(
            "/probe/", {}, format="json", HTTP_COOKIE=f"{settings.ACCESS_TOKEN_COOKIE}=not-a-token"
        )

        response = probe(request)

        # Unauthenticated (401 with a Bearer challenge), not a CSRF failure
        assert response.status_code == 401
        assert "CSRF" not in str(response.data)


class TestGraphQLEndpoint:
    def test_graphql_post_with_cookie_and_no_token_is_refused(self, user, access_token):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.ACCESS_TOKEN_COOKIE] = access_token

        response = client.post("/api/graphql/", {"query": "query { __typename }"}, format="json")

        assert response.status_code == 403

    def test_graphql_post_with_matching_token_executes(self, user, access_token, csrf_secret):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.ACCESS_TOKEN_COOKIE] = access_token
        client.cookies["csrftoken"] = csrf_secret

        response = client.post(
            "/api/graphql/",
            {"query": "query { __typename }"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_secret,
        )

        assert response.status_code == 200
        assert response.json()["data"] == {"__typename": "Query"}


class TestCsrfBootstrap:
    def test_sets_the_csrf_cookie_and_returns_the_token(self):
        response = APIClient().get("/api/auth/csrf/")

        assert response.status_code == 200
        assert "csrftoken" in response.cookies
        assert response.json()["csrfToken"]

    def test_returned_token_is_accepted_on_a_write(self, user, access_token):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get("/api/auth/csrf/").json()["csrfToken"]
        client.cookies[settings.ACCESS_TOKEN_COOKIE] = access_token

        response = client.post(
            "/api/graphql/",
            {"query": "query { __typename }"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        assert response.status_code == 200


class TestRefreshAndLogoutCookies:
    """The refresh cookie is sent cross-site too, so using it must carry the CSRF token, like any other write."""

    @pytest.fixture
    def refresh_token(self, user):
        return create_jwt_tokens(user)["refresh"]

    def test_refresh_with_cookie_and_no_token_is_refused(self, refresh_token):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.REFRESH_TOKEN_COOKIE] = refresh_token

        response = client.post("/api/auth/token-refresh/", {}, format="json")

        assert response.status_code == 403

    def test_refresh_with_cookie_and_matching_token_succeeds(self, refresh_token, csrf_secret):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.REFRESH_TOKEN_COOKIE] = refresh_token
        client.cookies["csrftoken"] = csrf_secret

        response = client.post("/api/auth/token-refresh/", {}, format="json", HTTP_X_CSRFTOKEN=csrf_secret)

        assert response.status_code == 200

    def test_logout_with_cookie_and_no_token_is_refused(self, refresh_token):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.REFRESH_TOKEN_COOKIE] = refresh_token

        response = client.post("/api/auth/logout/", {}, format="json")

        assert response.status_code == 403

    def test_logout_with_matching_token_succeeds(self, refresh_token, csrf_secret):
        client = APIClient(enforce_csrf_checks=True)
        client.cookies[settings.REFRESH_TOKEN_COOKIE] = refresh_token
        client.cookies["csrftoken"] = csrf_secret

        response = client.post("/api/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=csrf_secret)

        assert response.status_code == 200
