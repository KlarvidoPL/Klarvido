"""Explicit, authenticated administrative deletion using the shared lifecycle."""

from getpass import getpass

from django.core.management.base import BaseCommand, CommandError
from django.http import HttpRequest
from rest_framework.exceptions import APIException

from apps.users.models import User
from apps.users.services.deletion import delete_account
from apps.users.services.otp import validate_otp
from apps.sso.services.passkey_management import password_grant


class Command(BaseCommand):
    help = 'Delete a superuser with administrator password/OTP and typed email confirmation.'

    def add_arguments(self, parser):
        parser.add_argument('--account-id', required=True)
        parser.add_argument('--administrator-id', required=True)

    def handle(self, *args, **options):
        target = User.objects.filter(pk=options['account_id'], is_superuser=True).first()
        operator = User.objects.filter(pk=options['administrator_id'], is_superuser=True, is_active=True).first()
        if not target or not operator:
            raise CommandError('Both IDs must identify superusers; the administrator must be active.')
        if input(f'Type {target.email} to permanently delete this superuser: ') != target.email:
            raise CommandError('Confirmation did not match; nothing deleted.')
        request = HttpRequest()
        request.method = 'POST'
        request.user = operator
        try:
            request.META['HTTP_X_PASSKEY_AUTHORIZATION'] = password_grant(
                operator, {'action': 'account_delete', 'password': getpass('Administrator password: ')}
            )
            if operator.otp_enabled and operator.otp_verified:
                validate_otp(operator, getpass('Administrator authentication code: '), request)
                request._account_deletion_otp = (str(operator.pk), operator.otp_last_used_code_hash)
            delete_account(target.pk, request, via_management=True)
        except APIException as exc:
            raise CommandError(str(getattr(exc, 'detail', exc))) from exc
        self.stdout.write(self.style.SUCCESS('Superuser deleted; durable cleanup scheduled.'))
