from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from .. import models
from ..adapters import MockDataAdapter
from ..calculations import CalculationEngine, NoCanonicalFactsError, PeriodPreset, PeriodResolver
from ..contracts import AnalyticalValue, DataQuality, PeriodReference, SourceReference, ValueKind
from ..services import import_from_adapter


pytestmark = pytest.mark.django_db
CALCULATED_AT = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
JUNE = PeriodReference(date(2026, 6, 1), date(2026, 6, 30))


@pytest.fixture
def demo_tenant(tenant):
    import_from_adapter(tenant=tenant, adapter=MockDataAdapter())
    return tenant


@pytest.fixture
def engine(demo_tenant):
    return CalculationEngine(demo_tenant, calculated_at=CALCULATED_AT)


def test_financial_summary_uses_canonical_invoice_totals(engine):
    summary = engine.financial_summary(JUNE)

    assert summary.revenue.value == Decimal("201900.00")
    assert summary.costs.value == Decimal("123590.00")
    assert summary.pre_tax_result.value == Decimal("78310.00")
    assert summary.gross_margin.value == Decimal("38.7865")
    assert summary.revenue.unit == "PLN"
    assert summary.revenue.calculation_version == "revenue:v1"
    assert summary.revenue.calculated_at == CALCULATED_AT
    assert summary.revenue.kind is ValueKind.FACT
    assert summary.revenue.sources


def test_net_result_is_not_claimed_without_income_tax_source(engine):
    summary = engine.financial_summary(JUNE)

    assert summary.income_tax is None
    assert summary.net_result is None
    assert summary.net_margin is None


def test_financial_comparison_distinguishes_percent_and_percentage_points(engine):
    may = PeriodReference(date(2026, 5, 1), date(2026, 5, 31))

    summary = engine.financial_summary(JUNE, comparison_period=may)

    assert summary.revenue_change.value == Decimal("-0.5419")
    assert summary.revenue_change.unit == "%"
    assert summary.costs_change.value == Decimal("14.4246")
    assert summary.pre_tax_result_change.value == Decimal("-17.5597")
    assert summary.gross_margin_change.value == Decimal("-8.0066")
    assert summary.gross_margin_change.unit == "pp"
    assert summary.gross_margin_change.comparison_period == may
    assert summary.net_result_change is None
    assert summary.net_margin_change is None


def test_explicit_tax_estimate_produces_estimated_net_result(engine):
    tax = AnalyticalValue(
        value=Decimal("17000.00"),
        unit="PLN",
        period=JUNE,
        sources=(SourceReference("MOCK", "income-tax-2026-06"),),
        calculation_version="demo-income-tax:v1",
        calculated_at=CALCULATED_AT,
        quality=DataQuality(status="VALID", score=1.0),
        kind=ValueKind.ESTIMATE,
        limitations=("Demonstration income tax estimate.",),
    )

    summary = engine.financial_summary(JUNE, income_tax=tax)

    assert summary.net_result.value == Decimal("61310.00")
    assert summary.net_margin.value == Decimal("30.3665")
    assert summary.net_result.kind is ValueKind.ESTIMATE
    assert summary.net_result.calculation_version == "net-result:v1"


def test_net_comparison_requires_and_uses_tax_for_both_periods(engine):
    may = PeriodReference(date(2026, 5, 1), date(2026, 5, 31))
    june_tax = _tax_value(Decimal("17000.00"), JUNE, "income-tax-2026-06")
    may_tax = _tax_value(Decimal("18000.00"), may, "income-tax-2026-05")

    summary = engine.financial_summary(
        JUNE,
        income_tax=june_tax,
        comparison_period=may,
        comparison_income_tax=may_tax,
    )

    assert summary.net_result_change.value == Decimal("-20.3663")
    assert summary.net_result_change.unit == "%"
    assert summary.net_margin_change.value == Decimal("-7.5596")
    assert summary.net_margin_change.unit == "pp"
    assert summary.net_result_change.kind is ValueKind.ESTIMATE


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"value": Decimal("-1.00")}, "cannot be negative"),
        ({"unit": "EUR"}, "must use PLN"),
        (
            {"period": PeriodReference(date(2026, 5, 1), date(2026, 5, 31))},
            "period must match",
        ),
    ],
)
def test_income_tax_must_match_financial_summary_contract(engine, overrides, message):
    tax = _tax_value(Decimal("17000.00"), JUNE, "income-tax-2026-06")
    tax = AnalyticalValue(
        value=overrides.get("value", tax.value),
        unit=overrides.get("unit", tax.unit),
        period=overrides.get("period", tax.period),
        sources=tax.sources,
        calculation_version=tax.calculation_version,
        calculated_at=tax.calculated_at,
        quality=tax.quality,
        kind=tax.kind,
        limitations=tax.limitations,
    )

    with pytest.raises(ValueError, match=message):
        engine.financial_summary(JUNE, income_tax=tax)


def test_relative_change_is_unknown_when_comparison_value_is_zero(engine, demo_tenant):
    may = PeriodReference(date(2026, 5, 1), date(2026, 5, 31))
    models.Invoice.objects.filter(
        tenant=demo_tenant,
        invoice_type=models.InvoiceType.SALES,
        issue_date__range=(may.start_date, may.end_date),
    ).update(net_amount=Decimal("0.00"), tax_amount=Decimal("0.00"), gross_amount=Decimal("0.00"))

    summary = engine.financial_summary(JUNE, comparison_period=may)

    assert summary.revenue_change is None


def test_summary_requires_trusted_sales_and_purchase_facts(engine):
    empty_period = PeriodReference(date(2025, 1, 1), date(2025, 1, 31))

    with pytest.raises(NoCanonicalFactsError, match="No trusted sales invoices"):
        engine.financial_summary(empty_period)


def test_customer_portfolio_calculates_share_change_and_concentration(engine, demo_tenant):
    selection = PeriodResolver(demo_tenant).resolve(PeriodPreset.LATEST_MONTH)
    portfolio = engine.customers(selection.current, selection.comparison)

    assert portfolio.total.value == Decimal("201900.00")
    assert portfolio.active_count.value == 12
    assert portfolio.active_count.calculation_version == "active-counterparties:v1"
    assert portfolio.largest_party.name == "MebloDom Sieć Sklepów"
    assert portfolio.largest_party.amount.value == Decimal("31000.00")
    assert portfolio.largest_party.percentage_change.value == Decimal("-27.9070")
    assert portfolio.largest_party.percentage_change.comparison_period == selection.comparison
    assert portfolio.largest_party.invoice_count.value == 3
    assert portfolio.top_three_concentration.value == Decimal("43.5859")
    assert sum((party.share.value for party in portfolio.parties), Decimal("0")) == Decimal("100.0000")


def test_supplier_portfolio_uses_purchase_invoices(engine, demo_tenant):
    selection = PeriodResolver(demo_tenant).resolve(PeriodPreset.LATEST_MONTH)
    portfolio = engine.suppliers(selection.current, selection.comparison)

    assert portfolio.total.value == Decimal("123590.00")
    assert portfolio.active_count.value == 11
    assert portfolio.largest_party.name == "DrewnoPol"
    assert portfolio.top_three_concentration.value == Decimal("46.5248")


def test_cost_structure_reconciles_to_total_purchase_invoices(engine):
    structure = engine.cost_structure(JUNE)
    categories = {item.category_code: item for item in structure.categories}

    assert structure.total.value == Decimal("123590.00")
    assert sum((item.amount.value for item in structure.categories), Decimal("0")) == structure.total.value
    assert categories["production-materials"].amount.value == Decimal("52000.00")
    assert categories[None].amount.value == Decimal("22000.00")
    assert categories[None].category_name == "Uncategorized"


def test_invalid_source_invoice_is_excluded_and_quality_is_lowered(engine, demo_tenant):
    invoice = models.Invoice.objects.filter(
        tenant=demo_tenant,
        invoice_type=models.InvoiceType.SALES,
        issue_date__range=(JUNE.start_date, JUNE.end_date),
    ).first()
    excluded_amount = invoice.net_amount
    invoice.source_record.validation_status = models.ValidationStatus.INVALID
    invoice.source_record.save()

    revenue = engine.financial_summary(JUNE).revenue

    assert revenue.value == Decimal("201900.00") - excluded_amount
    assert revenue.quality.status == "WARNING"
    assert revenue.quality.score < 1
    assert "excluded" in revenue.limitations[0]


def test_calculation_is_scoped_to_tenant(engine, tenant_factory):
    foreign_tenant = tenant_factory()
    import_from_adapter(tenant=foreign_tenant, adapter=MockDataAdapter())
    foreign_invoice = models.Invoice.objects.filter(
        tenant=foreign_tenant,
        invoice_type=models.InvoiceType.SALES,
        issue_date__range=(JUNE.start_date, JUNE.end_date),
    ).first()
    foreign_invoice.net_amount += Decimal("1000.00")
    foreign_invoice.gross_amount += Decimal("1000.00")
    foreign_invoice.save()

    assert engine.financial_summary(JUNE).revenue.value == Decimal("201900.00")


def _tax_value(value, period, external_id):
    return AnalyticalValue(
        value=value,
        unit="PLN",
        period=period,
        sources=(SourceReference("MOCK", external_id),),
        calculation_version="demo-income-tax:v1",
        calculated_at=CALCULATED_AT,
        quality=DataQuality(status="VALID", score=1.0),
        kind=ValueKind.ESTIMATE,
        limitations=("Demonstration income tax estimate.",),
    )
