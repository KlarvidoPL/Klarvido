from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Generic, TypeVar


ValueT = TypeVar("ValueT")


class ValueKind(StrEnum):
    FACT = "fact"
    ESTIMATE = "estimate"
    SIMULATION = "simulation"


@dataclass(frozen=True, slots=True)
class PeriodReference:
    start_date: date
    end_date: date

    def __post_init__(self):
        if self.end_date < self.start_date:
            raise ValueError("Period end date cannot be before its start date.")


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_system: str
    external_id: str
    source_record_id: str | None = None

    def __post_init__(self):
        if not self.source_system or not self.external_id:
            raise ValueError("A source reference requires a source system and external identifier.")


@dataclass(frozen=True, slots=True)
class DataQuality:
    status: str
    score: float | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.status:
            raise ValueError("Data quality status cannot be empty.")
        if self.score is not None and not 0 <= self.score <= 1:
            raise ValueError("Data quality score must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class AnalyticalValue(Generic[ValueT]):
    value: ValueT | None
    unit: str
    period: PeriodReference
    sources: tuple[SourceReference, ...]
    calculation_version: str
    calculated_at: datetime
    quality: DataQuality
    kind: ValueKind
    limitations: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.unit:
            raise ValueError("Analytical value unit cannot be empty.")
        if not self.sources:
            raise ValueError("Analytical value requires at least one source reference.")
        if not self.calculation_version:
            raise ValueError("Calculation version cannot be empty.")
        if self.calculated_at.tzinfo is None or self.calculated_at.utcoffset() is None:
            raise ValueError("Calculation timestamp must be timezone-aware.")
