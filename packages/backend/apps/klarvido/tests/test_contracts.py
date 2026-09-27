from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from ..contracts import AnalyticalValue, DataQuality, PeriodReference, SourceReference, ValueKind


pytestmark = pytest.mark.django_db


def build_value(**overrides):
    values = {
        "value": Decimal("1250.50"),
        "unit": "PLN",
        "period": PeriodReference(date(2026, 6, 1), date(2026, 6, 30)),
        "sources": (SourceReference("KSEF", "invoice-1", "record-1"),),
        "calculation_version": "revenue:v1",
        "calculated_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "quality": DataQuality(status="READY", score=1.0),
        "kind": ValueKind.FACT,
    }
    values.update(overrides)
    return AnalyticalValue(**values)


def test_analytical_value_carries_required_metadata():
    result = build_value()

    assert result.value == Decimal("1250.50")
    assert result.kind is ValueKind.FACT
    assert result.sources[0].source_record_id == "record-1"


def test_analytical_value_is_immutable():
    result = build_value()

    with pytest.raises(FrozenInstanceError):
        result.unit = "EUR"


def test_analytical_value_requires_a_source():
    with pytest.raises(ValueError, match="at least one source"):
        build_value(sources=())


def test_analytical_value_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_value(calculated_at=datetime(2026, 7, 1))


def test_period_rejects_reversed_dates():
    with pytest.raises(ValueError, match="cannot be before"):
        PeriodReference(date(2026, 6, 30), date(2026, 6, 1))


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_data_quality_rejects_score_outside_normalized_range(score):
    with pytest.raises(ValueError, match="between 0 and 1"):
        DataQuality(status="LIMITED", score=score)
