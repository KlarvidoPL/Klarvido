"""Produce a read-only inventory for support; never automatically reclaim accounts."""

import json

from django.core.management.base import BaseCommand

from apps.users.services.social_link_review import historical_link_candidates


class Command(BaseCommand):
    help = 'Review social links without recorded fresh ownership proof (read-only; no emails or provider UIDs).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--details', action='store_true', help='Include account IDs and credential/membership counts'
        )

    def handle(self, *args, **options):
        candidates = list(historical_link_candidates())
        result = {
            'review_required': len(candidates),
            'with_password': sum(row['has_password'] for row in candidates),
            'with_otp': sum(row['has_otp'] for row in candidates),
            'with_passkeys': sum(bool(row['active_passkeys']) for row in candidates),
            'with_memberships': sum(bool(row['memberships']) for row in candidates),
            'note': 'Missing proof does not establish abuse. Verify mailbox ownership and review credentials and '
            'memberships before any recovery. Confirmed accounts require incident review, not unconfirmed reclaim.',
        }
        if options['details']:
            result['candidates'] = candidates
        self.stdout.write(json.dumps(result, indent=2))
