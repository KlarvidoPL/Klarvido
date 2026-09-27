import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

from apps.klarvido import models

from .contracts import (
    AccountingPeriodData,
    AdapterDataset,
    CategoryData,
    CompanyData,
    CounterpartyData,
    InvoiceData,
    InvoiceLineData,
    SourceMetadata,
)


DEFAULT_FIXTURE_PATH = Path(__file__).parent / "data" / "mock_dataset_v1.json"


class MockDataAdapter:
    source_system = models.SourceSystem.MOCK

    def __init__(self, fixture_path: Path | str = DEFAULT_FIXTURE_PATH):
        self.fixture_path = Path(fixture_path)

    def fetch(self) -> AdapterDataset:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        schema_version = payload["schema_version"]
        data_as_of = datetime.fromisoformat(payload["data_as_of"])

        company_payload = payload["company"]
        company = CompanyData(
            source=self._metadata("company", company_payload["id"], schema_version, data_as_of, company_payload),
            legal_name=company_payload["legal_name"],
            tax_identifier=company_payload["tax_identifier"],
            regon=company_payload["regon"],
            pkd_code=company_payload["pkd_code"],
            country_code=company_payload["country_code"],
            default_currency=company_payload["default_currency"],
        )

        counterparties = tuple(
            CounterpartyData(
                source=self._metadata("counterparty", item["id"], schema_version, data_as_of, item),
                name=item["name"],
                tax_identifier=item["tax_identifier"],
                country_code=item["country_code"],
                is_customer=item["is_customer"],
                is_supplier=item["is_supplier"],
            )
            for item in payload["counterparties"]
        )
        categories = tuple(
            CategoryData(
                source=self._metadata("category", item["code"], schema_version, data_as_of, item),
                code=item["code"],
                name=item["name"],
                kind=item["kind"],
            )
            for item in payload["categories"]
        )
        periods = tuple(self._period(item, schema_version, data_as_of) for item in payload["periods"])
        counterparties_by_id = {item["id"]: item for item in payload["counterparties"]}
        invoices = tuple(self._invoice(item, counterparties_by_id, schema_version) for item in payload["invoices"])

        return AdapterDataset(
            external_reference=payload["external_reference"],
            schema_version=schema_version,
            data_as_of=data_as_of,
            company=company,
            counterparties=counterparties,
            categories=categories,
            periods=periods,
            invoices=invoices,
        )

    def _period(self, payload, schema_version, data_as_of):
        start_date = date.fromisoformat(payload["start_date"])
        return AccountingPeriodData(
            source=self._metadata("accounting_period", payload["id"], schema_version, data_as_of, payload),
            kind=payload["kind"],
            label=payload["label"],
            start_date=start_date,
            end_date=date.fromisoformat(payload["end_date"]),
        )

    def _invoice(self, payload, counterparties_by_id, schema_version):
        issue_date = date.fromisoformat(payload["issue_date"])
        effective_at = datetime.combine(issue_date, time.min, tzinfo=timezone.utc)
        counterparty = counterparties_by_id[payload["counterparty_id"]]
        line = InvoiceLineData(
            position=1,
            description=payload["description"],
            category_code=payload["category_code"],
            quantity=None,
            unit="",
            unit_price_net=None,
            net_amount=Decimal(str(payload["net_amount"])),
            tax_rate=Decimal(str(payload["tax_rate"])),
            tax_amount=Decimal(str(payload["tax_amount"])),
            gross_amount=Decimal(str(payload["gross_amount"])),
        )
        return InvoiceData(
            source=self._metadata("invoice", payload["id"], schema_version, effective_at, payload),
            counterparty_tax_identifier=counterparty["tax_identifier"],
            invoice_type=payload["invoice_type"],
            document_number=payload["document_number"],
            issue_date=issue_date,
            currency=payload["currency"],
            net_amount=line.net_amount,
            tax_amount=line.tax_amount,
            gross_amount=line.gross_amount,
            lines=(line,),
        )

    def _metadata(self, record_type, external_id, schema_version, effective_at, raw_payload):
        return SourceMetadata(
            source_system=self.source_system,
            external_id=external_id,
            record_type=record_type,
            schema_version=schema_version,
            effective_at=effective_at,
            raw_payload=raw_payload,
        )
