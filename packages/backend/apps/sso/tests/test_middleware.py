from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.sso.middleware import SessionActivityMiddleware
from apps.sso.models import SSOSession

from . import factories

pytestmark = pytest.mark.django_db

STALE = timedelta(hours=1)


def make_stale(session):
    SSOSession.objects.filter(pk=session.pk).update(last_activity_at=timezone.now() - STALE)


def run_middleware(user, session_id):
    request = RequestFactory().get("/")
    request.user = user
    request.COOKIES[settings.SESSION_ID_COOKIE] = session_id
    return SessionActivityMiddleware(lambda request: HttpResponse())(request)


def last_activity(session):
    return SSOSession.objects.get(pk=session.pk).last_activity_at


class TestSessionActivityMiddleware:
    def test_authenticated_request_records_activity(self, user):
        session = factories.SSOSessionFactory(user=user)
        make_stale(session)
        before = timezone.now()

        run_middleware(user, session.session_id)

        assert last_activity(session) >= before

    def test_writes_at_most_once_per_interval(self, user):
        session = factories.SSOSessionFactory(user=user)
        make_stale(session)
        run_middleware(user, session.session_id)

        make_stale(session)
        run_middleware(user, session.session_id)

        # The second request fell within the same interval, so it didn't write again
        assert last_activity(session) < timezone.now() - STALE + timedelta(minutes=1)

    def test_ignores_anonymous_requests(self, user):
        session = factories.SSOSessionFactory(user=user)
        make_stale(session)

        run_middleware(AnonymousUser(), session.session_id)

        assert last_activity(session) < timezone.now() - timedelta(minutes=30)

    def test_ignores_another_users_session(self, user, user_factory):
        session = factories.SSOSessionFactory(user=user_factory())
        make_stale(session)

        run_middleware(user, session.session_id)

        assert last_activity(session) < timezone.now() - timedelta(minutes=30)

    def test_graphql_request_authenticated_by_jwt_records_activity(self, user):
        """API requests are authenticated by DRF inside the view - the middleware must still see that user."""
        session = factories.SSOSessionFactory(user=user)
        make_stale(session)
        client = APIClient()
        client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
        client.cookies[settings.SESSION_ID_COOKIE] = session.session_id
        before = timezone.now()

        response = client.post("/api/graphql/", {"query": "{ currentUser { email } }"}, format="json")

        assert response.status_code == 200
        assert response.json()["data"]["currentUser"]["email"] == user.email
        assert last_activity(session) >= before
