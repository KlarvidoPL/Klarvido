"""
KSeF token access, checked end to end through the real request path (JWT cookie -> tenant middleware -> permission
classes): viewing the connection needs security.ksef.view, changing it needs security.ksef.view and security.ksef.manage.
"""

import base64
import os
from unittest.mock import patch

import pytest
from django.conf import settings
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.ksef import services
from apps.ksef.client import TokenCheck
from apps.ksef.constants import KsefCredentialStatus
from apps.ksef.models import KsefCredential
from apps.multitenancy.constants import TenantType, TenantUserRole
from apps.multitenancy.models import ActionLog, OrganizationRole, Permission, TenantMembershipRole

pytestmark = pytest.mark.django_db

QUERY = """
    query Credential($tenantId: ID!) { ksefCredential(tenantId: $tenantId) { status tokenHint } }
"""
SET = """
    mutation Set($tenantId: ID!, $token: String!) { setKsefToken(tenantId: $tenantId, token: $token) { ok errorCode } }
"""
TEST = """
    mutation Test($tenantId: ID!) { testKsefToken(tenantId: $tenantId) { ok errorCode } }
"""
DELETE = """
    mutation Delete($tenantId: ID!) { deleteKsefToken(tenantId: $tenantId) { ok errorCode } }
"""
CHANGE_CASES = [
    ("set", SET, lambda tenant_id: {"tenantId": tenant_id, "token": "token-1234"}),
    ("test", TEST, lambda tenant_id: {"tenantId": tenant_id}),
    ("delete", DELETE, lambda tenant_id: {"tenantId": tenant_id}),
]


@pytest.fixture(autouse=True)
def encryption_key(settings):
    settings.KSEF_ENCRYPTION_KEYS = base64.b64encode(os.urandom(32)).decode()


@pytest.fixture
def polish_tenant(tenant_factory):
    return tenant_factory(nip="5252344078", type=TenantType.ORGANIZATION)


@pytest.fixture
def stored_token(polish_tenant):
    KsefCredential.objects.create(
        tenant=polish_tenant,
        encrypted_token=b"not-really-ciphertext",
        token_hint="1234",
        status=KsefCredentialStatus.VALID,
    )
    return polish_tenant


def tenant_gid(tenant):
    return to_global_id("TenantType", str(tenant.pk))


def post(user, query, variables):
    client = APIClient()
    client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
    return client.post("/api/graphql/", {"query": query, "variables": variables}, format="json").json()


def assert_denied(response):
    assert response["errors"][0]["message"] == "permission_denied", response


def member_with_permissions(tenant, user, membership_factory_fn, codes):
    """A custom organization role with exactly the given permission codes, assigned to the user."""
    membership = membership_factory_fn(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
    TenantMembershipRole.objects.filter(membership=membership).delete()
    role = OrganizationRole.objects.create(tenant=tenant, name="KSeF test role", description="")
    role.permissions.add(*Permission.objects.filter(code__in=codes))
    TenantMembershipRole.objects.create(membership=membership, role=role, assigned_by=user)
    return user


@pytest.fixture
def user_with_codes(user_factory, tenant_membership_factory, polish_tenant):
    def make(codes):
        user = user_factory()
        return member_with_permissions(polish_tenant, user, tenant_membership_factory, codes)

    return make


@pytest.mark.parametrize(
    "codes, can_view",
    [
        ([], False),
        (["security.ksef.manage"], False),
        (["security.ksef.view"], True),
        (["security.ksef.view", "security.ksef.manage"], True),
    ],
)
def test_viewing_the_connection_requires_ksef_view(user_with_codes, stored_token, codes, can_view):
    user = user_with_codes(codes)

    response = post(user, QUERY, {"tenantId": tenant_gid(stored_token)})

    if can_view:
        assert response["data"]["ksefCredential"]["status"] == KsefCredentialStatus.VALID
    else:
        assert_denied(response)


@pytest.mark.parametrize("name, query, variables", CHANGE_CASES)
@pytest.mark.parametrize("codes", [[], ["security.ksef.view"], ["security.ksef.manage"]])
def test_changing_the_token_needs_view_and_manage(user_with_codes, stored_token, name, query, variables, codes):
    user = user_with_codes(codes)
    before = KsefCredential.objects.get(tenant=stored_token).encrypted_token

    response = post(user, query, variables(tenant_gid(stored_token)))

    assert_denied(response)
    assert KsefCredential.objects.get(tenant=stored_token).encrypted_token == before


@pytest.mark.parametrize("name, query, variables", CHANGE_CASES)
def test_organization_admin_cannot_change_the_token(
    tenant_membership_factory, polish_tenant, user_factory, stored_token, name, query, variables
):
    admin = user_factory()
    tenant_membership_factory(tenant=polish_tenant, user=admin, role=TenantUserRole.ADMIN)

    assert_denied(post(admin, query, variables(tenant_gid(stored_token))))
    assert (
        post(admin, QUERY, {"tenantId": tenant_gid(stored_token)})["data"]["ksefCredential"]["status"]
        == KsefCredentialStatus.VALID
    )


def test_owner_can_change_the_token(tenant_membership_factory, polish_tenant, user_factory, stored_token):
    owner = user_factory()
    tenant_membership_factory(tenant=polish_tenant, user=owner, role=TenantUserRole.OWNER)

    with patch.object(services, "verify_token", return_value=TokenCheck(status=KsefCredentialStatus.VALID)):
        response = post(owner, SET, {"tenantId": tenant_gid(stored_token), "token": "new-token-5678"})

    assert response["data"]["setKsefToken"]["ok"] is True
    assert KsefCredential.objects.get(tenant=stored_token).token_hint == "5678"


def test_view_and_manage_can_replace_the_token(user_with_codes, stored_token):
    user = user_with_codes(["security.ksef.view", "security.ksef.manage"])

    with patch.object(services, "verify_token", return_value=TokenCheck(status=KsefCredentialStatus.VALID)):
        response = post(user, SET, {"tenantId": tenant_gid(stored_token), "token": "new-token-5678"})

    assert response["data"]["setKsefToken"]["ok"] is True
    assert KsefCredential.objects.get(tenant=stored_token).token_hint == "5678"


def test_non_member_is_denied_even_with_a_valid_tenant_id(user_factory, stored_token):
    outsider = user_factory()

    assert_denied(post(outsider, QUERY, {"tenantId": tenant_gid(stored_token)}))
    assert_denied(post(outsider, DELETE, {"tenantId": tenant_gid(stored_token)}))
    assert KsefCredential.objects.filter(tenant=stored_token).exists()


def test_denied_change_writes_no_activity_log_entry(user_with_codes, stored_token):
    user = user_with_codes(["security.ksef.view"])

    assert_denied(post(user, DELETE, {"tenantId": tenant_gid(stored_token)}))

    assert ActionLog.objects.filter(entity_type="ksef_credential").count() == 0


def test_new_tenant_admin_role_excludes_manage(tenant_factory):
    """New tenants: the organization Admin role gets security.ksef.view but not security.ksef.manage."""
    from apps.multitenancy.constants import SystemRoleType
    from apps.multitenancy.permissions import create_system_roles_for_tenant

    tenant = tenant_factory(nip="5252344078")
    create_system_roles_for_tenant(tenant)
    admin_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.ADMIN)
    codes = set(admin_role.permissions.values_list("code", flat=True))

    assert "security.ksef.view" in codes
    assert "security.ksef.manage" not in codes
