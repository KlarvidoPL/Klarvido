import pytest
from django.test import Client
from django.urls import reverse

from apps.multitenancy.constants import TenantUserRole
from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(user_factory, settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    superuser = user_factory(is_superuser=True, is_confirmed=True)
    client = Client()
    client.force_login(superuser)
    return client, superuser


def test_action_shows_confirmation_page_without_executing(admin_client, user_factory):
    client, _ = admin_client
    account = user_factory(is_confirmed=False)

    response = client.post(
        reverse("admin:users_user_changelist"),
        {"action": "reclaim_unconfirmed_account", "_selected_action": [str(account.pk)]},
    )

    assert response.status_code == 200
    account.refresh_from_db()
    assert account.has_usable_password()
    assert not SSOAuditLog.objects.filter(event_type=SSOAuditEventType.ACCOUNT_RECLAIMED).exists()


def test_action_flags_organization_memberships_before_reclaiming(admin_client, user_factory, tenant_membership_factory):
    client, _ = admin_client
    account = user_factory(is_confirmed=False)
    membership = tenant_membership_factory(user=account, role=TenantUserRole.OWNER, is_accepted=True)

    response = client.post(
        reverse("admin:users_user_changelist"),
        {"action": "reclaim_unconfirmed_account", "_selected_action": [str(account.pk)]},
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert membership.tenant.name in content
    assert "Owner" in content


def test_action_shows_no_memberships_when_account_has_none(admin_client, user_factory):
    client, _ = admin_client
    account = user_factory(is_confirmed=False)

    response = client.post(
        reverse("admin:users_user_changelist"),
        {"action": "reclaim_unconfirmed_account", "_selected_action": [str(account.pk)]},
    )

    assert response.status_code == 200
    assert "No organization memberships" in response.content.decode()


def test_action_confirmed_post_reclaims_account(admin_client, user_factory):
    client, superuser = admin_client
    account = user_factory(is_confirmed=False)

    response = client.post(
        reverse("admin:users_user_changelist"),
        {
            "action": "reclaim_unconfirmed_account",
            "_selected_action": [str(account.pk)],
            "post": "yes",
        },
    )

    assert response.status_code == 302
    account.refresh_from_db()
    assert not account.has_usable_password()
    assert SSOAuditLog.objects.filter(
        event_type=SSOAuditEventType.ACCOUNT_RECLAIMED, user=account, metadata__actor_id=str(superuser.pk)
    ).exists()


def test_action_refuses_confirmed_accounts(admin_client, user_factory):
    client, _ = admin_client
    account = user_factory(is_confirmed=True)
    original_password = account.password

    response = client.post(
        reverse("admin:users_user_changelist"),
        {
            "action": "reclaim_unconfirmed_account",
            "_selected_action": [str(account.pk)],
            "post": "yes",
        },
    )

    assert response.status_code == 200
    account.refresh_from_db()
    assert account.password == original_password
