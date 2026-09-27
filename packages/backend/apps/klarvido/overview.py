from dataclasses import dataclass

from apps.klarvido import models
from apps.klarvido.calculations import CalculationEngine, PeriodPreset, PeriodResolver
from apps.klarvido.contracts import PeriodReference
from apps.klarvido.readiness import AnalysisKind, ReadinessEngine


@dataclass(frozen=True, slots=True)
class MonthlySummary:
    label: str
    period: PeriodReference
    summary: object


@dataclass(frozen=True, slots=True)
class PartyTrendPoint:
    label: str
    period: PeriodReference
    amount: object | None


@dataclass(frozen=True, slots=True)
class PartyOverview:
    aggregate: object
    trend: tuple[PartyTrendPoint, ...]


@dataclass(frozen=True, slots=True)
class PortfolioOverview:
    aggregate: object
    parties: tuple[PartyOverview, ...]


@dataclass(frozen=True, slots=True)
class InvoiceOverview:
    invoice: models.Invoice
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KlarvidoOverview:
    company: models.CompanyProfile | None
    preset: str
    period: PeriodReference
    comparison_period: PeriodReference | None
    financial_summary: object
    monthly_summaries: tuple[MonthlySummary, ...]
    customers: PortfolioOverview
    suppliers: PortfolioOverview
    cost_structure: object
    invoices: tuple[InvoiceOverview, ...]
    readiness: tuple[object, ...]


def build_overview(tenant, preset=PeriodPreset.HALF_YEAR):
    selection = PeriodResolver(tenant).resolve(preset)
    engine = CalculationEngine(tenant)
    periods = tuple(
        models.AccountingPeriod.objects.filter(
            tenant=tenant,
            start_date__gte=selection.current.start_date,
            end_date__lte=selection.current.end_date,
        ).order_by("start_date")
    )
    monthly_summaries = tuple(
        MonthlySummary(
            label=period.label,
            period=PeriodReference(period.start_date, period.end_date),
            summary=engine.financial_summary(PeriodReference(period.start_date, period.end_date)),
        )
        for period in periods
    )
    customer_aggregate = engine.customers(selection.current, selection.comparison)
    supplier_aggregate = engine.suppliers(selection.current, selection.comparison)
    invoices = tuple(
        InvoiceOverview(
            invoice=invoice,
            categories=tuple(
                dict.fromkeys(line.category.name if line.category else "Bez kategorii" for line in invoice.lines.all())
            ),
        )
        for invoice in _trusted_invoices(tenant, selection.current)
    )
    readiness_engine = ReadinessEngine(tenant)

    return KlarvidoOverview(
        company=models.CompanyProfile.objects.filter(tenant=tenant).first(),
        preset=preset.value,
        period=selection.current,
        comparison_period=selection.comparison,
        financial_summary=engine.financial_summary(
            selection.current,
            comparison_period=selection.comparison,
        ),
        monthly_summaries=monthly_summaries,
        customers=_portfolio_overview(engine, customer_aggregate, monthly_summaries, "customers"),
        suppliers=_portfolio_overview(engine, supplier_aggregate, monthly_summaries, "suppliers"),
        cost_structure=engine.cost_structure(selection.current),
        invoices=invoices,
        readiness=tuple(
            readiness_engine.evaluate(analysis, selection.current)
            for analysis in (
                AnalysisKind.CUSTOMER_CONCENTRATION,
                AnalysisKind.CUSTOMER_TREND,
                AnalysisKind.SUPPLIER_CONCENTRATION,
                AnalysisKind.COST_STRUCTURE,
            )
        ),
    )


def _portfolio_overview(engine, aggregate, monthly_summaries, method_name):
    monthly_values = []
    for item in monthly_summaries:
        try:
            monthly_values.append((item, getattr(engine, method_name)(item.period)))
        except ValueError:
            monthly_values.append((item, None))

    parties = []
    for party in aggregate.parties:
        points = []
        for item, portfolio in monthly_values:
            monthly_party = (
                next(
                    (entry for entry in portfolio.parties if entry.counterparty_id == party.counterparty_id),
                    None,
                )
                if portfolio
                else None
            )
            points.append(PartyTrendPoint(item.label, item.period, monthly_party.amount if monthly_party else None))
        parties.append(PartyOverview(party, tuple(points)))
    return PortfolioOverview(aggregate, tuple(parties))


def _trusted_invoices(tenant, period):
    return (
        models.Invoice.objects.filter(
            tenant=tenant,
            issue_date__range=(period.start_date, period.end_date),
            source_record__validation_status__in=(
                models.ValidationStatus.VALID,
                models.ValidationStatus.WARNING,
            ),
        )
        .exclude(status=models.InvoiceStatus.CANCELLED)
        .select_related("counterparty", "source_record")
        .prefetch_related("lines__category")
        .order_by("-issue_date", "-id")
    )
