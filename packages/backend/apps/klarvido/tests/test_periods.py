from datetime import date

import pytest

from ..adapters import MockDataAdapter
from ..calculations import PeriodPreset, PeriodResolver
from ..contracts import PeriodReference
from ..services import import_from_adapter


pytestmark = pytest.mark.django_db


@pytest.fixture
def demo_tenant(tenant):
    import_from_adapter(tenant=tenant, adapter=MockDataAdapter())
    return tenant


def test_latest_and_previous_month_are_resolved_from_canonical_facts(demo_tenant):
    resolver = PeriodResolver(demo_tenant)

    latest = resolver.resolve(PeriodPreset.LATEST_MONTH)
    previous = resolver.resolve(PeriodPreset.PREVIOUS_MONTH)

    assert latest.current == PeriodReference(date(2026, 6, 1), date(2026, 6, 30))
    assert latest.comparison == PeriodReference(date(2026, 5, 1), date(2026, 5, 31))
    assert previous.current == PeriodReference(date(2026, 5, 1), date(2026, 5, 31))
    assert previous.comparison == PeriodReference(date(2026, 4, 1), date(2026, 4, 30))


def test_quarter_has_previous_three_month_comparison(demo_tenant):
    selection = PeriodResolver(demo_tenant).resolve(PeriodPreset.LAST_QUARTER)

    assert selection.current == PeriodReference(date(2026, 4, 1), date(2026, 6, 30))
    assert selection.comparison == PeriodReference(date(2026, 1, 1), date(2026, 3, 31))


@pytest.mark.parametrize("preset", [PeriodPreset.HALF_YEAR, PeriodPreset.YEAR_TO_DATE])
def test_long_period_has_no_comparison_when_previous_facts_are_missing(demo_tenant, preset):
    selection = PeriodResolver(demo_tenant).resolve(preset)

    assert selection.current == PeriodReference(date(2026, 1, 1), date(2026, 6, 30))
    assert selection.comparison is None


def test_full_custom_month_uses_full_previous_calendar_month(demo_tenant):
    selection = PeriodResolver(demo_tenant).custom(date(2026, 6, 1), date(2026, 6, 30))

    assert selection.comparison == PeriodReference(date(2026, 5, 1), date(2026, 5, 31))
