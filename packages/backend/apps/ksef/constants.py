from django.db import models


class KsefEnvironment(models.TextChoices):
    """KSeF API environments. Selected per deployment via KSEF_ENVIRONMENT, never per organization."""

    TEST = "test", "Test"
    DEMO = "demo", "Demo"
    PROD = "prod", "Production"


KSEF_BASE_URLS = {
    KsefEnvironment.TEST: "https://api-test.ksef.mf.gov.pl/v2",
    KsefEnvironment.DEMO: "https://api-demo.ksef.mf.gov.pl/v2",
    KsefEnvironment.PROD: "https://api.ksef.mf.gov.pl/v2",
}


class KsefCredentialStatus(models.TextChoices):
    """Result of the last check of a stored KSeF token."""

    VALID = "VALID", "Valid"
    UNVERIFIED = "UNVERIFIED", "Not verified"
    INVALID = "INVALID", "Invalid"


class KsefErrorCode(models.TextChoices):
    """Stable error codes returned to the frontend, which maps them to translated messages."""

    INVALID_TOKEN = "INVALID_TOKEN", "KSeF rejected the token"
    NO_PERMISSIONS = "NO_PERMISSIONS", "Token has no permissions for this company"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE", "KSeF is unavailable"
    COUNTRY_NOT_SUPPORTED = "COUNTRY_NOT_SUPPORTED", "KSeF is only available for Polish organizations"
    NIP_MISSING = "NIP_MISSING", "Organization has no NIP"
    TOKEN_EMPTY = "TOKEN_EMPTY", "Token is empty or too long"
    ENCRYPTION_NOT_CONFIGURED = "ENCRYPTION_NOT_CONFIGURED", "Token encryption key is not configured"
    DECRYPTION_FAILED = "DECRYPTION_FAILED", "Stored token could not be decrypted"
    NOT_CONFIGURED = "NOT_CONFIGURED", "No KSeF token is saved"


MAX_TOKEN_LENGTH = 512
