"""
Encrypt OIDC client secrets that were stored in plaintext before SSO_ENCRYPTION_KEYS existed.

Run once per environment after the key is configured:
    python manage.py encrypt_oidc_client_secrets
Safe to run again: connections that are already encrypted are skipped.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.sso.crypto import SSOEncryptionNotConfigured, ensure_encryption_configured
from apps.sso.models import TenantSSOConnection


class Command(BaseCommand):
    help = "Encrypt plaintext OIDC client secrets and clear the plaintext copies"

    def handle(self, *args, **options):
        try:
            ensure_encryption_configured()
        except SSOEncryptionNotConfigured as e:
            raise CommandError(str(e))

        legacy = TenantSSOConnection.objects.exclude(oidc_client_secret="").filter(
            oidc_client_secret_encrypted__isnull=True
        )
        migrated = 0
        for connection in legacy:
            connection.set_oidc_client_secret(connection.oidc_client_secret)
            connection.save(update_fields=["oidc_client_secret", "oidc_client_secret_encrypted"])
            migrated += 1

        self.stdout.write(f"Encrypted {migrated} OIDC client secret(s).")
