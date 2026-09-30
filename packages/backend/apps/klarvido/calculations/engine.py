from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.klarvido import models
from apps.klarvido.contracts import (
    AnalyticalValue,
    DataQuality,
    PeriodReference,
    SourceReference,
    ValueKind,
)

from .contracts import CategoryAggregate, CostStructure, FinancialSummary, PartyAggregate, PortfolioAggregate


MONEY_UNIT = "PLN"
PERCENT_UNIT = "%"
PERCENTAGE_POINT_UNIT = "pp"
MONEY_ZERO = Decimal("0.00")
PERCENT_PRECISION = Decimal("0.0001")


class NoCanonicalFactsError(ValueError):
    pass


class CalculationEngine:
    def __init__(self, tenant, *, calculated_at: datetime | None = None):
        self.tenant = tenant
        self.calculated_at = calculated_at or timezone.now()

    def financial_summary(
        self,
        period: PeriodReference,
        *,
        income_tax: AnalyticalValue[Decimal] | None = None,
        comparison_period: PeriodReference | None = None,
        comparison_income_tax: AnalyticalValue[Decimal] | None = None,
    ) -> FinancialSummary:
        sales = self._fact_set(models.InvoiceType.SALES, period)
        purchases = self._fact_set(models.InvoiceType.PURCHASE, period)
        revenue_amount = _sum_invoices(sales.invoices)
        cost_amount = _sum_invoices(purchases.invoices)
        all_invoices = sales.invoices + purchases.invoices

        revenue = self._value(revenue_amount, MONEY_UNIT, period, sales, "revenue:v1")
        costs = self._value(cost_amount, MONEY_UNIT, period, purchases, "costs:v1")
        pre_tax_amount = revenue_amount - cost_amount
        combined = _combine_fact_sets(sales, purchases)
        pre_tax_result = self._value(
            pre_tax_amount,
            MONEY_UNIT,
            period,
            combined,
            "pre-tax-result:v1",
        )
        gross_margin = self._value(
            _percentage(pre_tax_amount, revenue_amount),
            PERCENT_UNIT,
            period,
            combined,
            "gross-margin:v1",
        )

        net_result = None
        net_margin = None
        if income_tax is not None:
            self._validate_tax_input(income_tax, period)
            net_amount = pre_tax_amount - income_tax.value
            net_quality = _merge_quality(combined.quality, income_tax.quality)
            net_result = self._derived_value(
                value=net_amount,
                unit=MONEY_UNIT,
                period=period,
                sources=_merge_sources(self._sources(all_invoices), income_tax.sources),
                quality=net_quality,
                kind=_strongest_kind(ValueKind.FACT, income_tax.kind),
                version="net-result:v1",
                limitations=tuple(dict.fromkeys(net_quality.limitations + income_tax.limitations)),
            )
            net_margin = self._derived_value(
                value=_percentage(net_amount, revenue_amount),
                unit=PERCENT_UNIT,
                period=period,
                sources=net_result.sources,
                quality=net_result.quality,
                kind=net_result.kind,
                version="net-margin:v1",
                limitations=net_result.limitations,
            )

        summary = FinancialSummary(
            revenue=revenue,
            costs=costs,
            pre_tax_result=pre_tax_result,
            gross_margin=gross_margin,
            income_tax=income_tax,
            net_result=net_result,
            net_margin=net_margin,
        )
        if comparison_period is None:
            return summary

        comparison = self.financial_summary(
            comparison_period,
            income_tax=comparison_income_tax,
        )
        return replace(
            summary,
            revenue_change=self._relative_change(
                summary.revenue,
                comparison.revenue,
                "revenue-change:v1",
            ),
            costs_change=self._relative_change(
                summary.costs,
                comparison.costs,
                "costs-change:v1",
            ),
            pre_tax_result_change=self._relative_change(
                summary.pre_tax_result,
                comparison.pre_tax_result,
                "pre-tax-result-change:v1",
            ),
            gross_margin_change=self._percentage_point_change(
                summary.gross_margin,
                comparison.gross_margin,
                "gross-margin-change:v1",
            ),
            net_result_change=(
                self._relative_change(
                    summary.net_result,
                    comparison.net_result,
                    "net-result-change:v1",
                )
                if summary.net_result is not None and comparison.net_result is not None
                else None
            ),
            net_margin_change=(
                self._percentage_point_change(
                    summary.net_margin,
                    comparison.net_margin,
                    "net-margin-change:v1",
                )
                if summary.net_margin is not None and comparison.net_margin is not None
                else None
            ),
        )

    def customers(
        self,
        period: PeriodReference,
        comparison: PeriodReference | None = None,
    ) -> PortfolioAggregate:
        return self._portfolio(models.InvoiceType.SALES, period, comparison)

    def suppliers(
        self,
        period: PeriodReference,
        comparison: PeriodReference | None = None,
    ) -> PortfolioAggregate:
        return self._portfolio(models.InvoiceType.PURCHASE, period, comparison)

    def cost_structure(self, period: PeriodReference) -> CostStructure:
        purchases = self._fact_set(models.InvoiceType.PURCHASE, period)
        total_amount = _sum_invoices(purchases.invoices)
        grouped_amounts = defaultdict(lambda: MONEY_ZERO)
        grouped_invoices = defaultdict(list)

        for invoice in purchases.invoices:
            line_total = MONEY_ZERO
            for line in invoice.lines.all():
                key = (line.category.code, line.category.name) if line.category else (None, "Uncategorized")
                grouped_amounts[key] += line.net_amount
                grouped_invoices[key].append(invoice)
                line_total += line.net_amount
            difference = invoice.net_amount - line_total
            if difference:
                key = (None, "Uncategorized")
                grouped_amounts[key] += difference
                grouped_invoices[key].append(invoice)

        categories = []
        for (code, name), amount in sorted(grouped_amounts.items(), key=lambda item: item[1], reverse=True):
            facts = _fact_set_from_invoices(grouped_invoices[(code, name)], purchases.quality)
            categories.append(
                CategoryAggregate(
                    category_code=code,
                    category_name=name,
                    amount=self._value(amount, MONEY_UNIT, period, facts, "cost-category-amount:v1"),
                    share=self._value(
                        _percentage(amount, total_amount),
                        PERCENT_UNIT,
                        period,
                        purchases,
                        "cost-category-share:v1",
                    ),
                )
            )

        return CostStructure(
            total=self._value(total_amount, MONEY_UNIT, period, purchases, "cost-structure-total:v1"),
            categories=tuple(categories),
        )

    def _portfolio(self, invoice_type, period, comparison):
        current = self._fact_set(invoice_type, period)
        previous = self._optional_fact_set(invoice_type, comparison) if comparison else None
        current_by_party = _group_by_counterparty(current.invoices)
        previous_by_party = _group_by_counterparty(previous.invoices) if previous else {}
        total_amount = _sum_invoices(current.invoices)
        parties = []

        for counterparty_id, invoices in current_by_party.items():
            counterparty = invoices[0].counterparty
            amount = _sum_invoices(invoices)
            party_facts = _fact_set_from_invoices(invoices, current.quality)
            previous_invoices = previous_by_party.get(counterparty_id, [])
            change = None
            if previous_invoices:
                previous_amount = _sum_invoices(previous_invoices)
                percentage_change = _percentage_change(amount, previous_amount)
                if percentage_change is not None:
                    comparison_facts = _fact_set_from_invoices(
                        invoices + previous_invoices,
                        _merge_quality(current.quality, previous.quality),
                    )
                    change = self._value(
                        percentage_change,
                        PERCENT_UNIT,
                        period,
                        comparison_facts,
                        "counterparty-percentage-change:v1",
                        comparison_period=comparison,
                    )
            parties.append(
                PartyAggregate(
                    counterparty_id=str(counterparty.id),
                    name=counterparty.name,
                    tax_identifier=counterparty.tax_identifier,
                    amount=self._value(
                        amount,
                        MONEY_UNIT,
                        period,
                        party_facts,
                        "counterparty-amount:v1",
                    ),
                    share=self._value(
                        _percentage(amount, total_amount),
                        PERCENT_UNIT,
                        period,
                        current,
                        "counterparty-share:v1",
                    ),
                    percentage_change=change,
                    invoice_count=self._value(
                        len(invoices),
                        "count",
                        period,
                        party_facts,
                        "counterparty-invoice-count:v1",
                    ),
                )
            )

        parties.sort(key=lambda item: item.amount.value, reverse=True)
        top_three_amount = sum((item.amount.value for item in parties[:3]), MONEY_ZERO)
        concentration = self._value(
            _percentage(top_three_amount, total_amount),
            PERCENT_UNIT,
            period,
            current,
            "top-three-concentration:v1",
        )
        return PortfolioAggregate(
            invoice_type=invoice_type,
            total=self._value(total_amount, MONEY_UNIT, period, current, "portfolio-total:v1"),
            parties=tuple(parties),
            top_three_concentration=concentration,
            active_count=self._value(
                len(parties),
                "count",
                period,
                current,
                "active-counterparties:v1",
            ),
            largest_party=parties[0],
        )

    def _fact_set(self, invoice_type, period):
        facts = self._optional_fact_set(invoice_type, period)
        if facts is None:
            raise NoCanonicalFactsError(
                f"No trusted {invoice_type.lower()} invoices for {period.start_date} to {period.end_date}."
            )
        return facts

    def _optional_fact_set(self, invoice_type, period):
        if period is None:
            return None
        candidates = list(
            models.Invoice.objects.filter(
                tenant=self.tenant,
                invoice_type=invoice_type,
                issue_date__range=(period.start_date, period.end_date),
            )
            .exclude(status=models.InvoiceStatus.CANCELLED)
            .select_related("counterparty", "source_record")
            .prefetch_related("lines__category")
        )
        trusted = [
            invoice
            for invoice in candidates
            if invoice.source_record
            and invoice.source_record.validation_status
            in (models.ValidationStatus.VALID, models.ValidationStatus.WARNING)
        ]
        if not trusted:
            return None

        warning_count = sum(
            invoice.source_record.validation_status == models.ValidationStatus.WARNING for invoice in trusted
        )
        excluded_count = len(candidates) - len(trusted)
        limitations = []
        if warning_count:
            limitations.append(f"{warning_count} source records contain validation warnings.")
        if excluded_count:
            limitations.append(f"{excluded_count} invoices without trusted source metadata were excluded.")
        quality = DataQuality(
            status="WARNING" if limitations else "VALID",
            score=len(trusted) / len(candidates),
            limitations=tuple(limitations),
        )
        return _FactSet(tuple(trusted), quality)

    def _value(self, value, unit, period, facts, version, *, comparison_period=None):
        return self._derived_value(
            value=value,
            unit=unit,
            period=period,
            sources=self._sources(facts.invoices),
            quality=facts.quality,
            kind=ValueKind.FACT,
            version=version,
            limitations=facts.quality.limitations,
            comparison_period=comparison_period,
        )

    def _derived_value(
        self,
        *,
        value,
        unit,
        period,
        sources,
        quality,
        kind,
        version,
        limitations=(),
        comparison_period=None,
    ):
        return AnalyticalValue(
            value=value,
            unit=unit,
            period=period,
            sources=sources,
            calculation_version=version,
            calculated_at=self.calculated_at,
            quality=quality,
            kind=kind,
            limitations=tuple(limitations),
            comparison_period=comparison_period,
        )

    def _sources(self, invoices):
        records = {invoice.source_record_id: invoice.source_record for invoice in invoices}
        return tuple(
            SourceReference(
                source_system=record.source_system,
                external_id=record.external_id,
                source_record_id=str(record.id),
            )
            for _, record in sorted(records.items(), key=lambda item: item[1].external_id)
        )

    def _validate_tax_input(self, income_tax, period):
        if income_tax.value is None:
            raise ValueError("Income tax value cannot be empty.")
        if income_tax.value < 0:
            raise ValueError("Income tax cannot be negative.")
        if income_tax.unit != MONEY_UNIT:
            raise ValueError("Income tax must use PLN.")
        if income_tax.period != period:
            raise ValueError("Income tax period must match the financial summary period.")

    def _relative_change(self, current, previous, version):
        value = _percentage_change(current.value, previous.value)
        if value is None:
            return None
        return self._comparison_value(value, PERCENT_UNIT, current, previous, version)

    def _percentage_point_change(self, current, previous, version):
        value = (current.value - previous.value).quantize(
            PERCENT_PRECISION,
            rounding=ROUND_HALF_UP,
        )
        return self._comparison_value(
            value,
            PERCENTAGE_POINT_UNIT,
            current,
            previous,
            version,
        )

    def _comparison_value(self, value, unit, current, previous, version):
        quality = _merge_quality(current.quality, previous.quality)
        return self._derived_value(
            value=value,
            unit=unit,
            period=current.period,
            comparison_period=previous.period,
            sources=_merge_sources(current.sources, previous.sources),
            quality=quality,
            kind=_strongest_kind(current.kind, previous.kind),
            version=version,
            limitations=quality.limitations,
        )


class _FactSet:
    def __init__(self, invoices, quality):
        self.invoices = tuple(invoices)
        self.quality = quality


def _fact_set_from_invoices(invoices, quality):
    unique = {invoice.id: invoice for invoice in invoices}
    return _FactSet(tuple(unique.values()), quality)


def _combine_fact_sets(*fact_sets):
    invoices = []
    quality = fact_sets[0].quality
    for fact_set in fact_sets:
        invoices.extend(fact_set.invoices)
    for fact_set in fact_sets[1:]:
        quality = _merge_quality(quality, fact_set.quality)
    return _fact_set_from_invoices(invoices, quality)


def _group_by_counterparty(invoices):
    grouped = defaultdict(list)
    for invoice in invoices:
        grouped[invoice.counterparty_id].append(invoice)
    return grouped


def _sum_invoices(invoices):
    return sum((invoice.net_amount for invoice in invoices), MONEY_ZERO)


def _percentage(numerator, denominator):
    if denominator == 0:
        return Decimal("0.0000")
    return (numerator / denominator * Decimal("100")).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)


def _percentage_change(current, previous):
    if previous == 0:
        return None
    return ((current - previous) / abs(previous) * Decimal("100")).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _merge_sources(*source_groups):
    sources = {}
    for group in source_groups:
        for source in group:
            key = source.source_record_id or f"{source.source_system}:{source.external_id}"
            sources[key] = source
    return tuple(sorted(sources.values(), key=lambda item: (item.source_system, item.external_id)))


def _merge_quality(first, second):
    limitations = tuple(dict.fromkeys(first.limitations + second.limitations))
    scores = [score for score in (first.score, second.score) if score is not None]
    status = "VALID" if first.status == second.status == "VALID" and not limitations else "WARNING"
    return DataQuality(status=status, score=min(scores) if scores else None, limitations=limitations)


def _strongest_kind(first, second):
    order = {
        ValueKind.FACT: 0,
        ValueKind.ESTIMATE: 1,
        ValueKind.SIMULATION: 2,
    }
    return max((first, second), key=order.get)
