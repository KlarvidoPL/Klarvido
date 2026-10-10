"""Replay the external deletion ledger after restoring an older database."""

import json
import re
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Max
from apps.users.models import AccountDeletion, User
from apps.users.services.deletion import delete_account
from common.storages import get_user_exports_storage


class Command(BaseCommand):
    help = 'Reapply external account deletion markers after database restoration, before opening access.'

    def add_arguments(self, parser):
        parser.add_argument('--administrator-id', required=True)

    def handle(self, *args, **options):
        storage = get_user_exports_storage()
        actor = User.objects.filter(pk=options['administrator_id'], is_superuser=True, is_active=True).first()
        if actor is None:
            raise CommandError('An active administrator is required.')
        try:
            _, files = storage.listdir('account-deletions')
        except FileNotFoundError:
            files = []
        markers = []
        for name in files:
            if not re.fullmatch(r'[A-Za-z0-9_-]+\.json', name):
                raise CommandError('Invalid external marker filename.')
            with storage.open(f'account-deletions/{name}', 'rb') as source:
                marker = json.load(source)
            if marker.get('account_id') != name[:-5]:
                raise CommandError('External marker identity does not match its filename.')
            try:
                decoded = User._meta.pk.to_python(marker['account_id'])
                if str(decoded) != marker['account_id']:
                    raise ValueError('Noncanonical identity')
            except (TypeError, ValueError):
                raise CommandError('Invalid account identity in deletion marker.')
            markers.append(marker['account_id'])
        if str(actor.pk) in markers:
            raise CommandError('The chosen administrator was deleted. Select a surviving administrator.')
        request = SimpleNamespace(user=actor, META={}, headers={})
        User.objects.filter(pk__in=markers).update(is_active=False)
        failures = []
        for account_id in markers:
            if User.objects.filter(pk=account_id).exists():
                try:
                    delete_account(account_id, request, restoration=True)
                except Exception:
                    failures.append(account_id)
            else:
                AccountDeletion.objects.get_or_create(account_id=account_id, defaults={'actor_id': str(actor.pk)})
        if failures:
            raise CommandError(
                f'{len(failures)} disabled accounts require cleanup review. Keep maintenance mode enabled.'
            )
        if markers and connection.vendor == 'postgresql':
            # An older DB also restores an older sequence. Never reuse a deleted identity.
            largest_deleted = max(int(User._meta.pk.to_python(value)) for value in markers)
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_get_serial_sequence(%s, %s)', [User._meta.db_table, User._meta.pk.column])
                sequence = cursor.fetchone()[0]
                if sequence:
                    identifier = '.'.join(connection.ops.quote_name(part) for part in sequence.split('.'))
                    cursor.execute(
                        f'SELECT last_value FROM {identifier}'  # noqa: S608 -- quoted server-provided sequence
                    )
                    current = cursor.fetchone()[0]
                    largest_live = User.objects.aggregate(value=Max('pk'))['value']
                    cursor.execute(
                        'SELECT setval(%s, %s, true)', [sequence, max(current, largest_deleted, int(largest_live or 0))]
                    )
        self.stdout.write(self.style.SUCCESS(f'Reconciled {len(markers)} deleted account identities.'))
