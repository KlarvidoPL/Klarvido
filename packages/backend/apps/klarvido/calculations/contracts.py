from dataclasses import dataclass
from decimal import Decimal

from apps.klarvido.contracts import AnalyticalValue


@dataclass(frozen=True, slots=True)
class FinancialSummary:
    revenue: AnalyticalValue[Decimal]
    costs: AnalyticalValue[Decimal]
    pre_tax_result: AnalyticalValue[Decimal]
    gross_margin: AnalyticalValue[Decimal]
    income_tax: AnalyticalValue[Decimal] | None
    net_result: AnalyticalValue[Decimal] | None
    net_margin: AnalyticalValue[Decimal] | None
    revenue_change: AnalyticalValue[Decimal] | None = None
    costs_change: AnalyticalValue[Decimal] | None = None
    pre_tax_result_change: AnalyticalValue[Decimal] | None = None
    gross_margin_change: AnalyticalValue[Decimal] | None = None
    net_result_change: AnalyticalValue[Decimal] | None = None
    net_margin_change: AnalyticalValue[Decimal] | None = None


@dataclass(frozen=True, slots=True)
class PartyAggregate:
    counterparty_id: str
    name: str
    tax_identifier: str
    amount: AnalyticalValue[Decimal]
    share: AnalyticalValue[Decimal]
    percentage_change: AnalyticalValue[Decimal] | None
    invoice_count: AnalyticalValue[int]


@dataclass(frozen=True, slots=True)
class PortfolioAggregate:
    invoice_type: str
    total: AnalyticalValue[Decimal]
    parties: tuple[PartyAggregate, ...]
    top_three_concentration: AnalyticalValue[Decimal]
    active_count: AnalyticalValue[int]
    largest_party: PartyAggregate


@dataclass(frozen=True, slots=True)
class CategoryAggregate:
    category_code: str | None
    category_name: str
    amount: AnalyticalValue[Decimal]
    share: AnalyticalValue[Decimal]


@dataclass(frozen=True, slots=True)
class CostStructure:
    total: AnalyticalValue[Decimal]
    categories: tuple[CategoryAggregate, ...]
