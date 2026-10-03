"""
KSeF permissions are only offered to Polish organizations: they are hidden from the permission list for other
countries, not seeded into their roles, and rejected when a role for them is saved.
"""

import pytest
from django.conf import settings
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.multitenancy.constants import CompanyCountry, SystemRoleType, TenantType, TenantUserRole
from apps.multitenancy.models import OrganizationRole, OrganizationRolePermission, Permission
from apps.multitenancy.permissions import create_system_roles_for_tenant

pytestmark = pytest.mark.django_db

KSEF_CODES = {"security.ksef.view", "security.ksef.manage"}

ALL_PERMISSIONS = """
    query AllPermissions($tenantId: ID) { allPermissions(tenantId: $tenantId) { edges { node { code } } } }
"""
CREATE_ROLE = """
    mutation CreateRole($tenantId: ID!, $name: String!, $permissionIds: [ID]!) {
      createOrganizationRole(tenantId: $tenantId, name: $name, permissionIds: $permissionIds) { ok }
    }
"""


def post(user, query, variables):
    client = APIClient()
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    return client.post("/api/graphql/", {"query": query, "variables": variables}, format="json").json()


def codes_in(response):
    return {edge["node"]["code"] for edge in response["data"]["allPermissions"]["edges"]}


def make_tenant(tenant_factory, country):
    return tenant_factory(country=country, type=TenantType.ORGANIZATION, nip="5252344078")


def test_polish_organization_sees_ksef_permissions(user_factory, tenant_factory, tenant_membership_factory):
    tenant = make_tenant(tenant_factory, CompanyCountry.POLAND)
    user = user_factory()
    tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)

    response = post(user, ALL_PERMISSIONS, {"tenantId": to_global_id("TenantType", str(tenant.pk))})

    assert KSEF_CODES <= codes_in(response)


def test_other_countries_do_not_see_ksef_permissions(user_factory, tenant_factory, tenant_membership_factory):
    tenant = make_tenant(tenant_factory, "DE")
    user = user_factory()
    tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)

    response = post(user, ALL_PERMISSIONS, {"tenantId": to_global_id("TenantType", str(tenant.pk))})

    assert not (KSEF_CODES & codes_in(response))
    assert "org.settings.view" in codes_in(response)


def test_unfiltered_list_still_includes_ksef_permissions(user_factory):
    user = user_factory()

    response = post(user, ALL_PERMISSIONS, {})

    assert KSEF_CODES <= codes_in(response)


def test_other_country_system_roles_never_get_ksef_permissions(tenant_factory):
    tenant = make_tenant(tenant_factory, "DE")

    create_system_roles_for_tenant(tenant)

    granted = OrganizationRolePermission.objects.filter(role__tenant=tenant, permission__code__in=KSEF_CODES)
    assert not granted.exists()
    assert OrganizationRole.objects.filter(tenant=tenant, system_role_type=SystemRoleType.OWNER).exists()


def test_polish_admin_role_gets_view_but_not_manage(tenant_factory):
    tenant = make_tenant(tenant_factory, CompanyCountry.POLAND)

    create_system_roles_for_tenant(tenant)

    admin_codes = set(
        OrganizationRolePermission.objects.filter(
            role__tenant=tenant, role__system_role_type=SystemRoleType.ADMIN
        ).values_list("permission__code", flat=True)
    )
    assert "security.ksef.view" in admin_codes
    assert "security.ksef.manage" not in admin_codes


def test_saving_a_role_with_ksef_permission_is_rejected_outside_poland(
    user_factory, tenant_factory, tenant_membership_factory
):
    tenant = make_tenant(tenant_factory, "DE")
    user = user_factory()
    tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
    ksef_permission = Permission.objects.get(code="security.ksef.view")

    response = post(
        user,
        CREATE_ROLE,
        {
            "tenantId": to_global_id("TenantType", str(tenant.pk)),
            "name": "Invoice reader",
            "permissionIds": [to_global_id("PermissionType", str(ksef_permission.pk))],
        },
    )

    assert "not available for this organization" in str(response["errors"])
    assert not OrganizationRole.objects.filter(tenant=tenant, name="Invoice reader").exists()
