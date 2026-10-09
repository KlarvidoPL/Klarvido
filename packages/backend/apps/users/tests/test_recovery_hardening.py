"""E09/E10 regression cases; deferred until the final verification suite."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError as APIValidationError

from apps.users import tokens
from apps.users.models import ResetEmailLimit, SecurityEmailOutbox
from apps.users.serializers import PasswordResetSerializer, PasswordResetConfirmationSerializer, UserSignupSerializer
from apps.users.services.password_policy import validate_password
from apps.users.services.password_recovery import admit_reset
from common.ratelimiting.config import clear_config_cache

pytestmark = pytest.mark.django_db


def request(ip='192.0.2.10'):
    req = RequestFactory().post('/api/graphql/', REMOTE_ADDR=ip)
    req.user = AnonymousUser()
    return req


def reset(email, ip='192.0.2.10'):
    serializer = PasswordResetSerializer(data={'email': email}, context={'request': request(ip)})
    serializer.is_valid(raise_exception=True)
    return serializer.save()


@pytest.fixture(autouse=True)
def reset_rate_cache():
    cache.clear()
    clear_config_cache()
    yield
    clear_config_cache()


def test_recipient_cooldown_applies_across_ips_and_case(user_factory):
    user = user_factory(email='owner@example.com')
    assert reset(user.email) == {'ok': True}
    assert reset(user.email.upper(), '192.0.2.11') == {'ok': True}
    assert SecurityEmailOutbox.objects.filter(kind='PASSWORD_RESET').count() == 1
    assert ResetEmailLimit.objects.exclude(key='global').count() == 1


def test_unknown_and_inactive_addresses_have_identical_public_results(user_factory):
    inactive = user_factory(is_active=False)
    assert reset('unknown@example.com') == reset(inactive.email) == {'ok': True}
    assert not SecurityEmailOutbox.objects.exists()
    assert ResetEmailLimit.objects.exclude(key='global').count() == 2


def test_daily_and_global_limits_suppress_email(user_factory, settings):
    user = user_factory()
    reset(user.email)
    recipient = ResetEmailLimit.objects.exclude(key='global').get()
    recipient.last_queued_at -= timedelta(minutes=6)
    recipient.count = 5
    recipient.save()
    reset(user.email, '192.0.2.11')
    assert SecurityEmailOutbox.objects.count() == 1
    settings.RESET_EMAIL_GLOBAL_HOURLY_LIMIT = 1
    other = user_factory()
    assert reset(other.email, '192.0.2.12') == {'ok': True}
    assert SecurityEmailOutbox.objects.count() == 1


def test_configured_ip_policy_is_enforced(settings):
    settings.RATE_LIMITS = {'auth.password_reset': {'rate': '1/hour'}}
    clear_config_cache()
    assert admit_reset(request(), 'first@example.com', deliverable=False) == 'accepted'
    assert admit_reset(request(), 'second@example.com', deliverable=False) == 'ip_limited'


def test_shared_ip_allows_thirty_requests_across_recipients(settings):
    settings.RATE_LIMITS = {'auth.password_reset': {'rate': '30/hour'}}
    clear_config_cache()
    for index in range(30):
        assert admit_reset(request(), f'account{index}@example.com', deliverable=False) == 'accepted'
    assert admit_reset(request(), 'next@example.com', deliverable=False) == 'ip_limited'


def test_admission_failure_never_queues_an_email(user_factory):
    user = user_factory()
    with patch('apps.users.services.password_recovery.is_ratelimited', side_effect=RuntimeError('cache unavailable')):
        assert reset(user.email) == {'ok': True}
    assert not SecurityEmailOutbox.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_recipient_requests_queue_one_email(user_factory):
    user = user_factory()
    email = user.email

    def submit(index):
        try:
            return reset(email, f'192.0.2.{index + 20}')
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert results == [{'ok': True}] * 4
    assert SecurityEmailOutbox.objects.filter(kind='PASSWORD_RESET').count() == 1


def test_reset_expires_after_one_hour_without_shortening_activation(user_factory):
    user = user_factory()
    issued_at = tokens.password_reset_token._now()
    with patch.object(tokens.password_reset_token, '_now', return_value=issued_at), patch.object(
        tokens.account_activation_token, '_now', return_value=issued_at
    ):
        reset_token = tokens.password_reset_token.make_token(user)
        activation = tokens.account_activation_token.make_token(user)
    with patch.object(tokens.password_reset_token, '_now', return_value=issued_at + timedelta(seconds=3600)):
        assert tokens.password_reset_token.check_token(user, reset_token)
    with patch.object(tokens.password_reset_token, '_now', return_value=issued_at + timedelta(seconds=3601)):
        assert not tokens.password_reset_token.check_token(user, reset_token)
    with patch.object(tokens.account_activation_token, '_now', return_value=issued_at + timedelta(hours=2)):
        assert tokens.account_activation_token.check_token(user, activation)


def test_new_password_checks_email_and_profile_context(user_factory):
    user = user_factory(email='distinctive-owner@example.com')
    user.profile.first_name = 'Alexandrianna'
    user.profile.save()
    for password in ('distinctive-owner', 'Alexandrianna'):
        with pytest.raises(ValidationError):
            validate_password(password, user)
    validate_password('Quiet rivers unfold 42!', user)
    # The accepted product minimum remains eight characters.
    validate_password('Xq7!mZ2@', user)


def test_signup_context_is_available_before_account_creation():
    serializer = UserSignupSerializer(data={'email': 'predictable-owner@example.com', 'password': 'predictable-owner'})
    assert not serializer.is_valid()
    assert serializer.errors['password'][0].code == 'password_too_similar'


def test_reset_checks_proof_before_contextual_policy(user_factory):
    user = user_factory(email='predictable-owner@example.com')
    serializer = PasswordResetConfirmationSerializer(
        data={'user': str(user.pk), 'token': 'invalid', 'new_password': 'predictable-owner'}
    )
    assert not serializer.is_valid()
    assert 'new_password' not in serializer.errors
    valid = PasswordResetConfirmationSerializer(
        data={
            'user': str(user.pk),
            'token': tokens.password_reset_token.make_token(user),
            'new_password': 'predictable-owner',
        }
    )
    assert not valid.is_valid()
    assert valid.errors['new_password'][0].code == 'password_too_similar'


def test_locked_reset_rechecks_updated_profile(user_factory):
    user = user_factory(email='owner@example.com')
    password = 'Alexandrianna'
    serializer = PasswordResetConfirmationSerializer(
        data={'user': str(user.pk), 'token': tokens.password_reset_token.make_token(user), 'new_password': password}
    )
    serializer.is_valid(raise_exception=True)
    user.profile.first_name = password
    user.profile.save()
    with pytest.raises(APIValidationError):
        serializer.save()
