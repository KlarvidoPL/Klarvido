from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    source_system: str
    external_id: str
    record_type: str
    schema_version: str
    effective_at: datetime | None
    raw_payload: dict
    validation_status: str = "VALID"
    validation_messages: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CompanyData:
    source: SourceMetadata
    legal_name: str
    tax_identifier: str
    regon: str
    pkd_code: str
    country_code: str
    default_currency: str


@dataclass(frozen=True, slots=True)
class CounterpartyData:
    source: SourceMetadata
    name: str
    tax_identifier: str
    country_code: str
    is_customer: bool
    is_supplier: bool


@dataclass(frozen=True, slots=True)
class CategoryData:
    source: SourceMetadata
    code: str
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class AccountingPeriodData:
    source: SourceMetadata
    kind: str
    label: str
    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class InvoiceLineData:
    position: int
    description: str
    category_code: str | None
    quantity: Decimal | None
    unit: str
    unit_price_net: Decimal | None
    net_amount: Decimal
    tax_rate: Decimal | None
    tax_amount: Decimal
    gross_amount: Decimal


@dataclass(frozen=True, slots=True)
class InvoiceData:
    source: SourceMetadata
    counterparty_tax_identifier: str
    invoice_type: str
    document_number: str
    issue_date: date
    currency: str
    net_amount: Decimal
    tax_amount: Decimal
    gross_amount: Decimal
    lines: tuple[InvoiceLineData, ...]


@dataclass(frozen=True, slots=True)
class AdapterDataset:
    external_reference: str
    schema_version: str
    data_as_of: datetime
    records: tuple[SourceMetadata, ...] = ()
    company: CompanyData | None = None
    counterparties: tuple[CounterpartyData, ...] = ()
    categories: tuple[CategoryData, ...] = ()
    periods: tuple[AccountingPeriodData, ...] = ()
    invoices: tuple[InvoiceData, ...] = ()


class SourceAdapter(Protocol):
    source_system: str

    def fetch(self) -> AdapterDataset:
        ...
