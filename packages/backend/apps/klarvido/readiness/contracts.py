from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apps.klarvido.contracts import DataQuality, PeriodReference, SourceReference


class ReadinessStatus(StrEnum):
    READY = "READY"
    LIMITED = "LIMITED"
    BLOCKED = "BLOCKED"


class AnalysisKind(StrEnum):
    CUSTOMER_CONCENTRATION = "customer_concentration"
    CUSTOMER_TREND = "customer_trend"
    SUPPLIER_CONCENTRATION = "supplier_concentration"
    COST_STRUCTURE = "cost_structure"
    PRICE_VOLUME = "price_volume"
    CASH_FLOW = "cash_flow"


class DiagnosisStrength(StrEnum):
    INDICATIVE = "indicative"
    CONFIRMED = "confirmed"


class ReadinessGateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReadinessMetric:
    code: str
    label: str
    value: float
    unit: str
    status: ReadinessStatus
    ready_threshold: float
    limited_threshold: float


@dataclass(frozen=True, slots=True)
class DataReadiness:
    analysis: AnalysisKind
    period: PeriodReference
    status: ReadinessStatus
    score: float
    metrics: tuple[ReadinessMetric, ...]
    limitations: tuple[str, ...]
    sources: tuple[SourceReference, ...]
    policy_version: str
    checked_at: datetime

    @property
    def maximum_diagnosis_strength(self) -> DiagnosisStrength | None:
        if self.status is ReadinessStatus.READY:
            return DiagnosisStrength.CONFIRMED
        if self.status is ReadinessStatus.LIMITED:
            return DiagnosisStrength.INDICATIVE
        return None

    def ensure_diagnosis_allowed(self, requested: DiagnosisStrength) -> None:
        allowed = self.maximum_diagnosis_strength
        if allowed is None or (requested is DiagnosisStrength.CONFIRMED and allowed is DiagnosisStrength.INDICATIVE):
            raise ReadinessGateError(
                f"{requested.value} diagnosis is not allowed when readiness is {self.status.value}."
            )

    def as_data_quality(self) -> DataQuality:
        return DataQuality(
            status=self.status.value,
            score=self.score,
            limitations=self.limitations,
        )
