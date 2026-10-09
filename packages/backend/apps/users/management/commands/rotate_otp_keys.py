"""Resumable rotation: configure newest,old keys first; never print key/seed data."""
import base64

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.users.models import User
from apps.users.services.otp_crypto import load_keys, encrypt_seed, decrypt_seed, key_id


class Command(BaseCommand):
    help = 'Re-encrypt active/pending OTP seeds with the first configured key. Retain old keys until completion.'

    def handle(self, *args, **options):
        current_key = key_id(load_keys()[0])
        count = 0
        for pk in User.objects.order_by('pk').values_list('pk', flat=True).iterator(chunk_size=500):
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=pk)
                fields = []
                for field, purpose in (('otp_seed_encrypted', 'active'), ('otp_pending_seed_encrypted', 'pending')):
                    value = getattr(user, field)
                    if value:
                        seed = decrypt_seed(user.pk, purpose, value)
                        if base64.b64decode(value[3:])[:8] == current_key:
                            continue
                        setattr(user, field, encrypt_seed(user.pk, purpose, seed))
                        fields.append(field)
                if fields:
                    user.save(update_fields=fields)
                    count += 1
        self.stdout.write(f'OTP key rotation completed: {count} accounts processed')
