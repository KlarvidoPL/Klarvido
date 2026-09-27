from decimal import Decimal

import pytest
from graphql_relay import to_global_id

from apps.multitenancy.constants import TenantType, TenantUserRole

from ..adapters import MockDataAdapter
from ..calculations import PeriodPreset
from ..overview import build_overview
from ..services import import_from_adapter


pytestmark = pytest.mark.django_db


@pytest.fixture
def demo_tenant(tenant):
    import_from_adapter(tenant=tenant, adapter=MockDataAdapter())
    return tenant


def test_overview_uses_canonical_calculations_and_source_documents(demo_tenant):
    overview = build_overview(demo_tenant, PeriodPreset.HALF_YEAR)

    assert overview.financial_summary.revenue.value == Decimal("1215800.00")
    assert overview.financial_summary.costs.value == Decimal("614640.00")
    assert len(overview.monthly_summaries) == 6
    assert len(overview.invoices) == 209
    assert len(overview.customers.parties) == 12
    assert len(overview.suppliers.parties) == 11
    assert all(invoice.invoice.tenant_id == demo_tenant.id for invoice in overview.invoices)
    assert all(item.summary.revenue.sources for item in overview.monthly_summaries)


def test_graphql_overview_exposes_values_metadata_and_drill_down(
    graphene_client,
    demo_tenant,
    tenant_membership_factory,
    user,
):
    tenant_membership_factory(tenant=demo_tenant, user=user, role=TenantUserRole.OWNER)
    graphene_client.set_tenant_dependent_context(demo_tenant, TenantUserRole.OWNER)
    graphene_client.force_authenticate(user)

    executed = graphene_client.query(
        """
        query($tenantId: ID!) {
          klarvidoOverview(tenantId: $tenantId, preset: "latest_month") {
            period { startDate endDate }
            financialSummary {
              revenue {
                value
                unit
                kind
                calculationVersion
                quality { status score }
                sources { sourceSystem externalId sourceRecordId }
              }
              preTaxResult { value unit }
              grossMargin { value unit }
            }
            customers { activeCount { value } parties { name trend { label amount { value } } } }
            invoices { documentNumber counterpartyName sourceSystem sourceExternalId qualityStatus }
          }
        }
        """,
        variable_values={"tenantId": to_global_id("TenantType", demo_tenant.id)},
    )

    assert "errors" not in executed
    overview = executed["data"]["klarvidoOverview"]
    assert overview["period"] == {"startDate": "2026-06-01", "endDate": "2026-06-30"}
    assert overview["financialSummary"]["revenue"]["value"] == "201900.00"
    assert overview["financialSummary"]["revenue"]["unit"] == "PLN"
    assert overview["financialSummary"]["revenue"]["kind"] == "fact"
    assert overview["financialSummary"]["revenue"]["sources"]
    assert overview["financialSummary"]["preTaxResult"]["value"] == "78310.00"
    assert overview["customers"]["activeCount"]["value"] == "12"
    assert len(overview["invoices"]) == 36
    assert all(item["sourceSystem"] == "MOCK" for item in overview["invoices"])


def test_graphql_overview_rejects_a_tenant_id_outside_context(
    graphene_client,
    demo_tenant,
    tenant_factory,
    tenant_membership_factory,
    user,
):
    foreign_tenant = tenant_factory(name="Foreign", type=TenantType.ORGANIZATION)
    import_from_adapter(tenant=foreign_tenant, adapter=MockDataAdapter())
    tenant_membership_factory(tenant=demo_tenant, user=user, role=TenantUserRole.OWNER)
    graphene_client.set_tenant_dependent_context(demo_tenant, TenantUserRole.OWNER)
    graphene_client.force_authenticate(user)

    executed = graphene_client.query(
        """
        query($tenantId: ID!) {
          klarvidoOverview(tenantId: $tenantId) { preset }
        }
        """,
        variable_values={"tenantId": to_global_id("TenantType", foreign_tenant.id)},
    )

    assert executed["data"]["klarvidoOverview"] is None
    assert executed["errors"][0]["message"] == ("The requested tenant does not match the authenticated tenant context.")


def test_graphql_overview_requires_tenant_membership(graphene_client, demo_tenant, user):
    graphene_client.set_tenant_dependent_context(demo_tenant, None)
    graphene_client.force_authenticate(user)

    executed = graphene_client.query(
        """
        query($tenantId: ID!) {
          klarvidoOverview(tenantId: $tenantId) { preset }
        }
        """,
        variable_values={"tenantId": to_global_id("TenantType", demo_tenant.id)},
    )

    assert executed["errors"][0]["message"] == "permission_denied"


def test_graphql_overview_uses_half_year_as_the_default_preset(
    graphene_client,
    demo_tenant,
    tenant_membership_factory,
    user,
):
    tenant_membership_factory(tenant=demo_tenant, user=user, role=TenantUserRole.OWNER)
    graphene_client.set_tenant_dependent_context(demo_tenant, TenantUserRole.OWNER)
    graphene_client.force_authenticate(user)

    executed = graphene_client.query(
        """
        query($tenantId: ID!) {
          klarvidoOverview(tenantId: $tenantId) {
            preset
            period { startDate endDate }
            invoices { id }
          }
        }
        """,
        variable_values={"tenantId": to_global_id("TenantType", demo_tenant.id)},
    )

    assert "errors" not in executed
    assert executed["data"]["klarvidoOverview"]["preset"] == "half_year"
    assert executed["data"]["klarvidoOverview"]["period"] == {
        "startDate": "2026-01-01",
        "endDate": "2026-06-30",
    }
    assert len(executed["data"]["klarvidoOverview"]["invoices"]) == 209


def test_graphql_overview_rejects_an_unknown_period_preset(
    graphene_client,
    demo_tenant,
    tenant_membership_factory,
    user,
):
    tenant_membership_factory(tenant=demo_tenant, user=user, role=TenantUserRole.OWNER)
    graphene_client.set_tenant_dependent_context(demo_tenant, TenantUserRole.OWNER)
    graphene_client.force_authenticate(user)

    executed = graphene_client.query(
        """
        query($tenantId: ID!) {
          klarvidoOverview(tenantId: $tenantId, preset: "unsupported") { preset }
        }
        """,
        variable_values={"tenantId": to_global_id("TenantType", demo_tenant.id)},
    )

    assert executed["data"]["klarvidoOverview"] is None
    assert executed["errors"][0]["message"] == "Unsupported Klarvido period preset."
