"""Deployment checks for passkey settings."""

from django.core.checks import Error, Tags, register
from django.core.exceptions import ImproperlyConfigured
from .passkey_security import validate_configuration


@register(Tags.security)
def check_passkey_configuration(app_configs, **kwargs):
    try:
        validate_configuration()
    except ImproperlyConfigured as exc:
        return [Error(str(exc), id='sso.E001')]
    return []
