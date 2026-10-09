"""E13/E14/E15 regressions. Execute with the final security verification suite."""

import json
from datetime import timedelta
from unittest.mock import patch

import pyotp
import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.test import RequestFactory, Client
from django.utils import timezone
from rest_framework.test import APIClient

from apps.sso.models import SSOAuditLog, SSOSession
from apps.users import tokens
from apps.users.exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure
from apps.users.models import User, SecurityEmailOutbox, SignupEmailCooldown
from apps.users.services import otp
from apps.users.services.security import client_ip, record, enqueue_email, process_outbox
from apps.users.tasks import cleanup_authentication_records
from config import settings

pytestmark = pytest.mark.django_db
PASSWORD = 'Private-password-7319!'
SIGNUP = '''mutation($input: SingUpMutationInput!) {
    signUp(input: $input) { ok id email authenticated access refresh }
}'''
LOGIN = '''mutation($input: ObtainTokenMutationInput!) {
    tokenAuth(input: $input) { authenticated otpRequired }
}'''


def test_signup_logs_in_unverified_user_and_queues_activation():
    client = APIClient()
    response = client.post(
        '/api/graphql/',
        {
            'query': SIGNUP,
            'variables': {'input': {'email': 'new-owner@example.com', 'password': PASSWORD, 'language': 'pl'}},
        },
        format='json',
    )
    payload = response.json()['data']['signUp']
    assert payload['authenticated'] is True
    assert payload['access'] is None
    assert payload['refresh'] is None
    account = User.objects.get(email='new-owner@example.com')
    assert not account.is_confirmed
    assert account.check_password(PASSWORD)
    assert SSOSession.objects.filter(user=account).exists()
    assert SecurityEmailOutbox.objects.get(user=account).kind == 'ACCOUNT_ACTIVATION'
    assert SSOAuditLog.objects.get(event_type='auth_signup', success=True).user == account
    for name in (settings.ACCESS_TOKEN_COOKIE, settings.REFRESH_TOKEN_COOKIE, settings.SESSION_ID_COOKIE):
        assert name in response.cookies


def test_unverified_user_can_still_sign_in(user_factory):
    account = user_factory(is_confirmed=False)
    account.set_password(PASSWORD)
    account.save(update_fields=['password'])
    response = APIClient().post(
        '/api/graphql/',
        {
            'query': LOGIN,
            'variables': {'input': {'email': account.email, 'password': PASSWORD}},
        },
        format='json',
    )
    assert response.json()['data']['tokenAuth']['authenticated'] is True
    assert SSOSession.objects.filter(user=account).exists()


def test_failed_password_login_is_durable_and_redacted(user_factory):
    account = user_factory()
    response = APIClient().post(
        '/api/graphql/',
        {
            'query': LOGIN,
            'variables': {'input': {'email': account.email, 'password': PASSWORD}},
        },
        format='json',
    )
    assert response.json().get('errors')
    event = SSOAuditLog.objects.get(event_type='auth_password_login')
    assert not event.success
    assert event.metadata['account_id'] == str(account.pk)
    assert event.metadata['actor_id'] == 'anonymous'
    assert account.email not in json.dumps(event.metadata)
    assert PASSWORD not in json.dumps(event.metadata)
    assert not SecurityEmailOutbox.objects.exists()


def test_unknown_login_attempt_is_correlated_without_plaintext_email():
    email = 'unknown-private@example.com'
    response = APIClient().post(
        '/api/graphql/',
        {
            'query': LOGIN,
            'variables': {'input': {'email': email, 'password': PASSWORD}},
        },
        format='json',
    )
    assert response.json().get('errors')
    event = SSOAuditLog.objects.get(event_type='auth_password_login')
    assert event.user_id is None
    assert len(event.metadata['email_identifier']) == 64
    assert event.metadata['correlation_id']
    assert email not in json.dumps(event.metadata)


def test_successful_login_is_recorded_only_after_session_creation(user_factory):
    account = user_factory()
    account.set_password(PASSWORD)
    account.save(update_fields=['password'])
    with patch('apps.sso.services.SessionService.create_session', side_effect=RuntimeError('private detail')):
        response = APIClient().post(
            '/api/graphql/',
            {
                'query': LOGIN,
                'variables': {'input': {'email': account.email, 'password': PASSWORD}},
            },
            format='json',
        )
    assert response.json().get('errors')
    assert not SSOAuditLog.objects.filter(event_type='auth_password_login', success=True).exists()
    assert SSOAuditLog.objects.filter(event_type='auth_password_login', success=False).exists()


def test_password_change_and_alert_roll_back_if_audit_storage_fails(user_factory):
    account = user_factory()
    account.set_password(PASSWORD)
    account.save(update_fields=['password'])
    client = APIClient()
    client.force_authenticate(account)
    with patch('apps.users.serializers.record', side_effect=RuntimeError('audit unavailable')):
        response = client.post(
            '/api/graphql/',
            {
                'query': '''mutation($input: ChangePasswordMutationInput!) {
                changePassword(input: $input) { authenticated }
            }''',
                'variables': {'input': {'oldPassword': PASSWORD, 'newPassword': 'Changed-password-482!'}},
            },
            format='json',
        )
    assert response.json().get('errors')
    account.refresh_from_db()
    assert account.check_password(PASSWORD)
    assert not SecurityEmailOutbox.objects.exists()


def test_reset_completion_records_change_and_alert(user_factory):
    account = user_factory()
    token = tokens.password_reset_token.make_token(account)
    response = APIClient().post(
        '/api/graphql/',
        {
            'query': '''mutation($input: PasswordResetConfirmationMutationInput!) {
            passwordResetConfirm(input: $input) { ok }
        }''',
            'variables': {'input': {'user': str(account.pk), 'token': token, 'newPassword': PASSWORD}},
        },
        format='json',
    )
    assert not response.json().get('errors'), response.content
    assert SSOAuditLog.objects.filter(user=account, event_type='auth_password_reset', success=True).exists()
    assert SecurityEmailOutbox.objects.get(user=account).kind == 'PASSWORD_CHANGED'
    assert token not in json.dumps(SSOAuditLog.objects.get(event_type='auth_password_reset').metadata)


def test_otp_replacement_has_distinct_alert_and_failed_attempts_persist(user_factory):
    secret = pyotp.random_base32()
    account = user_factory(
        otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32(), otp_pending_base32=secret
    )
    otp.verify_otp(account, pyotp.TOTP(secret).now())
    assert SecurityEmailOutbox.objects.get(user=account).kind == 'OTP_REPLACED'
    assert SSOAuditLog.objects.filter(
        user=account, event_type='auth_otp_management', metadata__outcome='replaced'
    ).exists()
    for _ in range(5):
        with pytest.raises((OTPAttemptLimitExceeded, OTPVerificationFailure)):
            otp.validate_otp(account, 'invalid')
    account.refresh_from_db()
    assert account.otp_locked_until > timezone.now()
    assert SSOAuditLog.objects.filter(event_type='auth_otp_verification', success=False).count() == 5
    assert SSOAuditLog.objects.filter(metadata__outcome='locked').exists()


def test_outbox_is_transactional_and_survives_delivery_failure(user_factory):
    account = user_factory()
    with pytest.raises(RuntimeError), transaction.atomic():
        enqueue_email(account, 'PASSWORD_CHANGED')
        raise RuntimeError('rollback')
    assert not SecurityEmailOutbox.objects.exists()
    row = enqueue_email(account, 'PASSWORD_CHANGED')
    with patch('apps.users.services.security.deliver_email_message', side_effect=RuntimeError('secret payload')):
        process_outbox()
    row.refresh_from_db()
    assert row.sent_at is None and row.attempts == 1
    assert row.last_error == 'delivery_failed'
    assert row.next_attempt_at > timezone.now()
    row.next_attempt_at = timezone.now()
    row.save(update_fields=['next_attempt_at'])
    with patch('apps.users.services.security.deliver_email_message', return_value={'sent_emails_count': 1}) as delivery:
        process_outbox()
        process_outbox()
    delivery.assert_called_once()
    row.refresh_from_db()
    assert row.sent_at is not None


def test_outbox_exhaustion_is_visible_and_account_deletion_blocks_delivery(user_factory):
    account = user_factory()
    row = enqueue_email(account, 'PASSWORD_CHANGED')
    row.attempts = 7
    row.save(update_fields=['attempts'])
    with patch('apps.users.services.security.deliver_email_message', side_effect=RuntimeError('secret')):
        process_outbox()
    row.refresh_from_db()
    assert row.failed_at is not None
    assert row.last_error == 'delivery_failed'
    other = enqueue_email(account, 'PASSWORD_CHANGED')
    account.delete()
    with patch('apps.users.services.security.deliver_email_message') as delivery:
        process_outbox()
    delivery.assert_not_called()
    other.refresh_from_db()
    assert other.user_id is None
    assert other.cancelled_at is not None and other.sent_at is None


def test_security_events_retain_identifiers_after_account_deletion(user_factory):
    account = user_factory()
    event = record('auth_password_login', user=account, method='password')
    identifier = str(account.pk)
    account.delete()
    event.refresh_from_db()
    assert event.user_id is None
    assert event.metadata['account_id'] == identifier
    assert event.metadata['actor_id'] == identifier


def test_retention_does_not_delete_tenant_events(user_factory, settings):
    settings.AUTH_AUDIT_RETENTION_DAYS = 90
    account = user_factory()
    old = record('auth_password_login', user=account)
    tenant_event = SSOAuditLog.log_event('session_created', user=account)
    SSOAuditLog.objects.filter(pk__in=[old.pk, tenant_event.pk]).update(created_at=timezone.now() - timedelta(days=91))
    cleanup_authentication_records()
    assert not SSOAuditLog.objects.filter(pk=old.pk).exists()
    assert SSOAuditLog.objects.filter(pk=tenant_event.pk).exists()


def test_ip_and_user_agent_cannot_be_forged_by_untrusted_headers(settings):
    request = RequestFactory().get(
        '/',
        HTTP_X_FORWARDED_FOR='198.51.100.7',
        REMOTE_ADDR='203.0.113.2',
        HTTP_USER_AGENT='secret-password-reset-token',
    )
    request.user = AnonymousUser()
    settings.AUTH_AUDIT_TRUSTED_PROXIES = []
    assert client_ip(request) == '203.0.113.2'
    settings.AUTH_AUDIT_TRUSTED_PROXIES = ['203.0.113.0/24']
    assert client_ip(request) == '198.51.100.7'
    event = record('auth_password_login', request=request, success=False)
    assert 'secret-password-reset-token' not in event.user_agent


def test_google_initiation_requires_csrf_protected_post():
    client = Client(enforce_csrf_checks=True)
    url = '/api/auth/social/login/google-oauth2/'
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 403
    csrf = client.get('/api/auth/csrf/').json()['csrfToken']
    with patch('apps.users.views.do_auth') as auth:
        auth.return_value = client.get('/api/auth/csrf/')
        response = client.post(
            url, {'csrfmiddlewaretoken': csrf, 'locale': 'pl'}, HTTP_ORIGIN='http://testserver'
        )
    assert response.status_code == 200
    assert auth.call_args.kwargs['user'] is None
