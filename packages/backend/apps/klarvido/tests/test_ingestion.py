from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db.models import Sum

from .. import models
from ..adapters import MockDataAdapter
from ..adapters.contracts import AdapterDataset, SourceMetadata
from ..services import import_from_adapter


pytestmark = pytest.mark.django_db


class SourceOnlyAdapter:
    source_system = models.SourceSystem.NBP

    def fetch(self):
        effective_at = datetime(2026, 6, 30, tzinfo=timezone.utc)
        return AdapterDataset(
            external_reference="nbp-mock:v1",
            schema_version="1",
            data_as_of=effective_at,
            records=(
                SourceMetadata(
                    source_system=self.source_system,
                    external_id="eur-pln-2026-06-30",
                    record_type="exchange_rate",
                    schema_version="1",
                    effective_at=effective_at,
                    raw_payload={"currency": "EUR", "rate": "4.31"},
                ),
            ),
        )


class BrokenInvoiceAdapter:
    source_system = models.SourceSystem.MOCK

    def fetch(self):
        dataset = MockDataAdapter().fetch()
        broken_invoice = replace(
            dataset.invoices[0],
            counterparty_tax_identifier="missing-counterparty",
        )
        return replace(
            dataset,
            external_reference="klarvido-broken:v1",
            invoices=(broken_invoice,),
        )


def test_import_persists_canonical_demo_dataset(tenant):
    summary = import_from_adapter(tenant=tenant, adapter=MockDataAdapter())

    assert summary.source_records == 251
    assert summary.counterparties == 23
    assert summary.categories == 12
    assert summary.periods == 6
    assert summary.invoices == 209
    assert summary.invoice_lines == 209
    assert models.CompanyProfile.objects.get(tenant=tenant).legal_name == "Meble Kowalski Sp. z o.o."
    assert models.DataImport.objects.get(tenant=tenant).status == models.ImportStatus.COMPLETED
    assert models.Invoice.objects.filter(tenant=tenant).count() == 209
    assert models.InvoiceLine.objects.filter(tenant=tenant).count() == 209
    assert models.Invoice.objects.filter(tenant=tenant, invoice_type=models.InvoiceType.SALES).aggregate(
        total=Sum("net_amount")
    )["total"] == Decimal("1215800.00")


def test_import_is_idempotent_for_the_same_tenant(tenant):
    first = import_from_adapter(tenant=tenant, adapter=MockDataAdapter())
    invoice_ids = set(models.Invoice.objects.filter(tenant=tenant).values_list("id", flat=True))

    second = import_from_adapter(tenant=tenant, adapter=MockDataAdapter())

    assert second.data_import_id == first.data_import_id
    assert models.DataImport.objects.filter(tenant=tenant).count() == 1
    assert models.SourceRecord.objects.filter(tenant=tenant).count() == 251
    assert models.Invoice.objects.filter(tenant=tenant).count() == 209
    assert set(models.Invoice.objects.filter(tenant=tenant).values_list("id", flat=True)) == invoice_ids


def test_import_keeps_tenant_datasets_isolated(tenant_factory):
    first_tenant = tenant_factory()
    second_tenant = tenant_factory()

    import_from_adapter(tenant=first_tenant, adapter=MockDataAdapter())
    import_from_adapter(tenant=second_tenant, adapter=MockDataAdapter())

    assert models.Invoice.objects.filter(tenant=first_tenant).count() == 209
    assert models.Invoice.objects.filter(tenant=second_tenant).count() == 209
    assert not models.Invoice.objects.filter(
        tenant=first_tenant,
        counterparty__tenant=second_tenant,
    ).exists()


def test_management_command_loads_demo_for_existing_tenant(tenant, capsys):
    call_command("load_klarvido_demo", tenant_slug=tenant.slug)

    output = capsys.readouterr().out
    assert "209 invoices" in output
    assert models.Invoice.objects.filter(tenant=tenant).count() == 209


def test_source_only_adapter_uses_the_same_ingestion_contract(tenant):
    summary = import_from_adapter(tenant=tenant, adapter=SourceOnlyAdapter())

    assert summary.source_records == 1
    assert summary.invoices == 0
    assert models.SourceRecord.objects.get(tenant=tenant).record_type == "exchange_rate"
    assert not models.CompanyProfile.objects.filter(tenant=tenant).exists()


def test_failed_import_rolls_back_canonical_records_and_records_failure(tenant):
    with pytest.raises(KeyError, match="missing-counterparty"):
        import_from_adapter(tenant=tenant, adapter=BrokenInvoiceAdapter())

    data_import = models.DataImport.objects.get(tenant=tenant)
    assert data_import.status == models.ImportStatus.FAILED
    assert data_import.completed_at is not None
    assert "missing-counterparty" in data_import.error_message
    assert not models.SourceRecord.objects.filter(tenant=tenant).exists()
    assert not models.CompanyProfile.objects.filter(tenant=tenant).exists()
    assert not models.Counterparty.objects.filter(tenant=tenant).exists()
    assert not models.Invoice.objects.filter(tenant=tenant).exists()
