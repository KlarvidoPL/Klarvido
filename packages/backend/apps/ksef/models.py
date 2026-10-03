"""
Models for the KSeF integration.
"""

import hashid_field
from django.conf import settings
from django.db import models

from common.models import TenantDependentModelMixin, TimestampedMixin

from .constants import KsefCredentialStatus


class KsefCredential(TimestampedMixin, TenantDependentModelMixin):
    """
    The KSeF token of an organization. One per tenant.

    The token itself is only stored encrypted (see apps.ksef.crypto); nothing in this model, and nothing exposed through
    GraphQL, carries the plaintext. The hint is the last 4 characters, for display only.
    """

    id = hashid_field.HashidAutoField(primary_key=True)

    encrypted_token = models.BinaryField(help_text="AES-256-GCM payload, see apps.ksef.crypto")
    token_hint = models.CharField(max_length=16, help_text="Last characters of the token, for display")
    token_name = models.CharField(
        max_length=255, blank=True, default="", help_text="Name of the token in KSeF (not secret)"
    )
    status = models.CharField(max_length=16, choices=KsefCredentialStatus.choices)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # Bound to the tenant and the server key: a restored backup could never decrypt it on another instance, and the
    # plaintext must never be written into backup archives. Organizations re-enter the token after a restore.
    _backup_excluded = True

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="ksef_one_credential_per_tenant"),
        ]

    def __str__(self):
        return f"KSeF credential ({self.token_hint})"
