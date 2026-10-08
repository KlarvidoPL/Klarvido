from unittest.mock import Mock

import pytest
from rest_framework_simplejwt.tokens import RefreshToken
from social_core.exceptions import AuthForbidden
from social_django.models import UserSocialAuth

from apps.users.models import User
from apps.users.models import PendingSocialAccountLink
from apps.users.pipeline import create_social_user
from apps.users.services.social_linking import LINK_COOKIE
from apps.users.services.social_link_review import historical_link_candidates
from config import settings

pytestmark = pytest.mark.django_db


def run_social_pipeline(backend, email, uid='provider-identity', response=None):
    # Start at social_user: the provider's signed callback has already yielded
    # these details. Run the configured storage/linking steps without network I/O.
    # Google's userinfo response always carries email_verified; default to the
    # verified happy path so tests not specifically about that check don't need
    # to restate it, and let callers override to exercise the unverified case.
    return backend.run_pipeline(
        settings.SOCIAL_AUTH_PIPELINE,
        pipeline_index=2,
        details={'email': email, 'first_name': 'Owner'},
        uid=uid,
        response={'email_verified': True} if response is None else response,
    )


@pytest.mark.parametrize('confirmed', [False, True])
def test_matching_email_does_not_link_password_account(social_backend, user_factory, confirmed):
    account = user_factory(email='owner@example.com', is_confirmed=confirmed)
    original_password = account.password
    response = run_social_pipeline(social_backend, 'OWNER@example.com')
    assert response.status_code == 302
    expected_code = 'link_required' if confirmed else 'unconfirmed_account'
    assert response.url.endswith(f'social={expected_code}')
    account.refresh_from_db()
    assert account.is_confirmed == confirmed
    assert account.password == original_password
    assert not UserSocialAuth.objects.filter(user=account).exists()
    assert User.objects.filter(email__iexact=account.email).count() == 1
    assert PendingSocialAccountLink.objects.filter(user=account).exists() == confirmed
    if confirmed:
        assert response.cookies[LINK_COOKIE]['httponly']
        assert response.cookies[LINK_COOKIE]['max-age'] == 300


def test_preregistered_mfa_and_session_do_not_become_social_owners(social_backend, user_factory):
    account = user_factory(is_confirmed=False, otp_enabled=True, otp_verified=True, otp_base32='UNTRUSTEDSEED')
    token = RefreshToken.for_user(account)
    response = run_social_pipeline(social_backend, account.email)
    assert response.status_code == 302
    assert response.url.endswith('social=unconfirmed_account')
    account.refresh_from_db()
    assert not account.is_confirmed
    assert account.otp_base32 == 'UNTRUSTEDSEED'
    assert not UserSocialAuth.objects.exists()
    # No reclaim happened either: nothing here is a confirmed takeover, just a denial.
    assert account.has_usable_password()
    # The denied callback cannot publish any session or pending OTP credentials.
    assert social_backend.strategy.refresh_token is None
    assert social_backend.strategy.otp_auth_token is None
    assert social_backend.strategy.session_id is None
    assert token['user_id'] == str(account.pk)


def test_inactive_account_is_rejected_generically(social_backend, user_factory):
    account = user_factory(is_confirmed=True, is_active=False)
    response = run_social_pipeline(social_backend, account.email)
    assert response.status_code == 302
    assert response.url.endswith('social=failed')
    assert not PendingSocialAccountLink.objects.filter(user=account).exists()


@pytest.mark.parametrize('response', [{}, {'email_verified': False}, {'email_verified': 'true'}])
def test_unverified_provider_email_is_rejected(social_backend, response):
    before = set(User.objects.values_list('pk', flat=True))
    with pytest.raises(AuthForbidden):
        run_social_pipeline(social_backend, 'new-owner@example.com', response=response)
    assert set(User.objects.values_list('pk', flat=True)) == before


def test_unverified_provider_email_does_not_link_existing_account(social_backend, user_factory):
    account = user_factory(email='owner@example.com', is_confirmed=True)
    with pytest.raises(AuthForbidden):
        run_social_pipeline(social_backend, account.email, response={'email_verified': False})
    assert not PendingSocialAccountLink.objects.filter(user=account).exists()
    assert not UserSocialAuth.objects.filter(user=account).exists()


def test_new_social_signup_creates_passwordless_account(social_backend):
    result = run_social_pipeline(social_backend, 'new-owner@example.com')
    account = result['user']
    assert result['is_new']
    assert not account.has_usable_password()
    assert account.is_confirmed
    assert account.profile.first_name == 'Owner'
    assert UserSocialAuth.objects.get(user=account).uid == 'provider-identity'


def test_existing_provider_identity_continues_to_log_in(social_backend, user_factory):
    account = user_factory(is_confirmed=True)
    account.set_unusable_password()
    account.save()
    association = UserSocialAuth.objects.create(user=account, provider=social_backend.name, uid='provider-identity')
    result = run_social_pipeline(social_backend, account.email)
    assert result['user'].pk == account.pk
    assert not result['is_new']
    assert result['social'].pk == association.pk
    # No duplicate account was created for this email (regardless of other
    # accounts - e.g. a seeded admin - already present in this database).
    assert User.objects.filter(email__iexact=account.email).count() == 1


def test_email_change_does_not_merge_provider_identity_into_another_account(social_backend, user_factory):
    account = user_factory(is_confirmed=True)
    other = user_factory(is_confirmed=True)
    UserSocialAuth.objects.create(user=account, provider=social_backend.name, uid='provider-identity')
    result = run_social_pipeline(social_backend, other.email)
    assert result['user'].pk == account.pk
    assert not UserSocialAuth.objects.filter(user=other).exists()


def test_ambient_account_without_provider_association_is_rejected(social_backend, user):
    with pytest.raises(AuthForbidden):
        create_social_user(social_backend, {'email': user.email}, user=user)


def test_foreign_provider_association_is_rejected(social_backend, user_factory):
    account, other = user_factory(), user_factory()
    association = UserSocialAuth.objects.create(user=other, provider=social_backend.name, uid='other-identity')
    with pytest.raises(AuthForbidden):
        create_social_user(social_backend, {'email': account.email}, user=account, social=association)


def test_collision_cannot_use_legacy_storage_get_or_create(social_backend, user_factory, mocker):
    # A matching account appearing before insertion must be refused by the real
    # unique constraint. The old storage fallback must never be called.
    original_create = User.objects.create_user

    def concurrent_signup(**kwargs):
        user_factory(email=kwargs['email'])
        return original_create(**kwargs)

    mocker.patch.object(User.objects, 'create_user', side_effect=concurrent_signup)
    fallback = mocker.patch.object(social_backend.strategy, 'create_user', return_value=Mock())
    with pytest.raises(AuthForbidden):
        create_social_user(social_backend, {'email': 'collision@example.com'}, response={'email_verified': True})
    fallback.assert_not_called()
    # The insertion savepoint also rolls back the simulated concurrent fixture;
    # a real separately committed account would remain, but never be returned.
    assert not UserSocialAuth.objects.exists()


def test_provider_without_email_is_rejected(social_backend):
    before = set(User.objects.values_list('pk', flat=True))
    with pytest.raises(AuthForbidden):
        create_social_user(social_backend, {}, response={'email_verified': True})
    assert set(User.objects.values_list('pk', flat=True)) == before


def test_pipeline_has_no_implicit_email_association_or_legacy_creation():
    assert 'social_core.pipeline.social_auth.associate_by_email' not in settings.SOCIAL_AUTH_PIPELINE
    assert 'social_core.pipeline.user.create_user' not in settings.SOCIAL_AUTH_PIPELINE
    assert 'apps.users.pipeline.create_social_user' in settings.SOCIAL_AUTH_PIPELINE



def test_new_verified_provider_signup_has_recorded_ownership_proof(social_backend):
    result = run_social_pipeline(social_backend, 'new-verified-owner@example.com')
    assert result['user'].is_confirmed
    assert list(historical_link_candidates()) == []
