"""
Low-severity hardening: draft SAML metadata is not served, and the domain verification token is only visible
to members who can manage SSO.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from apps.multitenancy.constants import TenantUserRole
from apps.multitenancy.tests.factories import TenantFactory, TenantMembershipFactory
from apps.sso import constants
from apps.sso import schema as sso_schema
from apps.sso.services import domain_verification as dv
from apps.sso.services.saml import SAMLService
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestDraftMetadata:
    def test_draft_connection_serves_no_metadata(self, api_client, tenant_sso_connection):
        response = api_client.get(f"/api/sso/saml/{tenant_sso_connection.id}/metadata")

        assert response.status_code == 404

    def test_active_connection_serves_metadata(self, api_client, tenant_sso_connection):
        tenant_sso_connection.status = constants.SSOConnectionStatus.ACTIVE
        tenant_sso_connection.save()

        with mock.patch.object(SAMLService, "generate_sp_metadata", return_value="<EntityDescriptor/>"):
            response = api_client.get(f"/api/sso/saml/{tenant_sso_connection.id}/metadata")

        assert response.status_code == 200


class TestVerificationRecordVisibility:
    def _info(self, user, tenant):
        return SimpleNamespace(context=SimpleNamespace(user=user, tenant=tenant))

    def test_members_without_sso_permission_do_not_see_the_token(self):
        tenant = TenantFactory()
        user = UserFactory(email="record-member@sso-test.invalid")
        TenantMembershipFactory(user=user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True)
        claim = dv.add_domain(tenant, "client.pl")
        info = self._info(user, tenant)

        assert sso_schema.TenantDomainType.resolve_verification_record_name(claim, info) is None
        assert sso_schema.TenantDomainType.resolve_verification_record_value(claim, info) is None

    def test_owners_see_the_record_to_restore_it(self):
        tenant = TenantFactory()
        user = UserFactory(email="record-owner@sso-test.invalid")
        TenantMembershipFactory(user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True)
        claim = dv.add_domain(tenant, "client.pl")
        info = self._info(user, tenant)

        assert (
            sso_schema.TenantDomainType.resolve_verification_record_name(claim, info) == claim.verification_record_name
        )
        assert (
            sso_schema.TenantDomainType.resolve_verification_record_value(claim, info)
            == claim.verification_record_value
        )
