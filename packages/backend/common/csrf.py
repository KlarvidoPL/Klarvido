"""CSRF protection for cookie-authenticated APIs and browser authentication flows."""

from urllib.parse import urlsplit

from django.conf import settings
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied


@never_cache
@require_GET
def csrf_token(request):
    # A response token works when frontend and API have separate host-only cookies.
    return JsonResponse({'csrfToken': get_token(request)})


def trusted_origin(request):
    origin = request.headers.get('Origin')
    if not origin or origin == 'null':
        return False
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        return False
    own_origin = f'{request.scheme}://{request.get_host()}'
    return origin in [own_origin, *settings.CSRF_TRUSTED_ORIGINS]


def enforce_api_csrf(request, explicit_credential=False):
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return
    has_auth_cookie = any(
        request.COOKIES.get(name) for name in (settings.ACCESS_TOKEN_COOKIE, settings.REFRESH_TOKEN_COOKIE)
    )
    if not has_auth_cookie:
        if request.headers.get('Authorization', '').startswith('Bearer '):
            return  # Explicit credentials cannot be attached by a cross-site HTML form.
        if (
            explicit_credential
            and request.content_type == 'application/json'
            and (not request.headers.get('Origin') or trusted_origin(request))
        ):
            return
        # Safari can block all API cookies, including the CSRF cookie, before login.
        # An explicit trusted Origin plus a custom header requires a successful CORS preflight.
        # Cookie-authenticated requests always take the full Django token-validation path below.
        if (
            not request.COOKIES.get(settings.CSRF_COOKIE_NAME)
            and trusted_origin(request)
            and request.headers.get('X-CSRFToken')
        ):
            return
    check = CSRFCheck(lambda request: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied('CSRF verification failed.', code='csrf_failed')
