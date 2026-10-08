"""
Tokens only ever authenticate the exact account they were issued to, and only if this database issued them.

Regression for a production incident: after the database was wiped (user IDs start over) with an unchanged signing
key, a device still holding a refresh token from before the wipe refreshed it and was logged into the *new* account
that had been given the same user ID.
"""

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User
from apps.sso.tests.factories import SSOSessionFactory
from apps.users.services.otp_login import begin_otp_login

pytestmark = pytest.mark.django_db

CURRENT_USER = {"query": "query { currentUser { email } }"}


def current_user_with_header(access_token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client.post("/api/graphql/", CURRENT_USER, format="json")


def current_user_with_cookie(access_token):
    client = APIClient()
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(access_token)
    return client.post("/api/graphql/", CURRENT_USER, format="json")


def refresh_with(refresh_token):
    return APIClient().post("/api/auth/token-refresh/", {"refresh": str(refresh_token)}, format="json")


def wipe_and_recreate_with_same_id(user, user_factory):
    """What a database wipe does: the account is gone and a new one ends up with the same user ID."""
    user_id = user.pk
    user.delete()
    return user_factory(id=user_id, email="someone.else@example.com")


class TestRecycledUserId:
    def test_refresh_token_from_before_a_wipe_is_rejected(self, user, user_factory):
        old_refresh = RefreshToken.for_user(user)
        new_owner = wipe_and_recreate_with_same_id(user, user_factory)

        response = refresh_with(old_refresh)

        assert response.status_code == 401
        assert not OutstandingToken.objects.filter(user=new_owner).exists()

    def test_access_token_from_before_a_wipe_is_rejected(self, user, user_factory):
        old_access = RefreshToken.for_user(user).access_token
        wipe_and_recreate_with_same_id(user, user_factory)

        assert current_user_with_header(old_access).status_code == 401
        # A stale cookie is treated as logged out, never as the new account
        assert current_user_with_cookie(old_access).json()["data"]["currentUser"] is None

    def test_refresh_token_is_rejected_even_if_it_were_still_recorded(self, user, user_factory):
        """The account fingerprint alone must stop it too, independent of the outstanding-token check."""
        old_refresh = RefreshToken.for_user(user)
        new_owner = wipe_and_recreate_with_same_id(user, user_factory)
        # Pretend it's recorded as issued to the new account
        OutstandingToken.objects.filter(jti=old_refresh["jti"]).update(user=new_owner)

        assert refresh_with(old_refresh).status_code == 401


class TestOnlyTokensIssuedHere:
    def test_refresh_token_not_issued_by_this_database_is_rejected(self, user):
        foreign_refresh = RefreshToken.for_user(user)
        OutstandingToken.objects.filter(jti=foreign_refresh["jti"]).delete()

        assert refresh_with(foreign_refresh).status_code == 401

    def test_normal_refresh_still_works(self, user):
        refresh = RefreshToken.for_user(user)
        SSOSessionFactory(user=user, refresh_token_jti=refresh['jti'])
        response = refresh_with(refresh)

        assert response.status_code == 200
        assert response.json() == {'success': True}
        access = response.cookies[settings.ACCESS_TOKEN_COOKIE].value
        assert current_user_with_header(access).json()["data"]["currentUser"]["email"] == user.email


class TestPasswordChange:
    def test_changing_the_password_ends_existing_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        user.set_password("A-completely-new-password-123")
        user.save()

        assert current_user_with_header(refresh.access_token).status_code == 401
        assert refresh_with(refresh).status_code == 401

    def test_passwordless_accounts_get_distinct_fingerprints(self, user_factory):
        """Social/passwordless accounts share no fingerprint, so one can't stand in for another."""
        first, second = user_factory(), user_factory()
        for account in (first, second):
            account.set_unusable_password()
            account.save()

        assert RefreshToken.for_user(first)["hash_password"] != RefreshToken.for_user(second)["hash_password"]


class TestOtpAuthToken:
    def test_otp_step_token_is_not_a_login_token(self, user):
        """The token handed out after the password step (before the 2FA code) must not authenticate on its own."""
        otp_auth_token = begin_otp_login(user, "password")

        assert current_user_with_header(otp_auth_token).status_code == 401
        assert current_user_with_cookie(otp_auth_token).json()["data"]["currentUser"] is None
