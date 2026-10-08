import json
from datetime import timedelta
from typing import Optional

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError, ErrorDetail
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.exceptions import OTPVerificationFailure
from apps.users.models import PendingOTPLogin
from apps.users.serializers import ValidateOTPSerializer
from apps.users.services.otp_login import begin_otp_login
from config import settings

pytestmark = pytest.mark.django_db


class TestValidateOTPSerializer:
    @pytest.fixture
    def context_with_request_cookies(self, mocker):
        def _factory(cookies: Optional[dict] = None):
            request = mocker.Mock()
            request.COOKIES = cookies if cookies else {}
            context = {"request": request}

            return context

        return _factory

    @staticmethod
    def assert_invalid_token(error):
        assert json.dumps(error.value.detail) == json.dumps(
            {
                'non_field_errors': [
                    ErrorDetail(string="No valid token found in cookie 'otp_auth_token'", code='invalid_token')
                ]
            }
        )

    def test_missing_otp_auth_token_cookie_raises_invalid_token_error(self, context_with_request_cookies):
        serializer = ValidateOTPSerializer(data={"otp_token": "token"}, context=context_with_request_cookies())

        with pytest.raises(ValidationError) as error:
            serializer.is_valid(raise_exception=True)

        self.assert_invalid_token(error)

    def test_invalid_otp_auth_token_cookie_raises_invalid_token_error(self, context_with_request_cookies):
        context = context_with_request_cookies({settings.OTP_AUTH_TOKEN_COOKIE: "invalid-token"})
        serializer = ValidateOTPSerializer(data={"otp_token": "token"}, context=context)

        with pytest.raises(ValidationError) as error:
            serializer.is_valid(raise_exception=True)

        self.assert_invalid_token(error)

    def test_foreign_access_token_cannot_satisfy_pending_login(self, context_with_request_cookies, user):
        # Unlike the previous self-signed-JWT design, an ordinary, otherwise-valid
        # access/refresh token string cannot hash-match any PendingOTPLogin row -
        # only begin_otp_login() can ever create one.
        token = str(RefreshToken.for_user(user).access_token)
        context = context_with_request_cookies({settings.OTP_AUTH_TOKEN_COOKIE: token})
        serializer = ValidateOTPSerializer(data={"otp_token": "token"}, context=context)

        with pytest.raises(ValidationError) as error:
            serializer.is_valid(raise_exception=True)

        self.assert_invalid_token(error)

    def test_expired_pending_login_raises_invalid_token_error(self, context_with_request_cookies, user):
        token = begin_otp_login(user, "password")
        PendingOTPLogin.objects.filter(user=user).update(expires_at=timezone.now() - timedelta(seconds=1))
        context = context_with_request_cookies({settings.OTP_AUTH_TOKEN_COOKIE: token})
        serializer = ValidateOTPSerializer(data={"otp_token": "token"}, context=context)

        with pytest.raises(ValidationError) as error:
            serializer.is_valid(raise_exception=True)

        self.assert_invalid_token(error)

    def test_pending_login_invalidated_by_password_change_raises_invalid_token_error(
        self, context_with_request_cookies, user
    ):
        token = begin_otp_login(user, "password")
        user.set_password('BrandNewPassword!9372')
        user.save()
        context = context_with_request_cookies({settings.OTP_AUTH_TOKEN_COOKIE: token})
        serializer = ValidateOTPSerializer(data={"otp_token": "token"}, context=context)

        with pytest.raises(ValidationError) as error:
            serializer.is_valid(raise_exception=True)

        self.assert_invalid_token(error)

    def test_otp_validation_failure_raises_exception(self, context_with_request_cookies, user):
        token = begin_otp_login(user, "password")
        context = context_with_request_cookies({settings.OTP_AUTH_TOKEN_COOKIE: token})
        serializer = ValidateOTPSerializer(data={"otp_token": "token"}, context=context)

        with pytest.raises(OTPVerificationFailure) as error:
            serializer.is_valid(raise_exception=True)

        assert str(error.value) == "OTP must be verified first"
