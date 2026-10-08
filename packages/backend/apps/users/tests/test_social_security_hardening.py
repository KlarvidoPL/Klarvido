import importlib
import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pyotp
import pytest
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, DatabaseError
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from social_django.models import UserSocialAuth

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, WebAuthnChallenge, PasskeyManagementGrant
from apps.sso.services.sessions import SessionService
from apps.translations.models import Translation, TranslationKey, Locale
from apps.users import tokens
from apps.users.serializers import UserAccountConfirmationSerializer, PasswordResetConfirmationSerializer
from apps.users.services.account_reclaim import reclaim_unconfirmed_account
from apps.users.utils import generate_otp_auth_token

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clean_throttle_cache():
    cache.clear()
    yield
    cache.clear()


def test_reclaim_invalidates_all_old_email_and_otp_proofs(user_factory):
    account = user_factory(is_confirmed=False, otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
    activation = tokens.account_activation_token.make_token(account)
    reset = tokens.password_reset_token.make_token(account)
    otp = str(generate_otp_auth_token(account))
    challenge = WebAuthnChallenge.create_challenge(user=account)
    grant = PasskeyManagementGrant.objects.create(user=account, action='register', expires_at=challenge.expires_at)
    with patch('apps.users.services.account_reclaim.notifications.PasswordResetEmail.send'):
        reclaim_unconfirmed_account(account, user_factory(is_superuser=True))
    account.refresh_from_db()
    assert not tokens.account_activation_token.check_token(account, activation)
    assert not tokens.password_reset_token.check_token(account, reset)
    assert tokens.account_activation_token.check_token(account, tokens.account_activation_token.make_token(account))
    assert not WebAuthnChallenge.objects.filter(pk=challenge.pk).exists()
    assert not PasskeyManagementGrant.objects.filter(pk=grant.pk).exists()
    client = APIClient()
    client.cookies[settings.OTP_AUTH_TOKEN_COOKIE] = otp
    response = client.post(
        '/api/graphql/',
        {'query': 'mutation { validateOtp(input: {otpToken: "123456"}) { authenticated } }'},
        format='json',
    )
    assert 'errors' in response.json()
    assert settings.ACCESS_TOKEN_COOKIE not in response.cookies


def test_activation_token_is_bound_to_mailbox(user):
    token = tokens.account_activation_token.make_token(user)
    user.email = 'changed@example.com'
    assert not tokens.account_activation_token.check_token(user, token)


def test_historical_review_is_read_only_and_does_not_expose_email_or_uid(user_factory):
    account = user_factory(is_confirmed=True)
    unknown = UserSocialAuth.objects.create(user=account, provider='google-oauth2', uid='private-provider-id')
    proven = UserSocialAuth.objects.create(user=account, provider='facebook', uid='other-private-id')
    SSOAuditLog.log_event(
        SSOAuditEventType.SSO_LOGIN_SUCCESS,
        user=account,
        metadata={'action': 'account_linked', 'association_id': str(proven.pk), 'provider': proven.provider},
    )
    output = StringIO()
    original_password = account.password
    call_command('review_social_links', details=True, stdout=output)
    report = json.loads(output.getvalue())
    assert report['review_required'] == 1
    assert report['candidates'][0]['association_id'] == str(unknown.pk)
    assert account.email not in output.getvalue()
    assert unknown.uid not in output.getvalue()
    assert UserSocialAuth.objects.count() == 2
    account.refresh_from_db()
    assert account.password == original_password


def authenticated_client(account):
    client = APIClient()
    client.force_authenticate(account)
    return client


def association(account, provider='google-oauth2', uid='identity'):
    return UserSocialAuth.objects.create(user=account, provider=provider, uid=uid)


def unlink(client, row, password, otp=None):
    return client.post(
        '/api/auth/social-accounts/unlink/',
        {'associationId': str(row.pk), 'password': password, 'otpToken': otp or ''},
        format='json',
    )


def test_unlink_requires_password_and_revokes_sessions(user):
    row = association(user)
    refresh = RefreshToken.for_user(user)
    session, _ = SessionService(user).create_session(RequestFactory().get('/'), refresh_token_jti=refresh['jti'])
    client = authenticated_client(user)
    assert unlink(client, row, 'wrong').status_code == 403
    assert UserSocialAuth.objects.filter(pk=row.pk).exists()
    response = unlink(client, row, user._faker_password)
    assert response.status_code == 200
    assert not UserSocialAuth.objects.filter(pk=row.pk).exists()
    assert response.cookies[settings.ACCESS_TOKEN_COOKIE]['max-age'] == 0
    session.refresh_from_db()
    assert not session.is_active
    from_blacklist = APIClient().post('/api/auth/token-refresh/', {'refresh': str(refresh)}, format='json')
    assert from_blacklist.status_code == 401
    assert SSOAuditLog.objects.filter(user=user, metadata__action='account_unlinked').exists()


def test_unlink_requires_otp_and_preserves_attempt_limits(user):
    user.otp_enabled = user.otp_verified = True
    user.otp_base32 = pyotp.random_base32()
    user.save()
    row = association(user)
    client = authenticated_client(user)
    for _ in range(5):
        assert unlink(client, row, user._faker_password, 'invalid').status_code == 403
    response = unlink(client, row, user._faker_password, pyotp.TOTP(user.otp_base32).now())
    assert response.json()['code'] == 'otp_locked'
    assert UserSocialAuth.objects.filter(pk=row.pk).exists()


def test_unlink_accepts_password_plus_correct_otp(user):
    user.otp_enabled = user.otp_verified = True
    user.otp_base32 = pyotp.random_base32()
    user.save()
    row = association(user)
    assert (
        unlink(authenticated_client(user), row, user._faker_password, pyotp.TOTP(user.otp_base32).now()).status_code
        == 200
    )


def test_unlink_is_owner_scoped(user, user_factory):
    row = association(user_factory())
    client = authenticated_client(user)
    assert unlink(client, row, user._faker_password).status_code == 403
    assert client.get('/api/auth/social-accounts/').json()['accounts'] == []
    assert UserSocialAuth.objects.filter(pk=row.pk).exists()


def test_unlink_prevents_last_method_lockout(user):
    user.set_unusable_password()
    user.save()
    row = association(user)
    client = authenticated_client(user)
    assert client.get('/api/auth/social-accounts/').json()['accounts'][0]['canUnlink'] is False
    response = client.post('/api/auth/social-accounts/unlink/options/', {'associationId': str(row.pk)}, format='json')
    assert response.status_code == 403
    assert UserSocialAuth.objects.filter(pk=row.pk).exists()


def test_unlink_rejects_unauthenticated_requests():
    assert APIClient().get('/api/auth/social-accounts/').status_code in (401, 403)
    assert APIClient().post('/api/auth/social-accounts/unlink/', {}, format='json').status_code in (401, 403)


def test_unlink_enforces_cookie_csrf(user):
    client = APIClient(enforce_csrf_checks=True)
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    row = association(user)
    assert unlink(client, row, user._faker_password).status_code == 403
    assert UserSocialAuth.objects.filter(pk=row.pk).exists()


def test_reclaim_between_confirmation_validation_and_save_cannot_restore_credentials(user_factory):
    account = user_factory(is_confirmed=False)
    token = tokens.account_activation_token.make_token(account)
    serializer = UserAccountConfirmationSerializer(data={'user': str(account.pk), 'token': token})
    assert serializer.is_valid(), serializer.errors
    with patch('apps.users.services.account_reclaim.notifications.PasswordResetEmail.send'):
        reclaim_unconfirmed_account(account, user_factory(is_superuser=True))
    with pytest.raises(ValidationError):
        serializer.save()
    account.refresh_from_db()
    assert not account.is_confirmed
    assert not account.has_usable_password()


def test_unlink_storage_failure_rolls_back_removal(user):
    row = association(user)
    with patch('apps.users.services.social_unlink.SessionService.revoke_all_sessions', side_effect=DatabaseError):
        response = unlink(authenticated_client(user), row, user._faker_password)
    assert response.status_code == 503
    assert UserSocialAuth.objects.filter(pk=row.pk).exists()
    assert not SSOAuditLog.objects.filter(metadata__action='account_unlinked').exists()


def test_translation_migration_replaces_english_placeholders_and_preserves_custom_text():
    seed = importlib.import_module('apps.translations.migrations.0005_social_security_translations')
    for code in ['en', 'pl', 'de', 'fr', 'es', 'zh', 'hi', 'ar']:
        Locale.objects.get_or_create(code=code, defaults={'name': code, 'native_name': code})
    seed.seed_security_translations(apps, SimpleNamespace(connection=connection))
    key = TranslationKey.objects.get(key='Social accounts / Disconnect')
    polish = Translation.objects.get(key=key, locale__code='pl')
    polish.value = 'Disconnect'
    polish.save()
    french = Translation.objects.get(key=key, locale__code='fr')
    french.value = 'Custom reviewed translation'
    french.save()
    seed.seed_security_translations(apps, SimpleNamespace(connection=connection))
    polish.refresh_from_db()
    french.refresh_from_db()
    assert polish.value == 'Odłącz'
    assert french.value == 'Custom reviewed translation'
    assert (
        Translation.objects.filter(key=key, locale__code__in=['en', 'pl', 'de', 'fr', 'es', 'zh', 'hi', 'ar']).count()
        == 8
    )



def test_reclaim_between_reset_validation_and_save_invalidates_old_reset_proof(user_factory):
    account = user_factory(is_confirmed=False)
    token = tokens.password_reset_token.make_token(account)
    serializer = PasswordResetConfirmationSerializer(
        data={'user': str(account.pk), 'token': token, 'new_password': 'SecureReplacementPassword!482'}
    )
    assert serializer.is_valid(), serializer.errors
    with patch('apps.users.services.account_reclaim.notifications.PasswordResetEmail.send'):
        reclaim_unconfirmed_account(account, user_factory(is_superuser=True))
    with pytest.raises(ValidationError):
        serializer.save()
    account.refresh_from_db()
    assert not account.has_usable_password()
    assert not account.is_confirmed
