from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from apps.klarvido import models
from apps.klarvido.contracts import PeriodReference, SourceReference

from .contracts import AnalysisKind, DataReadiness, ReadinessMetric, ReadinessStatus


POLICY_VERSION = "data-readiness:v1"


@dataclass(frozen=True, slots=True)
class _Requirement:
    code: str
    label: str
    unit: str
    ready: float
    limited: float
    lower_is_better: bool = False


_SOURCE_HEALTH = _Requirement("source_health", "Source import health", "ratio", 1.0, 0.5)
_VALIDATION = _Requirement("validation_coverage", "Valid invoice coverage", "ratio", 1.0, 0.8)
_FRESHNESS = _Requirement("freshness_days", "Data freshness", "days", 30.0, 90.0, lower_is_better=True)
_SALES_AVAILABLE = _Requirement("sales_data_availability", "Sales data availability", "ratio", 1.0, 1.0)
_PURCHASES_AVAILABLE = _Requirement("purchase_data_availability", "Purchase data availability", "ratio", 1.0, 1.0)
_BUYERS = _Requirement("buyer_identification_completeness", "Buyer identification", "ratio", 0.95, 0.7)
_SUPPLIERS = _Requirement("supplier_identification_completeness", "Supplier identification", "ratio", 0.95, 0.7)
_SALES_HISTORY = _Requirement("sales_history_months", "Sales history", "months", 3.0, 2.0)
_PURCHASE_HISTORY = _Requirement("purchase_history_months", "Purchase history", "months", 3.0, 2.0)
_LINE_ITEMS = _Requirement("line_item_completeness", "Invoice line completeness", "ratio", 0.95, 0.7)
_CATEGORIES = _Requirement("category_completeness", "Cost category completeness", "ratio", 0.9, 0.6)
_QUANTITIES = _Requirement("quantity_completeness", "Quantity completeness", "ratio", 0.8, 0.5)
_UNIT_PRICES = _Requirement("unit_price_completeness", "Unit price completeness", "ratio", 0.8, 0.5)
_PAYMENT_FIELDS = _Requirement("payment_field_completeness", "Payment field completeness", "ratio", 0.8, 0.5)
_BANK_DATA = _Requirement("bank_data_availability", "Bank data availability", "ratio", 1.0, 1.0)


POLICIES = {
    AnalysisKind.CUSTOMER_CONCENTRATION: (
        _SOURCE_HEALTH,
        _VALIDATION,
        _FRESHNESS,
        _SALES_AVAILABLE,
        _BUYERS,
    ),
    AnalysisKind.CUSTOMER_TREND: (
        _SOURCE_HEALTH,
        _VALIDATION,
        _FRESHNESS,
        _SALES_AVAILABLE,
        _BUYERS,
        _SALES_HISTORY,
    ),
    AnalysisKind.SUPPLIER_CONCENTRATION: (
        _SOURCE_HEALTH,
        _VALIDATION,
        _FRESHNESS,
        _PURCHASES_AVAILABLE,
        _SUPPLIERS,
    ),
    AnalysisKind.COST_STRUCTURE: (
        _SOURCE_HEALTH,
        _VALIDATION,
        _FRESHNESS,
        _PURCHASES_AVAILABLE,
        _LINE_ITEMS,
        _CATEGORIES,
    ),
    AnalysisKind.PRICE_VOLUME: (
        _SOURCE_HEALTH,
        _VALIDATION,
        _FRESHNESS,
        _PURCHASES_AVAILABLE,
        _PURCHASE_HISTORY,
        _LINE_ITEMS,
        _QUANTITIES,
        _UNIT_PRICES,
    ),
    AnalysisKind.CASH_FLOW: (_SOURCE_HEALTH, _FRESHNESS, _PAYMENT_FIELDS, _BANK_DATA),
}


class ReadinessEngine:
    def __init__(self, tenant, *, checked_at: datetime | None = None):
        self.tenant = tenant
        self.checked_at = checked_at or timezone.now()
        if self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None:
            raise ValueError("Readiness timestamp must be timezone-aware.")

    def evaluate(self, analysis: AnalysisKind, period: PeriodReference) -> DataReadiness:
        profile = self._profile(period)
        metrics = tuple(self._evaluate_requirement(requirement, profile) for requirement in POLICIES[analysis])
        status = _weakest_status(metric.status for metric in metrics)
        limitations = tuple(_limitation(metric) for metric in metrics if metric.status is not ReadinessStatus.READY)
        score = sum(_status_score(metric.status) for metric in metrics) / len(metrics)
        return DataReadiness(
            analysis=analysis,
            period=period,
            status=status,
            score=round(score, 4),
            metrics=metrics,
            limitations=limitations,
            sources=profile.sources,
            policy_version=POLICY_VERSION,
            checked_at=self.checked_at,
        )

    def _profile(self, period):
        candidates = list(
            models.Invoice.objects.filter(
                tenant=self.tenant,
                issue_date__range=(period.start_date, period.end_date),
            )
            .exclude(status=models.InvoiceStatus.CANCELLED)
            .select_related("counterparty", "source_record")
            .prefetch_related("lines")
        )
        trusted = [invoice for invoice in candidates if _is_trusted(invoice)]
        sales = [invoice for invoice in trusted if invoice.invoice_type == models.InvoiceType.SALES]
        purchases = [invoice for invoice in trusted if invoice.invoice_type == models.InvoiceType.PURCHASE]
        lines = [line for invoice in trusted for line in invoice.lines.all()]
        purchase_lines = [line for invoice in purchases for line in invoice.lines.all()]

        historical = list(
            models.Invoice.objects.filter(tenant=self.tenant, issue_date__lte=period.end_date)
            .exclude(status=models.InvoiceStatus.CANCELLED)
            .select_related("source_record")
        )
        historical = [invoice for invoice in historical if _is_trusted(invoice)]

        bank_records = list(
            models.SourceRecord.objects.filter(
                tenant=self.tenant,
                record_type="bank_transaction",
                effective_at__date__range=(period.start_date, period.end_date),
                validation_status__in=(models.ValidationStatus.VALID, models.ValidationStatus.WARNING),
            )
        )
        source_records = [invoice.source_record for invoice in trusted] + bank_records
        source_systems = {record.source_system for record in source_records}
        imports = list(
            models.DataImport.objects.filter(
                tenant=self.tenant,
                source_system__in=source_systems,
            ).order_by("-updated_at", "-created_at")
        )
        latest_import = imports[0] if imports else None
        source_health = _source_health(latest_import, bool(source_records))
        latest_data_at = _latest_data_timestamp(imports, source_records)
        freshness_days = (
            max(0, (self.checked_at.date() - latest_data_at.date()).days)
            if latest_data_at is not None
            else float("inf")
        )

        return _DataProfile(
            values={
                "source_health": source_health,
                "validation_coverage": _ratio(
                    sum(
                        invoice.source_record is not None
                        and invoice.source_record.validation_status == models.ValidationStatus.VALID
                        for invoice in candidates
                    ),
                    len(candidates),
                ),
                "freshness_days": float(freshness_days),
                "sales_data_availability": float(bool(sales)),
                "purchase_data_availability": float(bool(purchases)),
                "buyer_identification_completeness": _ratio(
                    sum(bool(invoice.counterparty.tax_identifier) for invoice in sales),
                    len(sales),
                ),
                "supplier_identification_completeness": _ratio(
                    sum(bool(invoice.counterparty.tax_identifier) for invoice in purchases),
                    len(purchases),
                ),
                "sales_history_months": float(_history_months(historical, models.InvoiceType.SALES)),
                "purchase_history_months": float(_history_months(historical, models.InvoiceType.PURCHASE)),
                "line_item_completeness": _ratio(
                    sum(bool(invoice.lines.all()) for invoice in trusted),
                    len(trusted),
                ),
                "category_completeness": _ratio(
                    sum(line.category_id is not None for line in purchase_lines),
                    len(purchase_lines),
                ),
                "quantity_completeness": _ratio(
                    sum(line.quantity is not None for line in lines),
                    len(lines),
                ),
                "unit_price_completeness": _ratio(
                    sum(line.unit_price_net is not None for line in lines),
                    len(lines),
                ),
                "payment_field_completeness": _ratio(
                    sum(invoice.due_date is not None for invoice in trusted),
                    len(trusted),
                ),
                "bank_data_availability": float(bool(bank_records)),
            },
            sources=_source_references(source_records),
        )

    def _evaluate_requirement(self, requirement, profile):
        value = profile.values[requirement.code]
        if requirement.lower_is_better:
            if value <= requirement.ready:
                status = ReadinessStatus.READY
            elif value <= requirement.limited:
                status = ReadinessStatus.LIMITED
            else:
                status = ReadinessStatus.BLOCKED
        elif value >= requirement.ready:
            status = ReadinessStatus.READY
        elif value >= requirement.limited:
            status = ReadinessStatus.LIMITED
        else:
            status = ReadinessStatus.BLOCKED
        return ReadinessMetric(
            code=requirement.code,
            label=requirement.label,
            value=value,
            unit=requirement.unit,
            status=status,
            ready_threshold=requirement.ready,
            limited_threshold=requirement.limited,
        )


@dataclass(frozen=True, slots=True)
class _DataProfile:
    values: dict[str, float]
    sources: tuple[SourceReference, ...]


def _is_trusted(invoice):
    return invoice.source_record is not None and invoice.source_record.validation_status in (
        models.ValidationStatus.VALID,
        models.ValidationStatus.WARNING,
    )


def _source_health(latest_import, has_trusted_data):
    if latest_import is None:
        return 0.0
    if latest_import.status == models.ImportStatus.COMPLETED:
        return 1.0
    if has_trusted_data:
        return 0.5
    return 0.0


def _latest_data_timestamp(imports, source_records):
    completed_timestamps = [
        item.data_as_of for item in imports if item.status == models.ImportStatus.COMPLETED and item.data_as_of
    ]
    if completed_timestamps:
        return max(completed_timestamps)
    source_timestamps = [record.effective_at for record in source_records if record.effective_at]
    return max(source_timestamps) if source_timestamps else None


def _history_months(invoices, invoice_type):
    return len(
        {
            (invoice.issue_date.year, invoice.issue_date.month)
            for invoice in invoices
            if invoice.invoice_type == invoice_type
        }
    )


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _source_references(source_records):
    records = {record.id: record for record in source_records}
    return tuple(
        SourceReference(
            source_system=record.source_system,
            external_id=record.external_id,
            source_record_id=str(record.id),
        )
        for _, record in sorted(records.items(), key=lambda item: item[1].external_id)
    )


def _weakest_status(statuses):
    order = {
        ReadinessStatus.READY: 0,
        ReadinessStatus.LIMITED: 1,
        ReadinessStatus.BLOCKED: 2,
    }
    return max(statuses, key=order.get)


def _status_score(status):
    return {
        ReadinessStatus.READY: 1.0,
        ReadinessStatus.LIMITED: 0.5,
        ReadinessStatus.BLOCKED: 0.0,
    }[status]


def _limitation(metric):
    threshold = metric.ready_threshold if metric.status is ReadinessStatus.LIMITED else metric.limited_threshold
    comparison = "at most" if metric.code == "freshness_days" else "at least"
    return f"{metric.label} is {metric.value:g} {metric.unit}; {comparison} {threshold:g} is required."
