"""
Regression tests for apps.sso.enforcement.

should_enforce_sso_for_session() replaced an older, narrower check
(is_password_session(), True only for auth_method == 'password') that
exempted any *non*-password session from SSO enforcement. That was fine back
when 'password' and 'sso' were the only two auth methods in use, but adding a
distinct 'oauth' auth_method (see apps/users/views.py::complete()) would have
silently turned this into a real bypass: an OAuth-authenticated session is
just as capable of sidestepping a tenant's configured SSO connection as a
password login, so it must be enforced against exactly the same way - only a
genuine 'sso' session (issued via the tenant's own SAML/OIDC connection,
apps/sso/views.py) is exempt.
"""

from types import SimpleNamespace

import pytest

from apps.multitenancy import constants as multitenancy_constants
from apps.sso.enforcement import (
    check_tenant_sso_enforcement,
    filter_tenants_for_password_session,
    should_enforce_sso_for_session,
)

pytestmark = pytest.mark.django_db


def _request(user, auth_method=None):
    auth = {"auth_method": auth_method} if auth_method else None
    return SimpleNamespace(user=user, auth=auth, META={})


class TestShouldEnforceSsoForSession:
    def test_enforces_for_password_session(self, user):
        assert should_enforce_sso_for_session(_request(user, "password")) is True

    def test_enforces_for_oauth_session(self, user):
        assert should_enforce_sso_for_session(_request(user, "oauth")) is True

    def test_enforces_when_auth_method_claim_is_missing(self, user):
        """A missing/legacy claim defaults to 'password' (see
        get_auth_method_from_token) and must stay enforced, not exempted."""
        assert should_enforce_sso_for_session(_request(user)) is True

    def test_does_not_enforce_for_genuine_sso_session(self, user):
        assert should_enforce_sso_for_session(_request(user, "sso")) is False


class TestFilterTenantsForPasswordSession:
    def test_excludes_sso_enforced_tenant_for_oauth_session(
        self, user, tenant_factory, tenant_membership_factory, active_sso_connection
    ):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )
        other_tenant = tenant_factory()
        tenant_membership_factory(user=user, tenant=other_tenant, role=multitenancy_constants.TenantUserRole.MEMBER)

        from apps.multitenancy.models import Tenant

        queryset = Tenant.objects.filter(pk__in=[active_sso_connection.tenant_id, other_tenant.pk])
        result = filter_tenants_for_password_session(_request(user, "oauth"), queryset)

        assert list(result.values_list("pk", flat=True)) == [other_tenant.pk]

    def test_does_not_exclude_sso_enforced_tenant_for_sso_session(
        self, user, tenant_membership_factory, active_sso_connection
    ):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        from apps.multitenancy.models import Tenant

        queryset = Tenant.objects.filter(pk=active_sso_connection.tenant_id)
        result = filter_tenants_for_password_session(_request(user, "sso"), queryset)

        assert list(result.values_list("pk", flat=True)) == [active_sso_connection.tenant_id]


class TestCheckTenantSsoEnforcement:
    def test_blocks_oauth_session_without_break_glass_permission(
        self, user, tenant_membership_factory, active_sso_connection
    ):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        result = check_tenant_sso_enforcement(_request(user, "oauth"), active_sso_connection.tenant, user)

        assert result == "sso_login_required"

    def test_allows_sso_session(self, user, tenant_membership_factory, active_sso_connection):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        result = check_tenant_sso_enforcement(_request(user, "sso"), active_sso_connection.tenant, user)

        assert result is None
