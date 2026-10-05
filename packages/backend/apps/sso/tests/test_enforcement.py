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
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.multitenancy import constants as multitenancy_constants
from apps.sso import constants
from apps.users.jwt import create_jwt_tokens
from apps.sso.models import TenantDomain
from apps.sso.enforcement import (
    check_tenant_sso_enforcement,
    filter_tenants_for_password_session,
    should_enforce_sso_for_session,
)

pytestmark = pytest.mark.django_db


def _request(user, auth_method=None, sso_tenant_id=None):
    auth = {}
    if auth_method:
        auth["auth_method"] = auth_method
    if sso_tenant_id is not None:
        auth["sso_tenant_id"] = str(sso_tenant_id)
    return SimpleNamespace(user=user, auth=auth or None, META={})


class TestShouldEnforceSsoForSession:
    def test_enforces_for_password_session(self, user):
        assert should_enforce_sso_for_session(_request(user, "password"), tenant_id=7) is True

    def test_enforces_for_oauth_session(self, user):
        assert should_enforce_sso_for_session(_request(user, "oauth"), tenant_id=7) is True

    def test_enforces_when_auth_method_claim_is_missing(self, user):
        """A missing/legacy claim defaults to 'password' (see
        get_auth_method_from_token) and must stay enforced, not exempted."""
        assert should_enforce_sso_for_session(_request(user), tenant_id=7) is True

    def test_does_not_enforce_for_sso_session_of_the_same_tenant(self, user):
        assert should_enforce_sso_for_session(_request(user, "sso", sso_tenant_id=7), tenant_id=7) is False

    def test_enforces_for_sso_session_of_another_tenant(self, user):
        """An SSO login through tenant A's identity provider must not satisfy tenant B's SSO rule."""
        assert should_enforce_sso_for_session(_request(user, "sso", sso_tenant_id=3), tenant_id=7) is True

    def test_enforces_for_sso_session_without_tenant_claim(self, user):
        """Tokens issued before the tenant claim existed are enforced, so the user signs in once more."""
        assert should_enforce_sso_for_session(_request(user, "sso"), tenant_id=7) is True


class TestFilterTenantsForPasswordSession:
    def test_excludes_sso_enforced_tenant_for_oauth_session(
        self, user, tenant_factory, tenant_membership_factory, active_sso_connection
    ):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        verify_domain_for(active_sso_connection.tenant, domain)
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
        verify_domain_for(active_sso_connection.tenant, domain)
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        from apps.multitenancy.models import Tenant

        queryset = Tenant.objects.filter(pk=active_sso_connection.tenant_id)
        request = _request(user, "sso", sso_tenant_id=active_sso_connection.tenant_id)
        result = filter_tenants_for_password_session(request, queryset)

        assert list(result.values_list("pk", flat=True)) == [active_sso_connection.tenant_id]

    def test_excludes_enforced_tenant_for_sso_session_of_another_tenant(
        self, user, tenant_membership_factory, active_sso_connection
    ):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        verify_domain_for(active_sso_connection.tenant, domain)
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        from apps.multitenancy.models import Tenant

        queryset = Tenant.objects.filter(pk=active_sso_connection.tenant_id)
        # Logged in through some other tenant's identity provider; this tenant's rule still applies
        request = _request(user, "sso", sso_tenant_id=active_sso_connection.tenant_id + 1)
        result = filter_tenants_for_password_session(request, queryset)

        assert list(result.values_list("pk", flat=True)) == []


def verify_domain_for(tenant, domain):
    TenantDomain.objects.update_or_create(
        tenant=tenant,
        domain=domain,
        defaults={"status": constants.SSODomainStatus.VERIFIED, "verified_at": timezone.now()},
    )


class TestCheckTenantSsoEnforcement:
    def test_blocks_oauth_session_without_break_glass_permission(
        self, user, tenant_membership_factory, active_sso_connection
    ):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        verify_domain_for(active_sso_connection.tenant, domain)
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        result = check_tenant_sso_enforcement(_request(user, "oauth"), active_sso_connection.tenant, user)

        assert result == "sso_login_required"

    def test_unverified_domain_does_not_enforce_sso(self, user, tenant_membership_factory, active_sso_connection):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        # The connection factory verifies its domains by default; this test needs the claim left unverified
        TenantDomain.objects.filter(tenant=active_sso_connection.tenant, domain=domain).update(
            status=constants.SSODomainStatus.PENDING
        )
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        result = check_tenant_sso_enforcement(_request(user, "oauth"), active_sso_connection.tenant, user)

        assert result is None

    def test_allows_sso_session(self, user, tenant_membership_factory, active_sso_connection):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        verify_domain_for(active_sso_connection.tenant, domain)
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        request = _request(user, "sso", sso_tenant_id=active_sso_connection.tenant_id)
        result = check_tenant_sso_enforcement(request, active_sso_connection.tenant, user)

        assert result is None

    def test_blocks_sso_session_of_another_tenant(self, user, tenant_membership_factory, active_sso_connection):
        domain = user.email.rsplit("@", 1)[-1]
        active_sso_connection.enforce_sso = True
        active_sso_connection.allowed_domains = [domain]
        active_sso_connection.save()
        verify_domain_for(active_sso_connection.tenant, domain)
        tenant_membership_factory(
            user=user, tenant=active_sso_connection.tenant, role=multitenancy_constants.TenantUserRole.MEMBER
        )

        request = _request(user, "sso", sso_tenant_id=active_sso_connection.tenant_id + 1)
        result = check_tenant_sso_enforcement(request, active_sso_connection.tenant, user)

        assert result == "sso_login_required"


class TestSsoTenantClaim:
    def test_refresh_keeps_the_tenant_claim(self, user):
        """Refreshing the session must not drop the claim, or the SSO exemption would be lost mid-session."""
        tokens = create_jwt_tokens(user, auth_method="sso", sso_tenant_id="7")

        refreshed_access = RefreshToken(tokens["refresh"]).access_token

        assert refreshed_access["auth_method"] == "sso"
        assert refreshed_access["sso_tenant_id"] == "7"
