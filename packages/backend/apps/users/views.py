from config import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt import views as jwt_views, tokens as jwt_tokens
from rest_framework_simplejwt.views import TokenViewBase
from social_core.actions import do_complete
from social_django.utils import psa

from common.csrf import enforce_api_csrf

from . import serializers, utils


class CookieTokenRefreshView(jwt_views.TokenRefreshView):
    """Use the refresh token from an HTTP-only cookie and generate new pair (access, refresh)

    post:
    This endpoint is implemented with normal non-GraphQL request because it needs access to a refresh token cookie,
    which is an HTTP-only cookie with a path property set; this means the cookie is never sent to the GraphQL
    endpoint, thus preventing us from adding it to a blacklist.
    """

    serializer_class = serializers.CookieTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        enforce_api_csrf(request, explicit_credential=bool(request.data.get("refresh")))
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid(raise_exception=False):
            response = Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)
            utils.reset_auth_cookie(response)
            return response

        response = Response({"success": True}, status=status.HTTP_200_OK)

        utils.set_auth_cookie(
            response,
            {
                settings.ACCESS_TOKEN_COOKIE: serializer.data.get("access"),
                settings.REFRESH_TOKEN_COOKIE: serializer.data.get("refresh"),
            },
        )
        return response


class LogoutView(TokenViewBase):
    """Clear cookies containing auth cookies and add refresh token to a blacklist.

    post:
    Logout is implemented with normal non-GraphQL request because it needs access to a refresh token cookie,
    which is an HTTP-only cookie with a path property set; this means the cookie is never sent to the GraphQL
    endpoint, thus preventing us from adding it to a blacklist.

    This endpoint is designed to be "graceful" - it always succeeds and clears cookies,
    even if the refresh token is missing, invalid, or already expired. This ensures
    users can always log out regardless of their token state.
    """

    permission_classes = ()
    serializer_class = serializers.LogoutSerializer

    def post(self, request, *args, **kwargs):
        enforce_api_csrf(request, explicit_credential=bool(request.data.get("refresh")))
        serializer = self.get_serializer(data=request.data)
        # Always try to process logout - serializer is designed to be graceful
        if serializer.is_valid(raise_exception=False):
            serializer.save()

        # Always return success and clear cookies
        response = Response({"ok": True}, status=status.HTTP_200_OK)
        utils.reset_auth_cookie(response)
        return response


@never_cache
@csrf_exempt
@psa("social:complete")
def complete(request, backend, *args, **kwargs):
    """Authentication complete view"""

    def _do_login(backend, user, social_user):
        user.backend = "{0}.{1}".format(backend.__module__, backend.__class__.__name__)

        if user.otp_verified and user.otp_enabled:
            otp_auth_token = utils.generate_otp_auth_token(user)
            backend.strategy.set_otp_auth_token(otp_auth_token)
        else:
            token = jwt_tokens.RefreshToken.for_user(user)
            # Without this, get_auth_method_from_token() defaults missing claims
            # to 'password', which would misclassify this session to
            # should_enforce_sso_for_session() (apps/sso/enforcement.py) -
            # harmless there (still enforced) but wrong for any future check
            # that treats 'password' and 'oauth' differently.
            token['auth_method'] = 'oauth'
            token.access_token['auth_method'] = 'oauth'
            backend.strategy.set_jwt(token)

            try:
                from apps.sso.services import SessionService

                from .jwt import get_jti_from_refresh_token

                session_service = SessionService(user)
                _, session_id = session_service.create_session(
                    request, refresh_token_jti=get_jti_from_refresh_token(str(token))
                )
                backend.strategy.set_session_id(session_id)
            except Exception:
                # Don't fail login if session creation fails (mirrors
                # apps/users/schema.py::_create_session_for_user).
                pass

            # do_complete() sets this in-memory attribute (not persisted) on the
            # very first signup, before calling this callback - used to show the
            # welcome modal once, same as the password-signup flow already does.
            backend.strategy.set_is_new_signup(getattr(user, "is_new", False))

    # Always resolve the account fresh from the chosen social identity (email/uid) -
    # never from whatever user is already authenticated in this browser. Passing the
    # ambient request.user here would make "Sign in with Google" silently associate
    # (and log back into) the *current* session's user regardless of which Google
    # account was picked, instead of the account that identity actually belongs to.
    return do_complete(
        request.backend,
        _do_login,
        user=None,
        redirect_name=REDIRECT_FIELD_NAME,
        request=request,
        *args,  # noqa: B026
        **kwargs,
    )
