import pytest
import pytest_factoryboy
from django.contrib.auth.models import Group
from django.test import RequestFactory
from social_core.backends.google import GoogleOAuth2
from social_django.models import DjangoStorage

from apps.users.strategy import DjangoJWTStrategy
from common.acl.helpers import CommonGroups
from . import factories

pytest_factoryboy.register(factories.GroupFactory)
pytest_factoryboy.register(factories.UserFactory)
pytest_factoryboy.register(factories.UserProfileFactory)
pytest_factoryboy.register(factories.UserAvatarFactory)
pytest_factoryboy.register(factories.StripeCustomerFactory)


@pytest.fixture
def social_backend():
    Group.objects.get_or_create(name=CommonGroups.User)
    request = RequestFactory().get('/api/auth/social/complete/google-oauth2/')
    request.session = {}
    strategy = DjangoJWTStrategy(DjangoStorage, request=request)
    return GoogleOAuth2(strategy=strategy, redirect_uri='/')


@pytest.fixture()
def image_factory():
    return factories.image_factory


@pytest.fixture
def totp_mock(mocker):
    def _factory(verify):
        totp_mock = mocker.Mock()
        totp_mock.verify.return_value = verify
        mocker.patch("pyotp.TOTP", return_value=totp_mock)

    return _factory
