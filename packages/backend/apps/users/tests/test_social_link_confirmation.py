import hashlib
from datetime import timedelta
from unittest.mock import patch

import pyotp
import pytest
from django.conf import settings
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from social_core.exceptions import AuthForbidden
from social_django.models import UserSocialAuth

from apps.users.models import PendingSocialAccountLink
from apps.users.services.social_linking import begin_link, complete_link, LINK_COOKIE
from apps.users.services.otp_login import begin_otp_login
from apps.users.tests.test_social_account_linking import run_social_pipeline
from apps.users.tasks import cleanup_social_link_confirmations
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.django_db


def pending_request(social_backend, account):
    response = begin_link(social_backend, account, 'provider-identity')
    request = RequestFactory().post('/')
    request.COOKIES[LINK_COOKIE] = response.cookies[LINK_COOKIE].value
    return request


def test_password_login_confirms_matching_social_identity(social_backend, user_factory):
    account = user_factory(is_confirmed=True)
    request = pending_request(social_backend, account)
    client = APIClient()
    client.cookies[LINK_COOKIE] = request.COOKIES[LINK_COOKIE]
    response = client.post(
        '/api/graphql/',
        {
            'query': (
                'mutation($input: ObtainTokenMutationInput!) { '
                'tokenAuth(input: $input) { authenticated otpRequired } }'
            ),
            'variables': {'input': {'email': account.email, 'password': account._faker_password}},
        },
        format='json',
    )
    assert response.json()['data']['tokenAuth']['authenticated'], response.json()
    assert UserSocialAuth.objects.get(provider='google-oauth2', uid='provider-identity').user_id == account.pk
    assert response.cookies[LINK_COOKIE]['max-age'] == 0
    assert PendingSocialAccountLink.objects.get(user=account).used_at is not None
    assert run_social_pipeline(social_backend, account.email)['user'].pk == account.pk


def test_password_step_does_not_link_until_otp_succeeds(social_backend, user_factory):
    account = user_factory(
        is_confirmed=True,
        otp_enabled=True,
        otp_verified=True,
        otp_base32=pyotp.random_base32(),
    )
    request = pending_request(social_backend, account)
    client = APIClient()
    client.cookies[LINK_COOKIE] = request.COOKIES[LINK_COOKIE]
    response = client.post(
        '/api/graphql/',
        {
            'query': (
                'mutation($input: ObtainTokenMutationInput!) { '
                'tokenAuth(input: $input) { authenticated otpRequired } }'
            ),
            'variables': {'input': {'email': account.email, 'password': account._faker_password}},
        },
        format='json',
    )
    assert response.json()['data']['tokenAuth']['otpRequired'], response.json()
    assert not UserSocialAuth.objects.exists()
    assert settings.ACCESS_TOKEN_COOKIE not in response.cookies
    otp_response = client.post(
        '/api/graphql/',
        {
            'query': 'mutation($input: ValidateOTPMutationInput!) { validateOtp(input: $input) { authenticated } }',
            'variables': {'input': {'otpToken': pyotp.TOTP(account.otp_base32).now()}},
        },
        format='json',
    )
    assert otp_response.json()['data']['validateOtp']['authenticated'], otp_response.json()
    assert UserSocialAuth.objects.get().user_id == account.pk
    assert otp_response.cookies[LINK_COOKIE]['max-age'] == 0


@pytest.mark.parametrize('change', ['expired', 'password', 'otp', 'inactive', 'unconfirmed', 'used'])
def test_changed_or_expired_confirmation_is_rejected(social_backend, user_factory, change):
    account = user_factory(is_confirmed=True)
    request = pending_request(social_backend, account)
    pending = PendingSocialAccountLink.objects.get(user=account)
    if change == 'expired':
        pending.expires_at = timezone.now() - timedelta(seconds=1)
    elif change == 'used':
        pending.used_at = timezone.now()
    elif change == 'password':
        account.set_password('ChangedPassword!9372')
    elif change == 'otp':
        account.otp_base32 = pyotp.random_base32()
    elif change == 'inactive':
        account.is_active = False
    elif change == 'unconfirmed':
        account.is_confirmed = False
    account.save()
    pending.save()
    with pytest.raises(PermissionDenied):
        complete_link(request, account)
    assert not UserSocialAuth.objects.exists()


def test_other_account_cannot_complete_confirmation(social_backend, user_factory):
    account = user_factory(is_confirmed=True)
    other = user_factory(is_confirmed=True)
    with pytest.raises(PermissionDenied):
        complete_link(pending_request(social_backend, account), other)
    assert not UserSocialAuth.objects.exists()


def test_provider_identity_cannot_be_reassigned(social_backend, user_factory):
    account, other = user_factory(is_confirmed=True), user_factory(is_confirmed=True)
    request = pending_request(social_backend, account)
    association = UserSocialAuth.objects.create(user=other, provider='google-oauth2', uid='provider-identity')
    with pytest.raises(PermissionDenied):
        complete_link(request, account)
    association.refresh_from_db()
    assert association.user_id == other.pk
    assert PendingSocialAccountLink.objects.get(user=account).used_at is None


def test_confirmation_token_is_hashed_and_latest_request_invalidates_old(social_backend, user_factory):
    account = user_factory(is_confirmed=True)
    first = pending_request(social_backend, account)
    assert (
        PendingSocialAccountLink.objects.get().token_hash
        == hashlib.sha256(first.COOKIES[LINK_COOKIE].encode()).hexdigest()
    )
    second = pending_request(social_backend, account)
    assert PendingSocialAccountLink.objects.count() == 1
    with pytest.raises(PermissionDenied):
        complete_link(first, account)
    assert complete_link(second, account)
    with pytest.raises(PermissionDenied):
        complete_link(second, account)


def test_cancellation_clears_cookie_and_confirmation(social_backend, user_factory):
    request = pending_request(social_backend, user_factory(is_confirmed=True))
    client = APIClient()
    client.cookies[LINK_COOKIE] = request.COOKIES[LINK_COOKIE]
    response = client.post('/api/auth/social-link/cancel/', {}, format='json')
    assert response.status_code == 200
    assert response.cookies[LINK_COOKIE]['max-age'] == 0
    assert not PendingSocialAccountLink.objects.exists()


def test_debug_callback_failure_redirects_instead_of_traceback(api_client, settings):
    settings.DEBUG = True
    with patch('apps.users.views.do_complete', side_effect=AuthForbidden('google-oauth2')):
        response = api_client.get('/api/auth/social/complete/google-oauth2/')
    assert response.status_code == 302
    assert response.url.endswith('/en/auth/login?social=failed')
    assert 'localhost:5001' not in response.url


def test_otp_proof_failure_does_not_link(social_backend, user_factory):
    account = user_factory(is_confirmed=True, otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
    request = pending_request(social_backend, account)
    client = APIClient()
    client.cookies[LINK_COOKIE] = request.COOKIES[LINK_COOKIE]
    client.cookies[settings.OTP_AUTH_TOKEN_COOKIE] = begin_otp_login(account, 'password')
    response = client.post(
        '/api/graphql/',
        {
            'query': 'mutation($input: ValidateOTPMutationInput!) { validateOtp(input: $input) { authenticated } }',
            'variables': {'input': {'otpToken': 'invalid'}},
        },
        format='json',
    )
    assert 'errors' in response.json()
    assert not UserSocialAuth.objects.exists()


def test_session_failure_does_not_complete_link(social_backend, user_factory):
    account = user_factory(is_confirmed=True)
    request = pending_request(social_backend, account)
    client = APIClient()
    client.cookies[LINK_COOKIE] = request.COOKIES[LINK_COOKIE]
    with (
        patch('apps.users.schema.SessionService.create_session', side_effect=RuntimeError('storage unavailable')),
        patch('apps.users.services.social_linking.notifications.SocialAccountLinkedEmail.send') as mock_send,
    ):
        response = client.post(
            '/api/graphql/',
            {
                'query': 'mutation($input: ObtainTokenMutationInput!) { tokenAuth(input: $input) { authenticated } }',
                'variables': {'input': {'email': account.email, 'password': account._faker_password}},
            },
            format='json',
        )
    assert 'errors' in response.json()
    assert settings.ACCESS_TOKEN_COOKIE not in response.cookies
    assert not UserSocialAuth.objects.exists()
    assert PendingSocialAccountLink.objects.get(user=account).used_at is None
    # The whole transaction rolled back before complete_link ever ran, so the
    # "Google was linked" notification must never have been queued for it.
    mock_send.assert_not_called()


def test_link_succeeds_even_if_notification_send_fails(
    social_backend, user_factory, django_capture_on_commit_callbacks
):
    account = user_factory(is_confirmed=True)
    request = pending_request(social_backend, account)
    with (
        patch(
            'apps.users.services.social_linking.notifications.SocialAccountLinkedEmail.send',
            side_effect=RuntimeError('broker unreachable'),
        ) as mock_send,
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert complete_link(request, account)
    assert UserSocialAuth.objects.get(user=account).provider == 'google-oauth2'
    mock_send.assert_called_once()


def test_full_access_token_cannot_satisfy_otp_step_during_linking(social_backend, user_factory):
    # Unlike the previous self-signed-JWT pending-login proof, an ordinary,
    # otherwise-valid access token cannot hash-match any PendingOTPLogin row -
    # only begin_otp_login() (itself only reachable after a real password/OAuth
    # login) can ever create one.
    account = user_factory(is_confirmed=True, otp_enabled=True, otp_verified=True, otp_base32=pyotp.random_base32())
    request = pending_request(social_backend, account)
    client = APIClient()
    client.cookies[LINK_COOKIE] = request.COOKIES[LINK_COOKIE]
    client.cookies[settings.OTP_AUTH_TOKEN_COOKIE] = str(RefreshToken.for_user(account).access_token)
    response = client.post(
        '/api/graphql/',
        {
            'query': 'mutation($input: ValidateOTPMutationInput!) { validateOtp(input: $input) { authenticated } }',
            'variables': {'input': {'otpToken': pyotp.TOTP(account.otp_base32).now()}},
        },
        format='json',
    )
    assert 'errors' in response.json()
    assert not UserSocialAuth.objects.exists()


def test_cleanup_removes_expired_confirmations_only(social_backend, user_factory):
    expired_account = user_factory(is_confirmed=True)
    pending_request(social_backend, expired_account)
    PendingSocialAccountLink.objects.filter(user=expired_account).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    live_account = user_factory(is_confirmed=True)
    pending_request(social_backend, live_account)
    assert cleanup_social_link_confirmations() == 1
    assert PendingSocialAccountLink.objects.get().user_id == live_account.pk
