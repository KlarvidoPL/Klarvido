from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .services.otp_crypto import load_keys
from aws_xray_sdk.core import xray_recorder
from config.tracing import CredentialSafeEmitter


class UsersConfig(AppConfig):
    name = "apps.users"

    def ready(self):
        if settings.TRACING_BACKEND == "xray":
            previous = xray_recorder.emitter
            xray_recorder.emitter = CredentialSafeEmitter(f"{previous.ip}:{previous.port}")
        if not settings.IS_LOCAL_DEBUG or settings.OTP_ENCRYPTION_KEYS or settings.OTP_ENCRYPTION_KEYS_FILE:
            load_keys()
        for name in (
            'AUTH_PASSWORD_RESET_TIMEOUT',
            'RESET_EMAIL_COOLDOWN_SECONDS',
            'RESET_EMAIL_DAILY_LIMIT',
            'RESET_EMAIL_GLOBAL_HOURLY_LIMIT',
        ):
            if getattr(settings, name) <= 0:
                raise ImproperlyConfigured(f'{name} must be positive')
