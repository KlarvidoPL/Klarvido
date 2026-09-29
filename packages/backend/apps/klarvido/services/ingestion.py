import hashlib
import json
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.klarvido import models
from apps.klarvido.adapters.contracts import SourceAdapter, SourceMetadata


@dataclass(frozen=True, slots=True)
class ImportSummary:
    data_import_id: str
    source_records: int
    counterparties: int
    categories: int
    periods: int
    invoices: int
    invoice_lines: int


def import_from_adapter(*, tenant, adapter: SourceAdapter) -> ImportSummary:
    dataset = adapter.fetch()
    data_import = _get_or_create_import(
        tenant,
        adapter.source_system,
        dataset.external_reference,
        dataset.schema_version,
    )
    data_import.status = models.ImportStatus.PROCESSING
    data_import.started_at = timezone.now()
    data_import.completed_at = None
    data_import.error_message = ""
    data_import.data_as_of = dataset.data_as_of
    data_import.save()

    try:
        with transaction.atomic():
            summary = _persist_dataset(tenant, data_import, dataset)
            data_import.status = models.ImportStatus.COMPLETED
            data_import.completed_at = timezone.now()
            data_import.save()
            return summary
    except Exception as error:
        data_import.status = models.ImportStatus.FAILED
        data_import.completed_at = timezone.now()
        data_import.error_message = str(error)
        data_import.save()
        raise


def _get_or_create_import(tenant, source_system, external_reference, schema_version):
    data_import = models.DataImport.objects.filter(
        tenant=tenant,
        source_system=source_system,
        external_reference=external_reference,
    ).first()
    if data_import is None:
        data_import = models.DataImport.objects.create(
            tenant=tenant,
            source_system=source_system,
            external_reference=external_reference,
            schema_version=schema_version,
        )
    elif data_import.schema_version != schema_version:
        data_import.schema_version = schema_version
        data_import.save()
    return data_import


def _persist_dataset(tenant, data_import, dataset):
    source_record_count = 0

    for source in dataset.records:
        _upsert_source_record(tenant, data_import, source)
        source_record_count += 1

    if dataset.company is not None:
        _upsert_source_record(tenant, data_import, dataset.company.source)
        source_record_count += 1
        models.CompanyProfile.objects.update_or_create(
            tenant=tenant,
            defaults={
                "legal_name": dataset.company.legal_name,
                "tax_identifier": dataset.company.tax_identifier,
                "regon": dataset.company.regon,
                "pkd_code": dataset.company.pkd_code,
                "country_code": dataset.company.country_code,
                "default_currency": dataset.company.default_currency,
            },
        )

    counterparties = {}
    for item in dataset.counterparties:
        _upsert_source_record(tenant, data_import, item.source)
        source_record_count += 1
        counterparty, _ = models.Counterparty.objects.update_or_create(
            tenant=tenant,
            tax_identifier=item.tax_identifier,
            defaults={
                "name": item.name,
                "country_code": item.country_code,
                "is_customer": item.is_customer,
                "is_supplier": item.is_supplier,
            },
        )
        counterparties[item.tax_identifier] = counterparty

    categories = {}
    for item in dataset.categories:
        _upsert_source_record(tenant, data_import, item.source)
        source_record_count += 1
        category, _ = models.Category.objects.update_or_create(
            tenant=tenant,
            code=item.code,
            defaults={"name": item.name, "kind": item.kind, "is_active": True},
        )
        categories[item.code] = category

    for item in dataset.periods:
        _upsert_source_record(tenant, data_import, item.source)
        source_record_count += 1
        models.AccountingPeriod.objects.update_or_create(
            tenant=tenant,
            start_date=item.start_date,
            end_date=item.end_date,
            defaults={"kind": item.kind, "label": item.label},
        )

    invoice_line_count = 0
    for item in dataset.invoices:
        source_record = _upsert_source_record(tenant, data_import, item.source)
        source_record_count += 1
        invoice, _ = models.Invoice.objects.update_or_create(
            source_record=source_record,
            defaults={
                "tenant": tenant,
                "counterparty": counterparties[item.counterparty_tax_identifier],
                "invoice_type": item.invoice_type,
                "status": models.InvoiceStatus.ISSUED,
                "document_number": item.document_number,
                "issue_date": item.issue_date,
                "currency": item.currency,
                "net_amount": item.net_amount,
                "tax_amount": item.tax_amount,
                "gross_amount": item.gross_amount,
            },
        )
        positions = []
        for line in item.lines:
            positions.append(line.position)
            models.InvoiceLine.objects.update_or_create(
                invoice=invoice,
                position=line.position,
                defaults={
                    "tenant": tenant,
                    "category": categories.get(line.category_code),
                    "description": line.description,
                    "quantity": line.quantity,
                    "unit": line.unit,
                    "unit_price_net": line.unit_price_net,
                    "net_amount": line.net_amount,
                    "tax_rate": line.tax_rate,
                    "tax_amount": line.tax_amount,
                    "gross_amount": line.gross_amount,
                    "category_assignment_source": (
                        models.CategoryAssignmentSource.SOURCE
                        if line.category_code
                        else models.CategoryAssignmentSource.UNASSIGNED
                    ),
                },
            )
            invoice_line_count += 1
        invoice.lines.exclude(position__in=positions).delete()

    return ImportSummary(
        data_import_id=str(data_import.id),
        source_records=source_record_count,
        counterparties=len(dataset.counterparties),
        categories=len(dataset.categories),
        periods=len(dataset.periods),
        invoices=len(dataset.invoices),
        invoice_lines=invoice_line_count,
    )


def _upsert_source_record(tenant, data_import, source: SourceMetadata):
    canonical_payload = json.dumps(source.raw_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    source_record, _ = models.SourceRecord.objects.update_or_create(
        tenant=tenant,
        source_system=source.source_system,
        record_type=source.record_type,
        external_id=source.external_id,
        defaults={
            "data_import": data_import,
            "schema_version": source.schema_version,
            "effective_at": source.effective_at,
            "payload_checksum": checksum,
            "raw_payload": source.raw_payload,
            "validation_status": source.validation_status,
            "validation_messages": list(source.validation_messages),
        },
    )
    return source_record
