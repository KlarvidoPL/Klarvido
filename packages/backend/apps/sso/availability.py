"""
One switch for all of SSO: configuration, sign-in through SSO, enforcement and SCIM.

SSO is switched off until it is ready (SSO_CONFIGURATION_ENABLED=false). Its screens stay visible but cannot be used.
Existing SSO data is kept, so turning the switch back on restores it.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission

SSO_UNAVAILABLE_MESSAGE = "Single sign-on is not available yet."


def sso_enabled() -> bool:
    return bool(settings.SSO_CONFIGURATION_ENABLED)


class SSOEnabledPermission(BasePermission):
    """Refuses SSO configuration mutations while SSO is switched off."""

    message = SSO_UNAVAILABLE_MESSAGE

    def has_permission(self, request, view) -> bool:
        return sso_enabled()
