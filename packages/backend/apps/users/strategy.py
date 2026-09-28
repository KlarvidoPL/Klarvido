from urllib.parse import urlsplit

from config import settings
from social_django.strategy import DjangoStrategy

from . import utils


class DjangoJWTStrategy(DjangoStrategy):
    def __init__(self, storage, request=None, tpl=None):
        self.refresh_token = None
        self.otp_auth_token = None
        self.is_new_signup = False
        self.session_id = None
        super(DjangoJWTStrategy, self).__init__(storage, request, tpl)

    def redirect(self, url):
        """
        This method is called multiple times by social_django in various situations.
        One of such cases is when the OAuth2 flow is complete and we redirect user
        back to the web app. In such case an HTTPOnly cookie should be set to a
        JWT created during this step.
        """
        response = super(DjangoJWTStrategy, self).redirect(url)

        if self._user_is_authenticated():
            if self.refresh_token:
                auth_cookies = {
                    settings.ACCESS_TOKEN_COOKIE: str(self.refresh_token.access_token),
                    settings.REFRESH_TOKEN_COOKIE: str(self.refresh_token),
                }
                if self.session_id:
                    auth_cookies[settings.SESSION_ID_COOKIE] = self.session_id
                utils.set_auth_cookie(response, auth_cookies)
                if self.is_new_signup:
                    # Unlike the httpOnly auth cookies above (only ever sent
                    # automatically with requests *to* the API host, so the default
                    # same-host scoping is fine), this one is read directly via
                    # document.cookie by frontend JS running on the webapp's own
                    # host - a different subdomain in production (klarvido.com vs
                    # api.klarvido.com). Without an explicit shared-parent-domain
                    # scope, the browser sets it fine but the webapp's JS can never
                    # see it. PARENT_HOST is empty in local dev (single "localhost"
                    # host for both, where the default already works).
                    parent_host = getattr(settings, "PARENT_HOST", "")
                    response.set_cookie(
                        settings.NEW_SIGNUP_COOKIE,
                        "1",
                        max_age=settings.NEW_SIGNUP_COOKIE_MAX_AGE,
                        httponly=False,
                        secure=getattr(settings, "COOKIE_SECURE", True),
                        samesite=getattr(settings, "COOKIE_SAMESITE", "Lax"),
                        path="/",
                        domain=f".{parent_host}" if parent_host else None,
                    )
            elif self.otp_auth_token:
                otp_validate_url = self._construct_otp_validate_url(url)
                response = super(DjangoJWTStrategy, self).redirect(otp_validate_url)
                cookie_secure = getattr(settings, "COOKIE_SECURE", True)
                cookie_samesite = getattr(settings, "COOKIE_SAMESITE", "Lax")
                response.set_cookie(
                    settings.OTP_AUTH_TOKEN_COOKIE,
                    str(self.otp_auth_token),
                    max_age=settings.COOKIE_MAX_AGE,
                    httponly=True,
                    secure=cookie_secure,
                    samesite=cookie_samesite,
                )

            # The token has a defined value, which means this is the
            # last step of the OAuth flow – we can flush the session
            self.session.flush()

        return response

    def set_jwt(self, token):
        self.refresh_token = token

    def set_otp_auth_token(self, token):
        self.otp_auth_token = token

    def set_session_id(self, session_id):
        self.session_id = session_id

    def set_is_new_signup(self, is_new_signup):
        self.is_new_signup = is_new_signup

    def _user_is_authenticated(self) -> bool:
        return self.refresh_token or self.otp_auth_token

    def _construct_otp_validate_url(self, url: str) -> str:
        """`url` is the full "next" redirect target (e.g. https://host/pl/auth/login) -
        build the OTP page from its origin, not by appending onto its existing path,
        or the result is a malformed, doubled-up URL that matches no frontend route."""
        locale = self.session_get("locale") or "en"
        origin = urlsplit(url)
        return f"{origin.scheme}://{origin.netloc}/{locale}{settings.OTP_VALIDATE_PATH}"
