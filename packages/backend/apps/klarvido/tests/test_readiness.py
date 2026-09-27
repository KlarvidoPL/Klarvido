from datetime import date, datetime, timezone

import pytest

from .. import models
from ..adapters import MockDataAdapter
from ..contracts import PeriodReference
from ..readiness import (
    AnalysisKind,
    DiagnosisStrength,
    ReadinessEngine,
    ReadinessGateError,
    ReadinessStatus,
)
from ..services import import_from_adapter


pytestmark = pytest.mark.django_db
CHECKED_AT = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
JUNE = PeriodReference(date(2026, 6, 1), date(2026, 6, 30))


@pytest.fixture
def demo_tenant(tenant):
    import_from_adapter(tenant=tenant, adapter=MockDataAdapter())
    return tenant


@pytest.fixture
def engine(demo_tenant):
    return ReadinessEngine(demo_tenant, checked_at=CHECKED_AT)


def test_demo_data_is_ready_for_customer_trend(engine):
    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)
    metrics = {metric.code: metric for metric in readiness.metrics}

    assert readiness.status is ReadinessStatus.READY
    assert readiness.score == 1.0
    assert readiness.policy_version == "data-readiness:v1"
    assert readiness.checked_at == CHECKED_AT
    assert metrics["validation_coverage"].value == 1.0
    assert metrics["buyer_identification_completeness"].value == 1.0
    assert metrics["sales_history_months"].value == 6.0
    assert metrics["freshness_days"].value == 1.0
    assert readiness.sources


def test_readiness_rejects_naive_check_timestamp(demo_tenant):
    with pytest.raises(ValueError, match="timezone-aware"):
        ReadinessEngine(demo_tenant, checked_at=datetime(2026, 7, 1, 8, 0))


def test_demo_cost_structure_uses_calculated_category_completeness(engine):
    readiness = engine.evaluate(AnalysisKind.COST_STRUCTURE, JUNE)
    metrics = {metric.code: metric for metric in readiness.metrics}

    assert readiness.status is ReadinessStatus.READY
    assert 0.9 <= metrics["category_completeness"].value < 1.0
    assert metrics["line_item_completeness"].value == 1.0


@pytest.mark.parametrize("analysis", [AnalysisKind.PRICE_VOLUME, AnalysisKind.CASH_FLOW])
def test_demo_data_blocks_analyses_that_need_unavailable_fields(engine, analysis):
    readiness = engine.evaluate(analysis, JUNE)

    assert readiness.status is ReadinessStatus.BLOCKED
    assert readiness.maximum_diagnosis_strength is None
    assert readiness.limitations


def test_invalid_source_record_limits_otherwise_ready_analysis(engine, demo_tenant):
    source_record = models.SourceRecord.objects.filter(
        tenant=demo_tenant,
        record_type="invoice",
        invoice__issue_date__range=(JUNE.start_date, JUNE.end_date),
    ).first()
    source_record.validation_status = models.ValidationStatus.INVALID
    source_record.save()

    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)

    assert readiness.status is ReadinessStatus.LIMITED
    assert readiness.maximum_diagnosis_strength is DiagnosisStrength.INDICATIVE
    assert any("Valid invoice coverage" in limitation for limitation in readiness.limitations)


def test_source_warning_limits_readiness_without_discarding_fact(engine, demo_tenant):
    source_record = models.SourceRecord.objects.filter(
        tenant=demo_tenant,
        record_type="invoice",
        invoice__issue_date__range=(JUNE.start_date, JUNE.end_date),
    ).first()
    source_record.validation_status = models.ValidationStatus.WARNING
    source_record.save()

    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)

    assert readiness.status is ReadinessStatus.LIMITED
    assert any(source.source_record_id == str(source_record.id) for source in readiness.sources)


def test_cancelled_invoice_does_not_reduce_validation_coverage(engine, demo_tenant):
    invoice = models.Invoice.objects.filter(
        tenant=demo_tenant,
        issue_date__range=(JUNE.start_date, JUNE.end_date),
    ).first()
    invoice.status = models.InvoiceStatus.CANCELLED
    invoice.save()
    invoice.source_record.validation_status = models.ValidationStatus.INVALID
    invoice.source_record.save()

    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)
    metrics = {metric.code: metric for metric in readiness.metrics}

    assert readiness.status is ReadinessStatus.READY
    assert metrics["validation_coverage"].value == 1.0


def test_missing_buyer_identifiers_block_customer_analysis(engine, demo_tenant):
    models.Counterparty.objects.filter(tenant=demo_tenant, is_customer=True).update(tax_identifier="")

    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)
    metrics = {metric.code: metric for metric in readiness.metrics}

    assert readiness.status is ReadinessStatus.BLOCKED
    assert metrics["buyer_identification_completeness"].status is ReadinessStatus.BLOCKED


def test_stale_data_lowers_readiness(engine, demo_tenant):
    stale_engine = ReadinessEngine(
        demo_tenant,
        checked_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )

    readiness = stale_engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)

    assert readiness.status is ReadinessStatus.LIMITED
    assert any("Data freshness" in limitation for limitation in readiness.limitations)


def test_failed_refresh_keeps_facts_but_limits_readiness(engine, demo_tenant, data_import_factory):
    data_import_factory(
        tenant=demo_tenant,
        source_system=models.SourceSystem.MOCK,
        external_reference="failed-refresh",
        schema_version="1",
        status=models.ImportStatus.FAILED,
    )

    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)
    metrics = {metric.code: metric for metric in readiness.metrics}

    assert readiness.status is ReadinessStatus.LIMITED
    assert metrics["source_health"].value == 0.5
    assert readiness.sources


def test_readiness_is_tenant_scoped(demo_tenant, tenant_factory):
    empty_tenant = tenant_factory()

    readiness = ReadinessEngine(empty_tenant, checked_at=CHECKED_AT).evaluate(
        AnalysisKind.CUSTOMER_TREND,
        JUNE,
    )

    assert readiness.status is ReadinessStatus.BLOCKED
    assert readiness.sources == ()


def test_gate_prevents_diagnosis_stronger_than_readiness(engine, demo_tenant):
    ready = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)
    ready.ensure_diagnosis_allowed(DiagnosisStrength.CONFIRMED)

    invoice_sources = models.SourceRecord.objects.filter(
        tenant=demo_tenant,
        record_type="invoice",
        invoice__issue_date__range=(JUNE.start_date, JUNE.end_date),
    )
    invoice_sources.filter(pk=invoice_sources.first().pk).update(validation_status=models.ValidationStatus.INVALID)
    limited = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)
    limited.ensure_diagnosis_allowed(DiagnosisStrength.INDICATIVE)

    with pytest.raises(ReadinessGateError, match="confirmed diagnosis"):
        limited.ensure_diagnosis_allowed(DiagnosisStrength.CONFIRMED)


def test_gate_blocks_any_diagnosis_when_readiness_is_blocked(demo_tenant):
    empty_period = PeriodReference(date(2025, 1, 1), date(2025, 1, 31))
    blocked = ReadinessEngine(demo_tenant, checked_at=CHECKED_AT).evaluate(
        AnalysisKind.CUSTOMER_TREND,
        empty_period,
    )

    with pytest.raises(ReadinessGateError, match="indicative diagnosis"):
        blocked.ensure_diagnosis_allowed(DiagnosisStrength.INDICATIVE)


def test_readiness_converts_to_analytical_quality(engine):
    readiness = engine.evaluate(AnalysisKind.CUSTOMER_TREND, JUNE)

    quality = readiness.as_data_quality()

    assert quality.status == "READY"
    assert quality.score == 1.0
    assert quality.limitations == ()
