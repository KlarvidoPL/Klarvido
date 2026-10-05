"""
While SSO is switched off (SSO_CONFIGURATION_ENABLED=false), nothing can use it: no sign-in through SSO, no
discovery, no enforcement, no SCIM. The switch is off by default.
"""

import pytest

from apps.sso import constants
from apps.sso.availability import SSOEnabledPermission
from apps.sso.enforcement import get_sso_enforced_tenant_ids
from apps.sso.tests import factories

pytestmark = pytest.mark.django_db


@pytest.fixture
def sso_off(settings):
    settings.SSO_CONFIGURATION_ENABLED = False
    return settings


@pytest.fixture
def sso_on(settings):
    settings.SSO_CONFIGURATION_ENABLED = True
    return settings


def test_switch_is_off_by_default():
    """Read the module value, which the autouse fixture in conftest.py does not change."""
    from config import settings as project_settings

    assert project_settings.SSO_CONFIGURATION_ENABLED is False


def test_permission_refuses_configuration_while_off(sso_off):
    assert SSOEnabledPermission().has_permission(None, None) is False


def test_permission_allows_configuration_when_on(sso_on):
    assert SSOEnabledPermission().has_permission(None, None) is True


def test_discovery_reports_no_sso_while_off(sso_off, client, tenant):
    factories.TenantSSOConnectionFactory(
        tenant=tenant, status=constants.SSOConnectionStatus.ACTIVE, allowed_domains=["switch-off.example"]
    )

    response = client.post(
        "/api/graphql/",
        {
            "query": 'query { ssoDiscover(email: "user@switch-off.example") { ssoAvailable requireSso connections { id } } }'
        },
        content_type="application/json",
    )

    assert response.json()["data"]["ssoDiscover"] == {"ssoAvailable": False, "requireSso": False, "connections": []}


def test_enforcement_is_not_applied_while_off(sso_off, user):
    user.email = "person@enforced.example"
    user.save()
    factories.TenantSSOConnectionFactory(
        status=constants.SSOConnectionStatus.ACTIVE,
        enforce_sso=True,
        allowed_domains=["enforced.example"],
    )

    assert get_sso_enforced_tenant_ids(user) == set()


def test_saml_login_is_refused_while_off(sso_off, client):
    connection = factories.TenantSSOConnectionFactory(status=constants.SSOConnectionStatus.ACTIVE)

    response = client.get(f"/api/sso/saml/{connection.pk}/login")

    assert response.status_code == 503


def test_oidc_login_is_refused_while_off(sso_off, client):
    connection = factories.OIDCSSOConnectionFactory(status=constants.SSOConnectionStatus.ACTIVE)

    response = client.get(f"/api/sso/oidc/{connection.pk}/login")

    assert response.status_code == 503


def test_scim_is_refused_while_off(sso_off, client):
    response = client.get("/api/sso/scim/v2/Users", HTTP_AUTHORIZATION="Bearer anything")

    assert response.status_code == 503
