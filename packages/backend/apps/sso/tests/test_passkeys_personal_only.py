"""
Passkeys are personal: each user manages only their own passkeys from their Profile.

These tests make sure the organization-level passkey management stays removed and that
registering a passkey notifies only the user who registered it.
"""

from unittest import mock

import pytest
from django.contrib.admin.sites import site
from django.contrib.auth.models import Permission
from django.test import RequestFactory

from apps.multitenancy.constants import TenantUserRole
from apps.multitenancy.permissions import get_all_permissions
from apps.multitenancy.tests.factories import TenantFactory, TenantMembershipFactory
from apps.sso.admin import UserPasskeyAdmin
from apps.sso.models import UserPasskey
from apps.sso.schema import TenantOwnerMutation, TenantSSOQuery
from apps.users.tests.factories import UserFactory

from . import factories


pytestmark = pytest.mark.django_db


class TestOrganizationPasskeyManagementRemoved:
    """Organization admins have no way to list or remove members' passkeys."""

    def test_tenant_passkeys_query_is_not_exposed(self):
        assert 'tenant_passkeys' not in TenantSSOQuery._meta.fields

    def test_delete_tenant_passkey_mutation_is_not_exposed(self):
        assert 'delete_tenant_passkey' not in TenantOwnerMutation._meta.fields

    def test_manage_passkeys_permission_is_removed(self):
        codes = [perm.code for perm in get_all_permissions()]

        assert 'security.passkeys.manage' not in codes


class TestPasskeyRegistrationNotifications:
    """Registering a passkey notifies only the user who registered it, never tenant owners or admins."""

    def test_only_the_passkey_owner_is_notified(self):
        tenant = TenantFactory()
        org_owner = TenantMembershipFactory(tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True).user
        member = TenantMembershipFactory(tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True).user

        with mock.patch('apps.notifications.sender.send_notification') as send_notification:
            factories.UserPasskeyFactory(user=member)

        send_notification.assert_called_once()
        notified_user = send_notification.call_args.kwargs['user']
        assert notified_user == member
        assert notified_user != org_owner


class TestUserPasskeyAdminSuperuserOnly:
    """Passkeys are personal credentials: only superusers may view or change them in Django admin."""

    @pytest.fixture
    def passkey_admin(self):
        return UserPasskeyAdmin(UserPasskey, site)

    @pytest.fixture
    def request_for(self):
        def _build(user):
            request = RequestFactory().get('/admin/')
            request.user = user
            return request

        return _build

    def test_non_superuser_is_denied_even_with_model_permissions(self, passkey_admin, request_for):
        user = UserFactory(is_superuser=False)
        user.user_permissions.add(
            *Permission.objects.filter(content_type__app_label='sso', codename__endswith='userpasskey')
        )
        request = request_for(user)

        assert passkey_admin.has_module_permission(request) is False
        assert passkey_admin.has_view_permission(request) is False
        assert passkey_admin.has_add_permission(request) is False
        assert passkey_admin.has_change_permission(request) is False
        assert passkey_admin.has_delete_permission(request) is False

    def test_superuser_has_access(self, passkey_admin, request_for):
        superuser = UserFactory(is_superuser=True)
        request = request_for(superuser)

        assert passkey_admin.has_module_permission(request) is True
        assert passkey_admin.has_view_permission(request) is True
        assert passkey_admin.has_change_permission(request) is True
        assert passkey_admin.has_delete_permission(request) is True
