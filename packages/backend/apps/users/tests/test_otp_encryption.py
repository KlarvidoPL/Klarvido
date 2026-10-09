"""Encryption-at-rest and rotation invariants; do not execute until final verification."""
import base64
import io
import importlib
from types import SimpleNamespace

import pyotp
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import connection, models
from django.test.utils import isolate_apps

from apps.users.services.credentials import credential_version
from apps.users.services.otp import validate_otp, disable_otp
from apps.users.services.otp_crypto import encrypt_seed, decrypt_seed, OTPDecryptionError

pytestmark = pytest.mark.django_db
OLD = base64.b64encode(b'a' * 32).decode()
NEW = base64.b64encode(b'b' * 32).decode()


def test_database_has_no_plaintext_seed_or_url(user_factory, settings):
    settings.OTP_ENCRYPTION_KEYS = OLD
    seed = pyotp.random_base32()
    user = user_factory(otp_base32=seed, otp_pending_base32=seed, otp_verified=True, otp_enabled=True)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT otp_seed_encrypted, otp_pending_seed_encrypted FROM users_user WHERE id = %s', [int(user.pk)]
        )
        active, pending = cursor.fetchone()
    assert seed not in active and seed not in pending
    user.refresh_from_db()
    assert user.otp_base32 == seed and user.otp_pending_base32 == seed
    assert f'secret={seed}' in user.otp_auth_url
    validate_otp(user, pyotp.TOTP(seed).now())


def test_ciphertext_is_bound_to_account_and_purpose(settings):
    settings.OTP_ENCRYPTION_KEYS = OLD
    value = encrypt_seed(1, 'active', 'PRIVATESEED')
    for user_id, purpose in ((2, 'active'), (1, 'pending')):
        with pytest.raises(OTPDecryptionError):
            decrypt_seed(user_id, purpose, value)
    with pytest.raises(OTPDecryptionError):
        decrypt_seed(1, 'active', value[:-3] + 'AAAA')


def test_rotation_preserves_credential_proofs_and_authenticator(user_factory, settings):
    settings.OTP_ENCRYPTION_KEYS = OLD
    seed = pyotp.random_base32()
    user = user_factory(otp_base32=seed, otp_enabled=True, otp_verified=True)
    before = credential_version(user)
    settings.OTP_ENCRYPTION_KEYS = f'{NEW},{OLD}'
    output = io.StringIO()
    call_command('rotate_otp_keys', stdout=output)
    settings.OTP_ENCRYPTION_KEYS = NEW
    user.refresh_from_db()
    assert user.otp_base32 == seed
    assert credential_version(user) == before
    validate_otp(user, pyotp.TOTP(seed).now())
    assert seed not in output.getvalue()


def test_missing_key_has_no_plaintext_fallback(settings):
    settings.OTP_ENCRYPTION_KEYS = ''
    settings.OTP_ENCRYPTION_KEYS_FILE = ''
    with pytest.raises(ImproperlyConfigured):
        encrypt_seed(1, 'active', 'PRIVATESEED')


def test_disabling_clears_both_ciphertexts(user_factory, settings):
    settings.OTP_ENCRYPTION_KEYS = OLD
    user = user_factory(otp_base32=pyotp.random_base32(), otp_pending_base32=pyotp.random_base32())
    disable_otp(user)
    user.refresh_from_db()
    assert user.otp_seed_encrypted == user.otp_pending_seed_encrypted == ''


@pytest.mark.django_db(transaction=True)
def test_existing_plaintext_seeds_are_converted_before_columns_are_removed(settings):
    # Exercise the real data migration against a temporary legacy-shaped PostgreSQL table.
    settings.OTP_ENCRYPTION_KEYS = OLD
    with isolate_apps():

        class LegacyUser(models.Model):
            otp_base32 = models.CharField(max_length=255, default='')
            otp_pending_base32 = models.CharField(max_length=255, default='')
            otp_auth_url = models.CharField(max_length=255, default='')
            otp_pending_auth_url = models.CharField(max_length=255, default='')
            otp_seed_encrypted = models.TextField(default='')
            otp_pending_seed_encrypted = models.TextField(default='')

            class Meta:
                app_label = 'users'
                db_table = 'test_legacy_otp_conversion'

        with connection.schema_editor() as editor:
            editor.create_model(LegacyUser)
        try:
            active, pending = pyotp.random_base32(), pyotp.random_base32()
            legacy = LegacyUser.objects.create(otp_base32=active, otp_pending_base32=pending)
            migration = importlib.import_module(
                'apps.users.migrations.0013_resetemaillimit_remove_user_otp_auth_url_and_more'
            )
            with connection.schema_editor() as editor:
                migration.encrypt_existing_seeds(SimpleNamespace(get_model=lambda *args: LegacyUser), editor)
                for field in ('otp_base32', 'otp_pending_base32', 'otp_auth_url', 'otp_pending_auth_url'):
                    editor.remove_field(LegacyUser, LegacyUser._meta.get_field(field))
            encrypted, pending_encrypted = LegacyUser.objects.values_list(
                'otp_seed_encrypted', 'otp_pending_seed_encrypted'
            ).get(pk=legacy.pk)
            assert decrypt_seed(legacy.pk, 'active', encrypted) == active
            assert decrypt_seed(legacy.pk, 'pending', pending_encrypted) == pending
            with connection.cursor() as cursor:
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, LegacyUser._meta.db_table)
                }
            assert 'otp_base32' not in columns and 'otp_auth_url' not in columns
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(LegacyUser)
