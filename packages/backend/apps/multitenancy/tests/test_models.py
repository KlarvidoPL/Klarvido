import pytest
from unittest.mock import patch
from django.utils.text import slugify
from django.db import IntegrityError

from ..constants import TenantUserRole
from ..models import (
    Permission,
    Tenant,
    get_user_permissions_for_tenant,
    get_visible_tenants_for_user,
    has_real_tenant_membership,
    has_tenant_access,
    is_cross_tenant_superuser_access,
    is_superuser_bypass_eligible,
)

pytestmark = pytest.mark.django_db


class TestTenant:
    def test_save_unique_slug_generation(self, user):
        with patch("apps.multitenancy.models.slugify", side_effect=slugify) as mock_slugify:
            tenant = Tenant(name="Test Tenant", creator=user)
            tenant.save()

            mock_slugify.assert_called_once_with("Test Tenant")
            assert tenant.slug == "test-tenant"

    def test_save_unique_slug_with_collision(self, user, tenant_factory):
        tenant_factory(name="Test Tenant", creator=user)
        with patch("apps.multitenancy.models.slugify", side_effect=slugify) as mock_slugify:
            tenant = Tenant(name="Test Tenant", creator=user)
            tenant.save()

            mock_slugify.assert_called_with("Test Tenant")
            assert mock_slugify.call_count == 2
            assert tenant.slug == "test-tenant-1"

    def test_save_unique_slug_raises_different_integrity_error(self):
        tenant = Tenant(name="Test Tenant")
        try:
            tenant.save()
        except IntegrityError as e:
            assert "not-null constraint" in str(e).lower()


class TestTenantMembership:
    def test_unique_non_null_user_and_tenant(self, tenant, user, tenant_membership_factory):
        tenant_membership_factory(user=user, tenant=tenant)
        try:
            tenant_membership_factory(user=user, tenant=tenant)
        except IntegrityError:
            pass
        else:
            assert False, "IntegrityError not raised"

    def test_unique_non_null_user_and_invitee_email_address(self, tenant, tenant_membership_factory):
        tenant_membership_factory(invitee_email_address="user@example.com", tenant=tenant)
        try:
            tenant_membership_factory(invitee_email_address="user@example.com", tenant=tenant)
        except IntegrityError:
            pass
        else:
            assert False, "IntegrityError not raised"


class TestSuperuserBypassHelpers:
    """Tests for the centralized superuser cross-tenant access bypass helpers."""

    def test_is_superuser_bypass_eligible_true_for_superuser(self, user_factory):
        superuser = user_factory(is_superuser=True)
        assert is_superuser_bypass_eligible(superuser) is True

    def test_is_superuser_bypass_eligible_false_for_regular_user(self, user):
        assert is_superuser_bypass_eligible(user) is False

    def test_is_superuser_bypass_eligible_false_for_none(self):
        assert is_superuser_bypass_eligible(None) is False

    def test_has_tenant_access_true_for_superuser_without_membership(self, tenant, user_factory):
        superuser = user_factory(is_superuser=True)
        assert has_real_tenant_membership(superuser, tenant) is False
        assert has_tenant_access(superuser, tenant) is True

    def test_has_tenant_access_false_for_regular_user_without_membership(self, tenant, user):
        assert has_tenant_access(user, tenant) is False

    def test_has_tenant_access_true_for_regular_user_with_membership(self, tenant, user, tenant_membership_factory):
        tenant_membership_factory(user=user, tenant=tenant, is_accepted=True)
        assert has_tenant_access(user, tenant) is True

    def test_is_cross_tenant_superuser_access_true_without_membership(self, tenant, user_factory):
        superuser = user_factory(is_superuser=True)
        assert is_cross_tenant_superuser_access(superuser, tenant) is True

    def test_is_cross_tenant_superuser_access_false_when_real_member(
        self, tenant, user_factory, tenant_membership_factory
    ):
        superuser = user_factory(is_superuser=True)
        tenant_membership_factory(user=superuser, tenant=tenant, is_accepted=True)
        assert is_cross_tenant_superuser_access(superuser, tenant) is False

    def test_is_cross_tenant_superuser_access_false_for_regular_user(self, tenant, user):
        assert is_cross_tenant_superuser_access(user, tenant) is False

    def test_get_visible_tenants_for_user_superuser_returns_all_tenants(self, tenant_factory, user_factory):
        tenants = tenant_factory.create_batch(3)
        superuser = user_factory(is_superuser=True)
        visible = get_visible_tenants_for_user(superuser)
        assert set(visible) >= set(tenants)

    def test_get_visible_tenants_for_user_regular_user_returns_only_own_tenants(
        self, tenant_factory, user, tenant_membership_factory
    ):
        unrelated_tenants = tenant_factory.create_batch(3)
        own_tenant = tenant_factory()
        tenant_membership_factory(user=user, tenant=own_tenant, is_accepted=True)
        visible = set(get_visible_tenants_for_user(user))
        assert own_tenant in visible
        assert visible.isdisjoint(unrelated_tenants)

    def test_get_visible_tenants_for_user_unauthenticated_returns_none(self):
        assert list(get_visible_tenants_for_user(None)) == []


class TestGetUserPermissionsForTenantSuperuserBypass:
    def test_superuser_without_membership_gets_all_permissions(self, tenant, user_factory):
        superuser = user_factory(is_superuser=True)
        all_permission_codes = set(Permission.objects.values_list("code", flat=True))
        assert all_permission_codes, "expected at least one Permission row to exist from app migrations"

        permissions = get_user_permissions_for_tenant(superuser, tenant)

        assert permissions == all_permission_codes

    def test_superuser_with_real_membership_uses_real_role_permissions(
        self, tenant, user_factory, tenant_membership_factory
    ):
        superuser = user_factory(is_superuser=True)
        tenant_membership_factory(user=superuser, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True)

        all_permission_codes = set(Permission.objects.values_list("code", flat=True))
        assert all_permission_codes, "expected at least one Permission row to exist from app migrations"
        permissions = get_user_permissions_for_tenant(superuser, tenant)

        # A real (non-owner) membership's permission set must not be silently
        # upgraded to "all permissions" just because the user is also a superuser.
        assert permissions != all_permission_codes

    def test_regular_user_without_membership_gets_no_permissions(self, tenant, user):
        permissions = get_user_permissions_for_tenant(user, tenant)
        assert permissions == set()
