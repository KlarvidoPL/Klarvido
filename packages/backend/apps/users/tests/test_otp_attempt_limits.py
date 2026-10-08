from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pyotp
import pytest
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from apps.users.exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure
from apps.users.models import User
from apps.users.services.otp import generate_otp, validate_otp, verify_otp
from apps.users.services.otp_login import begin_otp_login

pytestmark = pytest.mark.django_db


@pytest.fixture
def account(user_factory):
    # otp_pending_base32 mirrors otp_base32 so verify_otp (setup, checked against the
    # pending secret) and validate_otp (login, checked against the active secret)
    # exercise the same shared failed-attempt counter in these rate-limit tests.
    secret = pyotp.random_base32()
    return user_factory(otp_enabled=True, otp_verified=True, otp_base32=secret, otp_pending_base32=secret)


@pytest.mark.parametrize('check', [verify_otp, validate_otp])
def test_five_failures_lock_even_correct_codes(account, check):
    for attempt in range(5):
        expected = OTPVerificationFailure if attempt < 4 else OTPAttemptLimitExceeded
        with pytest.raises(expected):
            check(account, 'invalid')
    account.refresh_from_db()
    assert account.otp_failed_attempts == 5
    locked_until = account.otp_locked_until
    with pytest.raises(OTPAttemptLimitExceeded):
        check(account, pyotp.TOTP(account.otp_base32).now())
    account.refresh_from_db()
    assert account.otp_locked_until == locked_until  # Blocked requests cannot extend the cooldown.
    assert account.otp_failed_attempts == 5


@pytest.mark.parametrize('check', [verify_otp, validate_otp])
def test_cooldown_expires(account, check, freezer):
    for _ in range(5):
        with pytest.raises(OTPVerificationFailure if account.otp_failed_attempts < 4 else OTPAttemptLimitExceeded):
            check(account, 'invalid')
    freezer.move_to(account.otp_locked_until)
    check(account, pyotp.TOTP(account.otp_base32).now())
    account.refresh_from_db()
    assert account.otp_failed_attempts == 0
    assert account.otp_locked_until is None


@pytest.mark.parametrize('check', [verify_otp, validate_otp])
def test_success_resets_failures(account, check):
    with pytest.raises(OTPVerificationFailure):
        check(account, 'invalid')
    check(account, pyotp.TOTP(account.otp_base32).now())
    account.refresh_from_db()
    assert account.otp_failed_attempts == 0
    assert account.otp_locked_until is None


def test_setup_and_login_share_counter_and_regeneration_does_not_reset(account):
    for check in [verify_otp, validate_otp, verify_otp, validate_otp]:
        with pytest.raises(OTPVerificationFailure):
            check(User.objects.get(pk=account.pk), 'invalid')
    generate_otp(account)  # A stale instance must not overwrite counters saved by other requests.
    with pytest.raises(OTPAttemptLimitExceeded):
        verify_otp(User.objects.get(pk=account.pk), 'invalid')
    account.refresh_from_db()
    assert account.otp_failed_attempts == 5


def test_other_accounts_are_unaffected(account, user_factory):
    User.objects.filter(pk=account.pk).update(
        otp_failed_attempts=5, otp_locked_until=timezone.now() + timedelta(minutes=15)
    )
    other = user_factory(otp_verified=True, otp_base32=pyotp.random_base32())
    validate_otp(other, pyotp.TOTP(other.otp_base32).now())


def test_locked_setup_cannot_enable_otp(user_factory):
    account = user_factory(otp_base32=pyotp.random_base32(), otp_locked_until=timezone.now() + timedelta(minutes=15))
    with pytest.raises(OTPAttemptLimitExceeded):
        verify_otp(account, pyotp.TOTP(account.otp_base32).now())
    account.refresh_from_db()
    assert not account.otp_enabled
    assert not account.otp_verified


def test_http_login_new_tokens_cannot_reset_limit_or_issue_login_cookies(account, api_client):
    query = 'mutation($input: ValidateOTPMutationInput!) { validateOtp(input: $input) { authenticated } }'
    for attempt in range(6):
        otp_token = pyotp.TOTP(account.otp_base32).now() if attempt == 5 else 'invalid'
        response = api_client.post(
            '/api/graphql/',
            data={
                'query': query,
                'variables': {'input': {'otpToken': otp_token, 'otpAuthToken': begin_otp_login(account, 'password')}},
            },
            format='json',
        )
        assert response.json()['data']['validateOtp'] is None
        assert response.json()['errors']
        assert settings.ACCESS_TOKEN_COOKIE not in response.cookies
        assert settings.REFRESH_TOKEN_COOKIE not in response.cookies
    account.refresh_from_db()
    assert account.otp_failed_attempts == 5
    assert response.json()['errors'][0]['message'] == 'Too many incorrect codes. Try again in 15 minutes.'


@pytest.mark.django_db(transaction=True)
def test_concurrent_guesses_share_account_limit(account):
    def attempt(_):
        close_old_connections()
        try:
            validate_otp(User.objects.get(pk=account.pk), 'invalid')
        except (OTPVerificationFailure, OTPAttemptLimitExceeded) as error:
            return type(error)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count(OTPVerificationFailure) == 4
    assert results.count(OTPAttemptLimitExceeded) == 8
    account.refresh_from_db()
    assert account.otp_failed_attempts == 5
