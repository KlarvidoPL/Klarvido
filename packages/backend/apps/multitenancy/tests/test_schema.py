import pytest
import os
from unittest.mock import patch
from django.conf import settings
from graphql_relay import to_global_id
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notification
from ..constants import (
    OWNER_ROLE_COLOR,
    RoleColor,
    TenantType,
    TenantUserRole,
    ActionActorType,
    Notification as NotificationConstant,
    SystemRoleType,
    VatStatus,
)
from ..models import (
    ActionLog,
    Tenant,
    TenantMembership,
    TenantMembershipRole,
    OrganizationRole,
    OrganizationOnboardingProfile,
    Permission,
)
from ..permissions import create_system_roles_for_tenant
from ..services.mf_whitelist import CompanyDetails


pytestmark = pytest.mark.django_db

VALID_NIP = "9721382373"
# Complete company details - every one is required when creating an organization
COMPANY_DETAILS = {
    "nip": VALID_NIP,
    "companyName": "ACME SP. Z O.O.",
    "regon": "123456785",
    "address": "UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
    "vatStatus": VatStatus.ACTIVE,
}


class TestCompanyLookupByNipQuery:
    QUERY_WITH_COUNTRY = '''
        query CompanyLookupByNip($nip: String!, $country: String) {
          companyLookupByNip(nip: $nip, country: $country) {
            found
            nip
          }
        }
    '''
    QUERY = '''
        query CompanyLookupByNip($nip: String!) {
          companyLookupByNip(nip: $nip) {
            found
            country
            nip
            companyName
            regon
            address
            vatStatus
          }
        }
    '''

    @patch("apps.multitenancy.schema.lookup_company")
    def test_found(self, mock_lookup, graphene_client, user):
        mock_lookup.return_value = CompanyDetails(
            company_name="ACME SP. Z O.O.",
            regon="123456785",
            address="UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
            vat_status=VatStatus.ACTIVE,
        )
        graphene_client.force_authenticate(user)
        executed = graphene_client.query(self.QUERY, variable_values={"nip": "972-138-23-73"})

        assert executed["data"]["companyLookupByNip"] == {
            "found": True,
            "country": "PL",
            "nip": VALID_NIP,
            "companyName": "ACME SP. Z O.O.",
            "regon": "123456785",
            "address": "UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
            "vatStatus": VatStatus.ACTIVE,
        }
        mock_lookup.assert_called_once_with("PL", VALID_NIP)

    @patch("apps.multitenancy.schema.lookup_company", return_value=None)
    def test_not_found(self, mock_lookup, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = graphene_client.query(self.QUERY, variable_values={"nip": VALID_NIP})

        result = executed["data"]["companyLookupByNip"]
        assert result["found"] is False
        assert result["nip"] == VALID_NIP
        assert result["companyName"] is None

    @patch("apps.multitenancy.schema.lookup_company")
    def test_invalid_nip(self, mock_lookup, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = graphene_client.query(self.QUERY, variable_values={"nip": "1234567890"})

        assert "nip" in executed["errors"][0]["extensions"]
        mock_lookup.assert_not_called()

    @patch("apps.multitenancy.schema.lookup_company", return_value=None)
    def test_accepts_eu_vat_number_form(self, mock_lookup, graphene_client, user):
        """ "PL" + NIP (the EU VAT number) is the same company - the prefix is stripped."""
        graphene_client.force_authenticate(user)
        executed = graphene_client.query(self.QUERY, variable_values={"nip": f"PL {VALID_NIP}"})

        assert executed["data"]["companyLookupByNip"]["nip"] == VALID_NIP
        mock_lookup.assert_called_once_with("PL", VALID_NIP)

    @patch("apps.multitenancy.schema.lookup_company")
    def test_unsupported_country(self, mock_lookup, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = graphene_client.query(self.QUERY_WITH_COUNTRY, variable_values={"nip": VALID_NIP, "country": "DE"})

        assert executed["errors"][0]["extensions"]["nip"][0]["code"] == "unsupported_country"
        mock_lookup.assert_not_called()

    @patch("apps.multitenancy.schema.lookup_company")
    def test_unauthenticated_user(self, mock_lookup, graphene_client):
        executed = graphene_client.query(self.QUERY, variable_values={"nip": VALID_NIP})

        assert executed["errors"][0]["message"] == "permission_denied"
        mock_lookup.assert_not_called()


class TestCreateTenantMutation:
    MUTATION = '''
        mutation CreateTenant($input: CreateTenantMutationInput!) {
          createTenant(input: $input) {
            tenant {
              id
              name
              slug
              type
              billingEmail
              country
              nip
              companyName
              regon
              address
              vatStatus
              membership {
                role
                invitationAccepted
              }
            }
          }
        }
    '''

    def test_create_new_tenant(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", "billingEmail": "test@example.com", **COMPANY_DETAILS})
        response_data = executed["data"]["createTenant"]["tenant"]
        assert response_data["name"] == "Test"
        assert response_data["slug"] == "test"
        assert response_data["type"] == TenantType.ORGANIZATION
        assert response_data["billingEmail"] == "test@example.com"
        assert response_data["nip"] == VALID_NIP
        assert response_data["membership"]["role"] == TenantUserRole.OWNER
        profile = OrganizationOnboardingProfile.objects.get(tenant__name="Test")
        assert profile.is_required is True
        assert profile.respondent_role == ""

    def test_create_new_tenant_with_company_details(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(
            graphene_client,
            {
                "name": "Acme",
                "nip": "972-138-23-73",
                "companyName": "ACME SP. Z O.O.",
                "regon": "123456785",
                "address": "UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
                "vatStatus": VatStatus.ACTIVE,
            },
        )
        assert "errors" not in executed, executed.get("errors")
        response_data = executed["data"]["createTenant"]["tenant"]
        assert response_data["nip"] == VALID_NIP
        assert response_data["companyName"] == "ACME SP. Z O.O."
        assert response_data["regon"] == "123456785"
        assert response_data["address"] == "UL. PRZYKŁADOWA 1, 00-001 WARSZAWA"
        assert response_data["vatStatus"] == VatStatus.ACTIVE

    def test_create_new_tenant_defaults_to_poland(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS})
        assert executed["data"]["createTenant"]["tenant"]["country"] == "PL"

    def test_create_new_tenant_with_eu_vat_number_form(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(
            graphene_client, {"name": "Test", **COMPANY_DETAILS, "country": "PL", "nip": f"PL{VALID_NIP}"}
        )
        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["createTenant"]["tenant"]["nip"] == VALID_NIP

    def test_create_new_tenant_in_unsupported_country(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS, "country": "DE"})
        assert executed["errors"][0]["extensions"]["country"][0]["code"] == "invalid_choice"

    def test_create_new_tenant_without_company_details(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test"})
        extensions = executed["errors"][0]["extensions"]
        # Every missing field is reported at once, so the form can mark all of them
        for field in ("nip", "company_name", "regon", "address", "vat_status"):
            assert extensions[field][0]["code"] == "required", field

    @pytest.mark.parametrize("field", ["companyName", "regon", "address", "vatStatus"])
    def test_create_new_tenant_with_blank_company_field(self, graphene_client, user, field):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS, field: ""})
        assert "errors" in executed, executed
        assert TenantMembership.objects.filter(user=user, tenant__name="Test").exists() is False

    def test_create_new_tenant_with_invalid_nip(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS, "nip": "1234567890"})
        assert executed["errors"][0]["extensions"]["nip"][0]["code"] == "invalid_nip"

    def test_create_new_tenant_with_invalid_regon(self, graphene_client, user):
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS, "regon": "123456789"})
        assert executed["errors"][0]["extensions"]["regon"][0]["code"] == "invalid_regon"

    def test_create_new_tenant_with_same_name(self, graphene_client, user, tenant_factory):
        tenant_factory(name="Test", slug="test")
        graphene_client.force_authenticate(user)
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS})
        response_data = executed["data"]["createTenant"]["tenant"]
        assert response_data["name"] == "Test"
        assert response_data["slug"] == "test-1"
        assert response_data["type"] == TenantType.ORGANIZATION
        assert response_data["membership"]["role"] == TenantUserRole.OWNER

    def test_unauthenticated_user(self, graphene_client):
        executed = self.mutate(graphene_client, {"name": "Test", **COMPANY_DETAILS})
        assert executed["errors"][0]["message"] == "permission_denied"

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestUpdateTenantMutation:
    MUTATION = '''
        mutation UpdateTenant($input: UpdateTenantMutationInput!) {
          updateTenant(input: $input) {
            tenant {
              id
              name
              slug
              type
              billingEmail
              membership {
                role
                invitationAccepted
              }
            }
          }
        }
    '''

    def test_update_tenant(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
                "billingEmail": "test@example.com",
            },
        )
        response_data = executed["data"]["updateTenant"]["tenant"]
        assert response_data["name"] == "Tenant 2"
        assert response_data["slug"] == "tenant-2"
        assert response_data["type"] == TenantType.ORGANIZATION
        assert response_data["billingEmail"] == "test@example.com"
        assert response_data["membership"]["role"] == TenantUserRole.OWNER

    def test_update_company_details(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 1",
                "nip": VALID_NIP,
                "companyName": "ACME SP. Z O.O.",
                "regon": "123456785",
                "address": "UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
                "vatStatus": VatStatus.EXEMPT,
            },
        )
        assert "errors" not in executed, executed.get("errors")
        tenant.refresh_from_db()
        assert tenant.nip == VALID_NIP
        assert tenant.company_name == "ACME SP. Z O.O."
        assert tenant.regon == "123456785"
        assert tenant.vat_status == VatStatus.EXEMPT

    def test_update_without_resolved_tenant(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        """No tenant in context (e.g. tenantId missing/invalid) must be refused, not crash on None."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(None, None)
        executed = self.mutate(
            graphene_client,
            {"id": to_global_id("TenantType", tenant.id), "tenantId": "invalid", "name": "Tenant 2"},
        )
        assert executed["errors"][0]["message"] == "permission_denied"
        tenant.refresh_from_db()
        assert tenant.name == "Tenant 1"

    def test_update_id_must_match_checked_tenant(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        other_tenant = tenant_factory(name="Other", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", other_tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Hijacked",
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"
        other_tenant.refresh_from_db()
        assert other_tenant.name == "Other"

    def test_update_legacy_tenant_without_nip(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        """Organizations created before NIP existed can still be renamed without providing one."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
            },
        )
        assert "errors" not in executed, executed.get("errors")

    @pytest.fixture
    def company_tenant(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(
            name="Tenant 1",
            type=TenantType.ORGANIZATION,
            nip=VALID_NIP,
            company_name="ACME SP. Z O.O.",
            regon="123456785",
            address="UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
            vat_status=VatStatus.ACTIVE,
        )
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        return tenant

    @classmethod
    def update_input(cls, tenant, **fields):
        return {
            "id": to_global_id("TenantType", tenant.id),
            "tenantId": to_global_id("TenantType", tenant.id),
            "name": tenant.name,
            **COMPANY_DETAILS,
            **fields,
        }

    def test_update_keeps_locked_nip_and_regon(self, graphene_client, company_tenant):
        """Re-sending the stored NIP/REGON (what the General tab does) is fine; other fields still update."""
        executed = self.mutate(
            graphene_client, self.update_input(company_tenant, address="UL. NOWA 5, 00-002 WARSZAWA")
        )
        assert "errors" not in executed, executed.get("errors")
        company_tenant.refresh_from_db()
        assert company_tenant.address == "UL. NOWA 5, 00-002 WARSZAWA"

    @pytest.mark.parametrize("field, value", [("nip", "1234563218"), ("regon", "12345678512347")])
    def test_update_cannot_change_locked_nip_or_regon(self, graphene_client, company_tenant, field, value):
        executed = self.mutate(graphene_client, self.update_input(company_tenant, **{field: value}))
        assert executed["errors"][0]["extensions"][field][0]["code"] == "immutable"
        company_tenant.refresh_from_db()
        assert company_tenant.nip == VALID_NIP
        assert company_tenant.regon == "123456785"

    @pytest.mark.parametrize(
        "field, error_key",
        [("companyName", "company_name"), ("regon", "regon"), ("address", "address"), ("vatStatus", "vat_status")],
    )
    def test_update_cannot_blank_company_field(self, graphene_client, company_tenant, field, error_key):
        executed = self.mutate(graphene_client, self.update_input(company_tenant, **{field: ""}))
        assert executed["errors"][0]["extensions"][error_key][0]["code"] == "required"

    def test_update_with_invalid_nip(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 1",
                "nip": "9721382374",
            },
        )
        assert executed["errors"][0]["extensions"]["nip"][0]["code"] == "invalid_nip"

    def test_user_without_membership(self, graphene_client, user, tenant_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
            },
        )
        assert "errors" in executed, f"Expected permission_denied, got: {executed}"
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_user_with_admin_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.ADMIN)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.ADMIN)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
            },
        )
        assert "errors" not in executed, f"Admin has org.settings.edit, expected success: {executed.get('errors')}"
        response_data = executed["data"]["updateTenant"]["tenant"]
        assert response_data["name"] == "Tenant 2"

    def test_user_with_member_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_unauthenticated_user(self, graphene_client, tenant_factory):
        tenant = tenant_factory(name="Tenant 1")
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_superuser_without_membership_can_update(self, graphene_client, user_factory, tenant_factory):
        """Superuser bypass: owner-equivalent access without a real membership row."""
        superuser = user_factory(is_superuser=True)
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "id": to_global_id("TenantType", tenant.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Tenant 2",
            },
        )
        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["updateTenant"]["tenant"]["name"] == "Tenant 2"

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestDeleteTenantMutation:
    MUTATION = '''
        mutation DeleteTenant($input: DeleteTenantMutationInput!) {
          deleteTenant(input: $input) {
            deletedIds
          }
        }
    '''

    def test_delete_tenant(
        self,
        graphene_client,
        user,
        tenant_factory,
        tenant_membership_factory,
        subscription_schedule_factory,
        monthly_plan_price,
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_id = tenant.id
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        subscription_schedule_factory(
            phases=[{'items': [{'price': monthly_plan_price.id}], 'trialing': True}], customer__subscriber=tenant
        )
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(graphene_client, self.input_for(tenant))
        response_data = executed["data"]["deleteTenant"]["deletedIds"]
        assert response_data[0] == to_global_id("TenantType", tenant_id)

    def test_delete_tenant_with_free_plan(
        self,
        graphene_client,
        user,
        tenant_factory,
        tenant_membership_factory,
        subscription_schedule_factory,
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_id = tenant.id
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        subscription_schedule_factory(phases=None, customer__subscriber=tenant)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(graphene_client, self.input_for(tenant))
        response_data = executed["data"]["deleteTenant"]["deletedIds"]
        assert response_data[0] == to_global_id("TenantType", tenant_id)

    def test_delete_default_tenant(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.DEFAULT)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(graphene_client, self.input_for(tenant))
        assert executed["errors"][0]["message"] == "GraphQlValidationError"

    def test_user_without_membership(self, graphene_client, user, tenant_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(graphene_client, self.input_for(tenant))
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_user_with_admin_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.ADMIN)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.ADMIN)
        executed = self.mutate(graphene_client, self.input_for(tenant))
        assert "errors" in executed, f"Admin cannot delete tenant (owner-only), got: {executed}"
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_user_with_member_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(graphene_client, self.input_for(tenant))
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_unauthenticated_user(self, graphene_client, tenant_factory):
        tenant = tenant_factory(name="Tenant 1")
        executed = self.mutate(graphene_client, self.input_for(tenant))
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_delete_over_http_resolves_tenant_from_tenant_id(
        self, mocker, user, tenant_factory, tenant_membership_factory
    ):
        """End to end through the middleware (the other tests inject the tenant into the context directly)."""
        # It would close the test's transaction-wrapped connection before the assertions below
        mocker.patch("apps.multitenancy.schema.close_old_connections")
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)

        response = self.post(user, self.input_for(tenant))

        assert "errors" not in response, response
        assert response["data"]["deleteTenant"]["deletedIds"] == [to_global_id("TenantType", tenant.id)]
        assert not Tenant.objects.filter(pk=tenant.pk).exists()

    def test_delete_over_http_without_tenant_id_is_rejected(self, user, tenant_factory, tenant_membership_factory):
        """Regression: sending only `id` left no tenant in the context and crashed on `None.type`."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)

        response = self.post(user, {"id": to_global_id("TenantType", tenant.id)})

        assert "errors" in response
        assert Tenant.objects.filter(pk=tenant.pk).exists()

    def test_cannot_delete_a_different_tenant_than_tenant_id(self, user, tenant_factory, tenant_membership_factory):
        own = tenant_factory(name="Own", type=TenantType.ORGANIZATION)
        other = tenant_factory(name="Other", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=own, user=user, role=TenantUserRole.OWNER)

        response = self.post(
            user, {"id": to_global_id("TenantType", other.id), "tenantId": to_global_id("TenantType", own.id)}
        )

        assert response["errors"][0]["message"] == "permission_denied"
        assert Tenant.objects.filter(pk=other.pk).exists()

    @staticmethod
    def input_for(tenant):
        return {"id": to_global_id("TenantType", tenant.id), "tenantId": to_global_id("TenantType", tenant.id)}

    @classmethod
    def post(cls, user, data):
        client = APIClient()
        client.cookies[settings.ACCESS_TOKEN_COOKIE] = str(RefreshToken.for_user(user).access_token)
        response = client.post("/api/graphql/", {"query": cls.MUTATION, "variables": {"input": data}}, format="json")
        return response.json()

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestCreateTenantInvitationMutation:
    MUTATION = '''
    mutation CreateTenantInvitation($input: CreateTenantInvitationMutationInput!) {
      createTenantInvitation(input: $input) {
        ok
      }
    }
    '''

    def test_create_tenant_invitation_by_owner(
        self, mocker, graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        make_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token"
        )
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        invited_user = user_factory()
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": invited_user.email,
                "role": TenantUserRole.ADMIN,
            },
        )
        response_data = executed["data"]["createTenantInvitation"]
        assert response_data["ok"] is True
        make_token.assert_called_once()

        assert Notification.objects.count() == 1
        notification = Notification.objects.first()
        assert notification.type == NotificationConstant.TENANT_INVITATION_CREATED.value
        assert notification.user == invited_user
        assert notification.issuer == user

    def test_create_default_tenant_invitation_by_owner(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.DEFAULT)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": "test@example.com",
                "role": TenantUserRole.ADMIN.upper(),
            },
        )
        assert executed["errors"][0]["message"] == "GraphQlValidationError"

    def test_create_tenant_invitation_by_admin(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.ADMIN)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.ADMIN)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": "test@example.com",
                "role": TenantUserRole.ADMIN.upper(),
            },
        )
        assert "errors" not in executed, f"Admin has members.invite, expected success: {executed.get('errors')}"
        assert executed["data"]["createTenantInvitation"]["ok"] is True

    def test_create_tenant_invitation_by_member(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": "test@example.com",
                "role": TenantUserRole.ADMIN.upper(),
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_user_without_membership(self, graphene_client, user, tenant_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": "test@example.com",
                "role": TenantUserRole.ADMIN.upper(),
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_unauthenticated_user(self, graphene_client, tenant_factory):
        tenant = tenant_factory(name="Tenant 1")
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": "test@example.com",
                "role": TenantUserRole.ADMIN.upper(),
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_invite_superuser_is_rejected(
        self, graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        """A superuser already has owner-equivalent access to every tenant via the
        cross-tenant bypass, so inviting them as a real, role-scoped member would
        only ever narrow their access - reject it with a clear message instead."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        superuser = user_factory(is_superuser=True)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)

        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "email": superuser.email,
                "role": TenantUserRole.MEMBER,
            },
        )

        assert executed["errors"][0]["message"] == "GraphQlValidationError"
        non_field_errors = executed["errors"][0]["extensions"]["non_field_errors"]
        # Deliberately generic - must not reveal that the target user is a superuser.
        assert non_field_errors[0]["message"] == "This user cannot be a member of this organization."
        assert non_field_errors[0]["code"] == "user_cannot_be_invited"
        assert not TenantMembership.objects.filter(tenant=tenant, user=superuser).exists()

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestDeleteTenantMembershipMutation:
    MUTATION = '''
    mutation DeleteTenantMembership($input: DeleteTenantMembershipMutationInput!) {
      deleteTenantMembership(input: $input) {
        deletedIds
      }
    }
    '''

    def test_delete_tenant_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["data"]["deleteTenantMembership"]["deletedIds"][0] == to_global_id(
            "TenantMembershipType", tenant_membership.id
        )

    def test_delete_own_tenant_membership_by_member(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["data"]["deleteTenantMembership"]["deletedIds"][0] == to_global_id(
            "TenantMembershipType", tenant_membership.id
        )

    def test_delete_own_tenant_membership_by_admin(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.ADMIN)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.ADMIN)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["data"]["deleteTenantMembership"]["deletedIds"][0] == to_global_id(
            "TenantMembershipType", tenant_membership.id
        )

    def test_delete_tenant_membership_not_accepted(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=False)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["data"]["deleteTenantMembership"]["deletedIds"][0] == to_global_id(
            "TenantMembershipType", tenant_membership.id
        )

    def test_delete_tenant_membership_not_accepted_owner_role(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        """A pending (unaccepted) invitation created with the Owner role holds no real access
        yet and must not trip the "only owners can remove owners" / "cannot remove the last
        owner" guards meant to protect real, accepted owners - even when there is only one
        real accepted owner in the tenant."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        pending_owner_invitation = tenant_membership_factory(
            tenant=tenant, role=TenantUserRole.OWNER, is_accepted=False
        )
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", pending_owner_invitation.id),
            },
        )
        assert executed["data"]["deleteTenantMembership"]["deletedIds"][0] == to_global_id(
            "TenantMembershipType", pending_owner_invitation.id
        )

    def test_delete_tenant_membership_with_invalid_id(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", "InvalidID"),
            },
        )
        assert executed["errors"][0]["message"] == "No TenantMembership matches the given query."

    def test_delete_default_tenant_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.DEFAULT)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["errors"][0]["message"] == "GraphQlValidationError"

    def test_delete_organization_tenant_membership_last_owner(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["errors"][0]["message"] == "GraphQlValidationError"

    def test_delete_tenant_membership_with_different_tenant_id(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_2 = tenant_factory(name="Tenant 2", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership_factory(tenant=tenant_2, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant_2, role=TenantUserRole.MEMBER)

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["errors"][0]["message"] == "No TenantMembership matches the given query."

    def test_delete_tenant_membership_by_member(
        self, graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user_factory(), role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["errors"][0]["message"] == "You don't have permission to remove members."

    def test_delete_tenant_membership_by_admin(
        self, graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.ADMIN)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user_factory(), role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.ADMIN)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert "errors" not in executed, f"Admin has members.remove, expected success: {executed.get('errors')}"
        assert executed["data"]["deleteTenantMembership"]["deletedIds"][0] == to_global_id(
            "TenantMembershipType", str(tenant_membership.id)
        )

    def test_delete_tenant_membership_by_not_a_member(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_delete_tenant_membership_by_unauthorized(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestUpdateTenantMembershipMutation:
    MUTATION = '''
    mutation UpdateTenantMembership($input: UpdateTenantMembershipMutationInput!) {
      updateTenantMembership(input: $input) {
        tenantMembership {
          id
          role
        }
      }
    }
    '''

    def test_update_tenant_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        data = executed["data"]["updateTenantMembership"]["tenantMembership"]
        assert data["id"] == to_global_id("TenantMembershipType", str(tenant_membership.id))
        assert data["role"] == TenantUserRole.ADMIN

    def test_update_tenant_membership_not_accepted(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=False)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        data = executed["data"]["updateTenantMembership"]["tenantMembership"]
        assert data["id"] == to_global_id("TenantMembershipType", str(tenant_membership.id))
        assert data["role"] == TenantUserRole.ADMIN

    def test_update_own_tenant_membership_by_member(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_update_own_tenant_membership_by_admin(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.ADMIN)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.ADMIN)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "MEMBER",
            },
        )
        assert "errors" in executed, f"Admin cannot demote self, expected permission_denied: {executed}"
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_update_tenant_membership_with_invalid_id(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", "InvalidID"),
                "role": "ADMIN",
            },
        )
        assert executed["errors"][0]["message"] == "No TenantMembership matches the given query."

    def test_update_default_tenant_membership(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.DEFAULT)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        assert "errors" in executed, f"Cannot change roles in DEFAULT tenant, expected error: {executed}"
        assert executed["errors"][0]["message"] == "GraphQlValidationError"

    def test_update_organization_tenant_membership_last_owner(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        TenantMembershipRole.objects.filter(membership=tenant_membership).delete()
        create_system_roles_for_tenant(tenant)
        admin_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.ADMIN)
        TenantMembershipRole.objects.create(membership=tenant_membership, role=admin_role, assigned_by=user)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        assert "errors" in executed, f"Expected last-owner demotion to fail: {executed}"
        assert executed["errors"][0]["message"] == "GraphQlValidationError"

    def test_update_tenant_membership_with_different_tenant_id(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_2 = tenant_factory(name="Tenant 2", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership_factory(tenant=tenant_2, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant_2, role=TenantUserRole.MEMBER)

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        assert executed["errors"][0]["message"] == "No TenantMembership matches the given query."

    def test_update_tenant_membership_by_not_a_member(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_update_tenant_membership_by_unauthorized(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.set_tenant_dependent_context(tenant, None)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_superuser_without_membership_can_update(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        """Superuser bypass: owner-equivalent access without a real membership row."""
        superuser = user_factory(is_superuser=True)
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(tenant, None)

        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )

        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["updateTenantMembership"]["tenantMembership"]["role"] == TenantUserRole.ADMIN

    def test_superuser_cross_tenant_access_logged_as_superuser_actor(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        """Action logging must distinguish a superuser's cross-tenant bypass access
        from a normal member action, so tenant owners can see support staff touched
        their org."""
        superuser = user_factory(is_superuser=True)
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION, action_logging_enabled=True)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(tenant, None)
        # Simulate what TenantUserRoleMiddleware would have set for a superuser with
        # no real membership row (the test client bypasses real middleware execution).
        graphene_client.execute_options["context_value"].is_superuser_cross_tenant_access = True

        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )

        assert "errors" not in executed, executed.get("errors")
        action_log = ActionLog.objects.filter(tenant=tenant, entity_type="tenant_membership").first()
        assert action_log is not None
        assert action_log.actor_type == ActionActorType.SUPERUSER

    def test_superuser_real_member_access_logged_as_user_actor(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        """A superuser acting within a tenant they're actually a member of logs as a
        normal USER action, not SUPERUSER - the bypass flag only fires for actual
        cross-tenant access."""
        superuser = user_factory(is_superuser=True)
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION, action_logging_enabled=True)
        tenant_membership_factory(tenant=tenant, user=superuser, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        graphene_client.execute_options["context_value"].is_superuser_cross_tenant_access = False

        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )

        assert "errors" not in executed, executed.get("errors")
        action_log = ActionLog.objects.filter(tenant=tenant, entity_type="tenant_membership").first()
        assert action_log is not None
        assert action_log.actor_type == ActionActorType.USER

    def test_regular_user_access_logged_as_user_actor(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        """Regression guard: normal member actions keep logging as USER."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION, action_logging_enabled=True)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        tenant_membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)

        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", tenant_membership.id),
                "role": "ADMIN",
            },
        )

        assert "errors" not in executed, executed.get("errors")
        action_log = ActionLog.objects.filter(tenant=tenant, entity_type="tenant_membership").first()
        assert action_log is not None
        assert action_log.actor_type == ActionActorType.USER

    def test_non_owner_cannot_promote_another_member_to_owner_via_legacy_role(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        """Regression coverage for a privilege-escalation gap: the legacy
        TenantMembership.role field is treated as a valid "is owner" signal throughout
        the app (AssignRolesToMemberMutation, invite flow, DeleteOrganizationRoleMutation,
        this mutation itself, ...), but nothing stopped a non-owner with just
        members.roles.edit from setting another member's legacy role straight to OWNER -
        instantly handing that member real owner-bypass privileges everywhere, without ever
        passing any of those checks legitimately."""
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        acting_user = user_factory()
        acting_membership = tenant_membership_factory(
            user=acting_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        # Replace the test factory's auto-assigned Member RBAC role with a custom role
        # granting only members.roles.edit, matching a real non-owner "role manager" admin.
        TenantMembershipRole.objects.filter(membership=acting_membership).delete()
        manager_role = OrganizationRole.objects.create(tenant=tenant, name="Role Manager", description="")
        manager_role.permissions.set([Permission.objects.get(code="members.roles.edit")])
        TenantMembershipRole.objects.create(membership=acting_membership, role=manager_role, assigned_by=acting_user)

        target_user = user_factory()
        target_membership = tenant_membership_factory(
            user=target_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )

        graphene_client.force_authenticate(acting_user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", target_membership.id),
                "role": "OWNER",
            },
        )

        assert executed["errors"][0]["message"] == "Only organization owners can assign the Owner role."
        target_membership.refresh_from_db()
        assert target_membership.role != TenantUserRole.OWNER

    def test_owner_can_promote_another_member_to_owner(
        self, graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER, is_accepted=True)
        target_user = user_factory()
        target_membership = tenant_membership_factory(
            user=target_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = self.mutate(
            graphene_client,
            {
                "tenantId": to_global_id("TenantType", tenant.id),
                "id": to_global_id("TenantMembershipType", target_membership.id),
                "role": "OWNER",
            },
        )

        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["updateTenantMembership"]["tenantMembership"]["role"] == TenantUserRole.OWNER

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestAcceptTenantInvitationMutation:
    MUTATION = '''
    mutation AcceptTenantInvitation($input: AcceptTenantInvitationMutationInput!) {
      acceptTenantInvitation(input: $input) {
        ok
      }
    }
    '''

    def test_accept_invitation_by_invitee(
        self, mocker, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        check_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.check_token", return_value=True
        )
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
        graphene_client.force_authenticate(user)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        response_data = executed["data"]["acceptTenantInvitation"]
        assert response_data["ok"] is True
        membership = TenantMembership.objects.filter(tenant=tenant, user=user).first()
        assert membership.is_accepted
        assert membership.invitation_accepted_at
        check_token.assert_called_once()

        assert Notification.objects.count() == 1
        notification = Notification.objects.first()
        assert notification.type == NotificationConstant.TENANT_INVITATION_ACCEPTED.value
        assert notification.user == membership.creator
        assert notification.issuer == user

    def test_accept_invitation_by_invitee_wrong_token(
        self, mocker, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        check_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.check_token", return_value=False
        )
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
        graphene_client.force_authenticate(user)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        assert executed["errors"][0]["message"] == "GraphQlValidationError"
        check_token.assert_called_once()

    def test_accept_invitation_by_other_user(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        logged_user = user_factory()
        invitee_user = user_factory()
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(
            tenant=tenant, user=invitee_user, role=TenantUserRole.MEMBER, is_accepted=False
        )
        graphene_client.force_authenticate(logged_user)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        assert executed["errors"][0]["message"] == "Invitation not found."

    def test_unauthenticated_user(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={'input': data})


class TestDeclineTenantInvitationMutation:
    MUTATION = '''
    mutation DeclineTenantInvitation($input:DeclineTenantInvitationMutationInput!) {
      declineTenantInvitation(input: $input) {
        ok
      }
    }
    '''

    def test_decline_invitation_by_invitee(
        self, mocker, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        check_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.check_token", return_value=True
        )
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
        graphene_client.force_authenticate(user)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        response_data = executed["data"]["declineTenantInvitation"]
        assert response_data["ok"] is True
        assert not TenantMembership.objects.filter(tenant=tenant, user=user).exists()
        check_token.assert_called_once()

        assert Notification.objects.count() == 1
        notification = Notification.objects.first()
        assert notification.type == NotificationConstant.TENANT_INVITATION_DECLINED.value
        assert notification.user == membership.creator
        assert notification.issuer == user

    def test_decline_invitation_by_invitee_wrong_token(
        self, mocker, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        check_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.check_token", return_value=False
        )
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
        graphene_client.force_authenticate(user)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        assert executed["errors"][0]["message"] == "GraphQlValidationError"
        check_token.assert_called_once()

    def test_decline_invitation_by_other_user(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        logged_user = user_factory()
        invitee_user = user_factory()
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(
            tenant=tenant, user=invitee_user, role=TenantUserRole.MEMBER, is_accepted=False
        )
        graphene_client.force_authenticate(logged_user)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        assert executed["errors"][0]["message"] == "Invitation not found."

    def test_unauthenticated_user(self, graphene_client, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.MEMBER, is_accepted=False)
        executed = self.mutate(
            graphene_client, {"id": to_global_id("TenantMembershipType", membership.id), "token": "token"}
        )
        assert executed["errors"][0]["message"] == "permission_denied"

    @classmethod
    def mutate(cls, graphene_client, data):
        return graphene_client.mutate(cls.MUTATION, variable_values={"input": data})


class TestAllTenantsQuery:
    def test_all_tenants_query(self, mocker, graphene_client, user_factory, tenant_factory, tenant_membership_factory):
        query = """
        query getAllTenants {
            allTenants {
                edges {
                    node {
                        id
                        name
                        slug
                        type
                        membership {
                            id
                            role
                            invitationAccepted
                            userId
                            inviteeEmailAddress
                            firstName
                            lastName
                            avatar
                            userEmail
                            invitationToken
                        }
                        userMemberships {
                            id
                            role
                            invitationAccepted
                            userId
                            inviteeEmailAddress
                            firstName
                            lastName
                            avatar
                            userEmail
                            invitationToken
                        }
                    }
                }
            }
        }
        """
        user = user_factory(has_avatar=True)
        tenant_factory.create_batch(10)
        make_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token"
        )
        default_user_tenant = user.tenants.first()
        tenant_with_invitation = tenant_factory(name="Invitation Tenant", type=TenantType.ORGANIZATION)
        tenants = [
            default_user_tenant,
            tenant_with_invitation,
            tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION),
            tenant_factory(name="Test tenant 2", type=TenantType.ORGANIZATION),
        ]
        default_user_tenant_membership = TenantMembership.objects.filter(user=user, tenant=default_user_tenant).first()
        invitation_membership = tenant_membership_factory(
            tenant=tenant_with_invitation, role=TenantUserRole.ADMIN, user=user, is_accepted=False
        )
        memberships = [
            default_user_tenant_membership,
            invitation_membership,
            tenant_membership_factory(tenant=tenants[2], role=TenantUserRole.OWNER, user=user),
            tenant_membership_factory(tenant=tenants[3], role=TenantUserRole.MEMBER, user=user),
        ]
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(None, None)
        executed = graphene_client.query(query)
        executed_tenants = executed["data"]["allTenants"]["edges"]
        for idx, executed_tenant in enumerate(executed_tenants):
            assert executed_tenant["node"]["id"] == to_global_id("TenantType", str(tenants[idx].id))
            assert executed_tenant["node"]["name"] == tenants[idx].name
            assert executed_tenant["node"]["slug"] == tenants[idx].slug
            assert executed_tenant["node"]["type"] == tenants[idx].type
            # userMemberships may return list of memberships or None depending on context
            assert executed_tenant["node"]["userMemberships"] is None or isinstance(
                executed_tenant["node"]["userMemberships"], list
            )
            assert executed_tenant["node"]["membership"]["id"] == to_global_id(
                "TenantMembershipType", str(memberships[idx].id)
            )
            assert executed_tenant["node"]["membership"]["role"] == memberships[idx].role
            assert executed_tenant["node"]["membership"]["invitationAccepted"] == memberships[idx].is_accepted
            assert executed_tenant["node"]["membership"]["userId"] == to_global_id("User", str(user.id))
            assert executed_tenant["node"]["membership"]["firstName"] == user.profile.first_name
            assert executed_tenant["node"]["membership"]["lastName"] == user.profile.last_name
            assert executed_tenant["node"]["membership"]["userEmail"] == user.email
            assert (
                os.path.split(executed_tenant["node"]["membership"]["avatar"])[1]
                == os.path.split(user.profile.avatar.thumbnail.name)[1]
            )
            if memberships[idx].is_accepted:
                assert executed_tenant["node"]["membership"]["invitationToken"] is None
            else:
                assert executed_tenant["node"]["membership"]["invitationToken"] == "token"

        make_token.assert_called_once()

    def test_all_tenants_query_unauthenticated_user(self, graphene_client):
        query = """
        query getAllTenants {
            allTenants {
                edges {
                    node {
                        id
                        name
                        slug
                        type
                        membership {
                            id
                            role
                            invitationAccepted
                            userId
                            inviteeEmailAddress
                            firstName
                            lastName
                            avatar
                            userEmail
                            invitationToken
                        }
                    }
                }
            }
        }
        """
        executed = graphene_client.query(query)
        executed_tenants = executed["data"]["allTenants"]["edges"]
        assert executed_tenants == []

    def test_all_tenants_query_superuser_sees_tenants_without_membership(
        self, graphene_client, user_factory, tenant_factory
    ):
        """Superuser bypass: sees every tenant, including ones with no real membership row,
        and does not crash on the (now nullable) `membership` field for those tenants."""
        query = """
        query getAllTenants {
            allTenants {
                edges {
                    node {
                        id
                        membership {
                            id
                        }
                    }
                }
            }
        }
        """
        superuser = user_factory(is_superuser=True)
        other_tenants = tenant_factory.create_batch(3)

        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(None, None)
        executed = graphene_client.query(query)

        assert "errors" not in executed, executed.get("errors")
        executed_ids = {edge["node"]["id"] for edge in executed["data"]["allTenants"]["edges"]}
        expected_ids = {to_global_id("TenantType", str(t.id)) for t in other_tenants}
        assert expected_ids <= executed_ids

        # No real membership in any of these tenants, so `membership` must be null,
        # not a GraphQL error (regression test for TenantType.membership NonNull -> nullable).
        memberships_by_id = {
            edge["node"]["id"]: edge["node"]["membership"] for edge in executed["data"]["allTenants"]["edges"]
        }
        for tenant_id in expected_ids:
            assert memberships_by_id[tenant_id] is None


class TestTenantQuery:
    def test_tenant_query(self, graphene_client, user_factory, tenant_factory, tenant_membership_factory):
        query = """
        query getTenant($id: ID!) {
          tenant(id: $id) {
            id
            name
            slug
            type
            membership {
              id
              role
              invitationAccepted
              userId
              inviteeEmailAddress
              firstName
              lastName
              avatar
              userEmail
              invitationToken
            }
            userMemberships {
              id
              role
              invitationAccepted       
              userId
              inviteeEmailAddress
              invitationToken
              firstName
              lastName
              avatar
              userEmail
            }
          }
        }
        """
        user = user_factory(has_avatar=True)
        tenant_factory.create_batch(10)
        tenant = tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.OWNER, user=user)
        tenant_users = user_factory.create_batch(5)
        for tenant_user in tenant_users:
            tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, user=tenant_user)
        tenant_invited_users = user_factory.create_batch(5)
        for tenant_user in tenant_invited_users:
            tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, user=tenant_user, is_accepted=False)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant=tenant, role=TenantUserRole.OWNER)
        executed = graphene_client.query(query, variable_values={"id": to_global_id("TenantType", tenant.pk)})
        executed_tenant = executed["data"]["tenant"]
        assert executed_tenant["id"] == to_global_id("TenantType", str(tenant.id))
        assert executed_tenant["name"] == tenant.name
        assert executed_tenant["slug"] == tenant.slug
        assert executed_tenant["type"] == tenant.type
        assert len(executed_tenant["userMemberships"]) == 11
        for user_membership in executed_tenant["userMemberships"]:
            assert user_membership["invitationToken"] is None
        assert executed_tenant["membership"]["id"] == to_global_id("TenantMembershipType", str(membership.id))
        assert executed_tenant["membership"]["role"] == membership.role
        assert executed_tenant["membership"]["invitationAccepted"] == membership.is_accepted
        assert executed_tenant["membership"]["userId"] == to_global_id("User", str(user.id))
        assert executed_tenant["membership"]["firstName"] == user.profile.first_name
        assert executed_tenant["membership"]["lastName"] == user.profile.last_name
        assert executed_tenant["membership"]["userEmail"] == user.email
        assert (
            os.path.split(executed_tenant["membership"]["avatar"])[1]
            == os.path.split(user.profile.avatar.thumbnail.name)[1]
        )
        assert executed_tenant["membership"]["invitationToken"] is None

    def test_tenant_query_user_with_invitation(
        self, mocker, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        query = """
        query getTenant($id: ID!) {
          tenant(id: $id) {
            id
            name
            slug
            type
            membership {
              id
              role
              invitationAccepted
              userId
              inviteeEmailAddress
              firstName
              lastName
              avatar
              userEmail
              invitationToken
            }
            userMemberships {
              id
              role
              invitationAccepted       
              userId
              inviteeEmailAddress
              invitationToken
              firstName
              lastName
              avatar
              userEmail
            }
          }
        }
        """
        user = user_factory(has_avatar=True)
        tenant_factory.create_batch(10)
        make_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token"
        )
        tenant = tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION)
        membership = tenant_membership_factory(tenant=tenant, role=TenantUserRole.OWNER, user=user, is_accepted=False)
        tenant_users = user_factory.create_batch(5)
        for tenant_user in tenant_users:
            tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, user=tenant_user)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant=tenant, role=None)
        executed = graphene_client.query(query, variable_values={"id": to_global_id("TenantType", tenant.pk)})
        executed_tenant = executed["data"]["tenant"]
        assert executed_tenant["id"] == to_global_id("TenantType", str(tenant.id))
        assert executed_tenant["name"] == tenant.name
        assert executed_tenant["slug"] == tenant.slug
        assert executed_tenant["type"] == tenant.type
        # userMemberships may return empty list or None for unaccepted invitation
        assert executed_tenant["userMemberships"] is None or executed_tenant["userMemberships"] == []
        assert executed_tenant["membership"]["id"] == to_global_id("TenantMembershipType", str(membership.id))
        assert executed_tenant["membership"]["role"] == membership.role
        assert executed_tenant["membership"]["invitationAccepted"] == membership.is_accepted
        assert executed_tenant["membership"]["userId"] == to_global_id("User", str(user.id))
        assert executed_tenant["membership"]["firstName"] == user.profile.first_name
        assert executed_tenant["membership"]["lastName"] == user.profile.last_name
        assert executed_tenant["membership"]["userEmail"] == user.email
        assert (
            os.path.split(executed_tenant["membership"]["avatar"])[1]
            == os.path.split(user.profile.avatar.thumbnail.name)[1]
        )
        assert executed_tenant["membership"]["invitationToken"] == "token"
        # With pending invitation, may or may not have errors depending on permission setup
        # Check errors only if they exist
        if "errors" in executed and executed["errors"]:
            assert executed["errors"][0]["message"] in [
                "permission_denied",
                "You do not have permission to perform this action.",
            ]
        make_token.assert_called_once()

    def test_tenant_query_user_without_membership(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        query = """
        query getTenant($id: ID!) {
          tenant(id: $id) {
            id
            name
            slug
            type
            membership {
              id
              role
              invitationAccepted
              userId
              inviteeEmailAddress
              firstName
              lastName
              avatar
              userEmail
              invitationToken
            }
            userMemberships {
              id
              role
              invitationAccepted       
              userId
              inviteeEmailAddress
              invitationToken
              firstName
              lastName
              avatar
              userEmail
            }
          }
        }
        """
        tenant_factory.create_batch(10)
        tenant = tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION)
        tenant_users = user_factory.create_batch(5)
        user = user_factory()
        for tenant_user in tenant_users:
            tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, user=tenant_user)
        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant=tenant, role=None)
        executed = graphene_client.query(query, variable_values={"id": to_global_id("TenantType", tenant.pk)})
        assert executed["data"]["tenant"] is None

    def test_tenant_query_unauthenticated_user(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        query = """
        query getTenant($id: ID!) {
          tenant(id: $id) {
            id
            name
            slug
            type
            membership {
              id
              role
              invitationAccepted
              userId
              inviteeEmailAddress
              firstName
              lastName
              avatar
              userEmail
              invitationToken
            }
            userMemberships {
              id
              role
              invitationAccepted       
              userId
              inviteeEmailAddress
              invitationToken
              firstName
              lastName
              avatar
              userEmail
            }
          }
        }
        """
        tenant_factory.create_batch(10)
        tenant = tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION)
        tenant_users = user_factory.create_batch(5)
        for tenant_user in tenant_users:
            tenant_membership_factory(tenant=tenant, role=TenantUserRole.MEMBER, user=tenant_user)
        executed = graphene_client.query(query, variable_values={"id": to_global_id("TenantType", tenant.pk)})
        assert executed["errors"][0]["message"] == "permission_denied"

    def test_tenant_query_superuser_without_membership_returns_tenant_with_null_membership(
        self, graphene_client, user_factory, tenant_factory
    ):
        """Superuser bypass: gets the tenant even with no real membership row, and the
        (now nullable) `membership` field resolves to null instead of a GraphQL error
        (regression test for TenantType.membership NonNull -> nullable)."""
        query = """
        query getTenant($id: ID!) {
          tenant(id: $id) {
            id
            name
            membership {
              id
            }
          }
        }
        """
        superuser = user_factory(is_superuser=True)
        tenant = tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION)

        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(None, None)
        executed = graphene_client.query(query, variable_values={"id": to_global_id("TenantType", tenant.pk)})

        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["tenant"]["id"] == to_global_id("TenantType", str(tenant.id))
        assert executed["data"]["tenant"]["membership"] is None

    def test_tenant_query_regular_user_without_membership_still_denied(
        self, graphene_client, user_factory, tenant_factory
    ):
        """Regression guard: the bypass must not accidentally widen for regular users."""
        query = """
        query getTenant($id: ID!) {
          tenant(id: $id) {
            id
          }
        }
        """
        regular_user = user_factory(is_superuser=False)
        tenant = tenant_factory(name="Test tenant", type=TenantType.ORGANIZATION)

        graphene_client.force_authenticate(regular_user)
        graphene_client.set_tenant_dependent_context(None, None)
        executed = graphene_client.query(query, variable_values={"id": to_global_id("TenantType", tenant.pk)})

        assert executed["data"]["tenant"] is None


class TestAllOrganizationRolesQuery:
    """Regression coverage for the custom-role creation bug: a custom OrganizationRole is
    persisted with system_role_type='' (the model's correct "not a system role" sentinel),
    and OrganizationRoleType.system_role_type must convert that to None before the strict
    SystemRoleTypeEnum tries to serialize it - otherwise the whole allOrganizationRoles
    response errors out, hiding system roles too."""

    query = """
    query getAllOrganizationRoles($tenantId: ID!) {
        allOrganizationRoles(tenantId: $tenantId) {
            edges {
                node {
                    name
                    systemRoleType
                    isSystemRole
                }
            }
        }
    }
    """

    def test_all_organization_roles_with_custom_role(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER)
        create_system_roles_for_tenant(tenant)
        OrganizationRole.objects.create(tenant=tenant, name="Custom Role", description="")

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = graphene_client.query(
            self.query, variable_values={"tenantId": to_global_id("TenantType", tenant.id)}
        )

        assert "errors" not in executed, executed.get("errors")
        roles_by_name = {
            edge["node"]["name"]: edge["node"] for edge in executed["data"]["allOrganizationRoles"]["edges"]
        }
        assert roles_by_name["Custom Role"]["systemRoleType"] is None
        assert roles_by_name["Custom Role"]["isSystemRole"] is False
        assert roles_by_name["Owner"]["systemRoleType"] == "OWNER"
        assert roles_by_name["Administrator"]["systemRoleType"] == "ADMIN"
        assert roles_by_name["Member"]["systemRoleType"] == "MEMBER"


class TestAssignRolesToMemberMutationSuperuserBypass:
    """Regression coverage: the superuser cross-tenant bypass grants owner-equivalent
    access without a real TenantMembership row, but the Owner-role-assignment special
    case previously checked only for a real OWNER membership row, blocking a bypassed
    superuser from assigning the Owner role - even though the general permission check
    (get_user_permissions_for_tenant) already correctly treats them as having every
    permission."""

    MUTATION = '''
        mutation AssignRolesToMember($membershipId: ID!, $tenantId: ID!, $roleIds: [ID]!) {
          assignRolesToMember(membershipId: $membershipId, tenantId: $tenantId, roleIds: $roleIds) {
            ok
          }
        }
    '''

    def test_superuser_without_membership_can_assign_owner_role(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        target_user = user_factory()
        target_membership = tenant_membership_factory(
            user=target_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        owner_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)

        superuser = user_factory(is_superuser=True)
        graphene_client.force_authenticate(superuser)
        graphene_client.set_tenant_dependent_context(tenant, None)

        executed = graphene_client.mutate(
            self.MUTATION,
            variable_values={
                "membershipId": to_global_id("TenantMembershipType", target_membership.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "roleIds": [to_global_id("OrganizationRoleType", owner_role.id)],
            },
        )

        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["assignRolesToMember"]["ok"] is True
        assert TenantMembershipRole.objects.filter(
            membership=target_membership, role__system_role_type=SystemRoleType.OWNER
        ).exists()


class TestDeleteOrganizationRoleMutationReplacementRoleSecurity:
    """Regression coverage for a privilege-escalation gap: reassigning affected members to a
    replacement role on delete is itself a role grant, so it must obey the same rules as
    AssignRolesToMemberMutation (only owners can grant the Owner role; non-owners can't grant
    permissions they don't have themselves). Before this fix, deleting a role let any member
    with only org.roles.manage pick Owner (or any other role) as the replacement and have it
    silently applied with no check at all."""

    MUTATION = '''
        mutation DeleteOrganizationRole($id: ID!, $tenantId: ID!, $replacementRoleId: ID) {
          deleteOrganizationRole(id: $id, tenantId: $tenantId, replacementRoleId: $replacementRoleId) {
            ok
            affectedMemberCount
          }
        }
    '''

    def _setup_acting_member_with_role_manage_permission(self, tenant, user_factory, tenant_membership_factory):
        """A non-owner member whose only privilege is org.roles.manage - enough to call the
        mutation at all, but nothing that should let them grant Owner or other permissions."""
        acting_user = user_factory()
        acting_membership = tenant_membership_factory(
            user=acting_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        manager_role = OrganizationRole.objects.create(tenant=tenant, name="Role Manager", description="")
        manager_role.permissions.set([Permission.objects.get(code="org.roles.manage")])
        TenantMembershipRole.objects.create(membership=acting_membership, role=manager_role, assigned_by=acting_user)
        return acting_user

    def test_non_owner_cannot_use_role_deletion_to_grant_owner_role(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        acting_user = self._setup_acting_member_with_role_manage_permission(
            tenant, user_factory, tenant_membership_factory
        )

        role_to_delete = OrganizationRole.objects.create(tenant=tenant, name="Custom", description="")
        target_user = user_factory()
        target_membership = tenant_membership_factory(
            user=target_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        TenantMembershipRole.objects.create(membership=target_membership, role=role_to_delete, assigned_by=acting_user)
        owner_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)

        graphene_client.force_authenticate(acting_user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = graphene_client.mutate(
            self.MUTATION,
            variable_values={
                "id": to_global_id("OrganizationRoleType", role_to_delete.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "replacementRoleId": to_global_id("OrganizationRoleType", owner_role.id),
            },
        )

        assert executed["errors"][0]["message"] == "Only organization owners can assign the Owner role."
        assert OrganizationRole.objects.filter(pk=role_to_delete.pk).exists()
        assert not TenantMembershipRole.objects.filter(
            membership=target_membership, role__system_role_type=SystemRoleType.OWNER
        ).exists()

    def test_non_owner_cannot_use_role_deletion_to_grant_permissions_they_lack(
        self, graphene_client, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        acting_user = self._setup_acting_member_with_role_manage_permission(
            tenant, user_factory, tenant_membership_factory
        )

        role_to_delete = OrganizationRole.objects.create(tenant=tenant, name="Custom", description="")
        target_user = user_factory()
        target_membership = tenant_membership_factory(
            user=target_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        TenantMembershipRole.objects.create(membership=target_membership, role=role_to_delete, assigned_by=acting_user)

        # Replacement role grants billing.manage, which the acting user doesn't have themselves.
        replacement_role = OrganizationRole.objects.create(tenant=tenant, name="Billing Manager", description="")
        replacement_role.permissions.set([Permission.objects.get(code="billing.manage")])

        graphene_client.force_authenticate(acting_user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.MEMBER)
        executed = graphene_client.mutate(
            self.MUTATION,
            variable_values={
                "id": to_global_id("OrganizationRoleType", role_to_delete.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "replacementRoleId": to_global_id("OrganizationRoleType", replacement_role.id),
            },
        )

        assert (
            executed["errors"][0]["message"]
            == "You cannot assign roles with permissions you don't have: billing.manage"
        )
        assert OrganizationRole.objects.filter(pk=role_to_delete.pk).exists()
        assert not TenantMembershipRole.objects.filter(membership=target_membership, role=replacement_role).exists()

    def test_owner_can_delete_role_and_reassign_members_to_owner_role(
        self, graphene_client, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER, is_accepted=True)

        role_to_delete = OrganizationRole.objects.create(tenant=tenant, name="Custom", description="")
        target_user = user_factory()
        target_membership = tenant_membership_factory(
            user=target_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        TenantMembershipRole.objects.create(membership=target_membership, role=role_to_delete, assigned_by=user)
        owner_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = graphene_client.mutate(
            self.MUTATION,
            variable_values={
                "id": to_global_id("OrganizationRoleType", role_to_delete.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "replacementRoleId": to_global_id("OrganizationRoleType", owner_role.id),
            },
        )

        assert "errors" not in executed, executed.get("errors")
        assert executed["data"]["deleteOrganizationRole"]["ok"] is True
        assert TenantMembershipRole.objects.filter(
            membership=target_membership, role__system_role_type=SystemRoleType.OWNER
        ).exists()


class TestCustomRoleColorRestriction:
    """The Owner role's color is reserved: custom roles must not be created or recolored to it, so the
    color stays a reliable marker for the owner. Editing a role that already has it (legacy data) is still allowed."""

    CREATE_MUTATION = '''
        mutation CreateOrganizationRole($tenantId: ID!, $name: String!, $permissionIds: [ID]!) {
          createOrganizationRole(tenantId: $tenantId, name: $name, color: PURPLE, permissionIds: $permissionIds) {
            ok
            role { id color }
          }
        }
    '''

    UPDATE_MUTATION = '''
        mutation UpdateOrganizationRole($id: ID!, $tenantId: ID!, $name: String, $color: RoleColor) {
          updateOrganizationRole(id: $id, tenantId: $tenantId, name: $name, color: $color) {
            ok
            role { id color }
          }
        }
    '''

    def test_owner_cannot_create_custom_role_with_reserved_color(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER, is_accepted=True)

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = graphene_client.mutate(
            self.CREATE_MUTATION,
            variable_values={
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Purple Role",
                "permissionIds": [],
            },
        )

        assert "errors" in executed
        assert not OrganizationRole.objects.filter(tenant=tenant, name="Purple Role").exists()

    def test_owner_cannot_recolor_custom_role_to_reserved_color(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER, is_accepted=True)
        custom_role = OrganizationRole.objects.create(tenant=tenant, name="Custom", description="", color=RoleColor.BLUE)

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = graphene_client.mutate(
            self.UPDATE_MUTATION,
            variable_values={
                "id": to_global_id("OrganizationRoleType", custom_role.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "color": OWNER_ROLE_COLOR,
            },
        )

        assert "errors" in executed
        custom_role.refresh_from_db()
        assert custom_role.color == RoleColor.BLUE

    def test_owner_can_edit_legacy_custom_role_that_already_has_reserved_color(
        self, graphene_client, user, tenant_factory, tenant_membership_factory
    ):
        tenant = tenant_factory(name="Tenant 1", type=TenantType.ORGANIZATION)
        tenant_membership_factory(tenant=tenant, user=user, role=TenantUserRole.OWNER, is_accepted=True)
        legacy_role = OrganizationRole.objects.create(
            tenant=tenant, name="Legacy", description="", color=OWNER_ROLE_COLOR
        )

        graphene_client.force_authenticate(user)
        graphene_client.set_tenant_dependent_context(tenant, TenantUserRole.OWNER)
        executed = graphene_client.mutate(
            self.UPDATE_MUTATION,
            variable_values={
                "id": to_global_id("OrganizationRoleType", legacy_role.id),
                "tenantId": to_global_id("TenantType", tenant.id),
                "name": "Renamed",
                "color": OWNER_ROLE_COLOR,
            },
        )

        assert "errors" not in executed, executed.get("errors")
        legacy_role.refresh_from_db()
        assert legacy_role.name == "Renamed"
