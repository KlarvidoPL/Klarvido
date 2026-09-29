import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from django.db.models import Max, Min, Q

from apps.klarvido import models
from apps.klarvido.contracts import PeriodReference


class PeriodPreset(StrEnum):
    LATEST_MONTH = "latest_month"
    PREVIOUS_MONTH = "previous_month"
    LAST_QUARTER = "last_quarter"
    HALF_YEAR = "half_year"
    YEAR_TO_DATE = "year_to_date"


@dataclass(frozen=True, slots=True)
class PeriodSelection:
    current: PeriodReference
    comparison: PeriodReference | None


class PeriodResolver:
    def __init__(self, tenant):
        self.tenant = tenant

    def resolve(self, preset: PeriodPreset) -> PeriodSelection:
        first_date, latest_date = self._date_bounds()
        latest_month = _month_period(latest_date.year, latest_date.month)

        if preset == PeriodPreset.LATEST_MONTH:
            current = latest_month
            comparison = _shift_months(current, -1)
        elif preset == PeriodPreset.PREVIOUS_MONTH:
            current = _shift_months(latest_month, -1)
            comparison = _shift_months(current, -1)
        elif preset == PeriodPreset.LAST_QUARTER:
            current = PeriodReference(_shift_months(latest_month, -2).start_date, latest_month.end_date)
            comparison = _shift_months(current, -3)
        elif preset == PeriodPreset.HALF_YEAR:
            current = PeriodReference(_shift_months(latest_month, -5).start_date, latest_month.end_date)
            comparison = _shift_months(current, -6)
        elif preset == PeriodPreset.YEAR_TO_DATE:
            current = PeriodReference(date(latest_date.year, 1, 1), latest_month.end_date)
            previous_year_end = _same_day_previous_year(latest_month.end_date)
            comparison = PeriodReference(date(latest_date.year - 1, 1, 1), previous_year_end)
        else:
            raise ValueError(f"Unsupported period preset: {preset}")

        if comparison.end_date < first_date or not self._has_facts(comparison):
            comparison = None
        return PeriodSelection(current=current, comparison=comparison)

    def custom(self, start_date: date, end_date: date, *, include_comparison=True) -> PeriodSelection:
        current = PeriodReference(start_date, end_date)
        comparison = None
        if include_comparison:
            if start_date.day == 1 and end_date.day == calendar.monthrange(end_date.year, end_date.month)[1]:
                candidate = _shift_months(current, -1)
            else:
                duration = end_date - start_date
                comparison_end = start_date - timedelta(days=1)
                candidate = PeriodReference(comparison_end - duration, comparison_end)
            if self._has_facts(candidate):
                comparison = candidate
        return PeriodSelection(current=current, comparison=comparison)

    def _date_bounds(self):
        bounds = self._trusted_invoices().aggregate(first=Min("issue_date"), latest=Max("issue_date"))
        if bounds["first"] is None:
            raise ValueError("Tenant has no trusted canonical invoices.")
        return bounds["first"], bounds["latest"]

    def _has_facts(self, period):
        return self._trusted_invoices().filter(issue_date__range=(period.start_date, period.end_date)).exists()

    def _trusted_invoices(self):
        return (
            models.Invoice.objects.filter(
                tenant=self.tenant,
            )
            .exclude(status=models.InvoiceStatus.CANCELLED)
            .filter(
                Q(source_record__validation_status=models.ValidationStatus.VALID)
                | Q(source_record__validation_status=models.ValidationStatus.WARNING)
            )
        )


def _month_period(year, month):
    return PeriodReference(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))


def _shift_months(period, months):
    shifted_start = _shift_date_month(period.start_date, months, first_day=True)
    shifted_end = _shift_date_month(period.end_date, months, first_day=False)
    return PeriodReference(shifted_start, shifted_end)


def _shift_date_month(value, months, *, first_day):
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = 1 if first_day else calendar.monthrange(year, month)[1]
    return date(year, month, day)


def _same_day_previous_year(value):
    day = min(value.day, calendar.monthrange(value.year - 1, value.month)[1])
    return date(value.year - 1, value.month, day)
