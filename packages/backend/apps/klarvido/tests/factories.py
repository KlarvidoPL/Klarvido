from datetime import date
from decimal import Decimal

import factory

from apps.multitenancy.tests import factories as multitenancy_factories

from .. import models


class CompanyProfileFactory(factory.django.DjangoModelFactory):
    tenant = factory.SubFactory(multitenancy_factories.TenantFactory)
    legal_name = factory.Sequence(lambda n: f"Company {n}")
    tax_identifier = factory.Sequence(lambda n: f"PL{n:010d}")

    class Meta:
        model = models.CompanyProfile


class DataImportFactory(factory.django.DjangoModelFactory):
    tenant = factory.SubFactory(multitenancy_factories.TenantFactory)
    source_system = models.SourceSystem.MOCK
    schema_version = "1"
    status = models.ImportStatus.COMPLETED

    class Meta:
        model = models.DataImport


class SourceRecordFactory(factory.django.DjangoModelFactory):
    data_import = factory.SubFactory(DataImportFactory)
    tenant = factory.LazyAttribute(lambda obj: obj.data_import.tenant)
    source_system = factory.LazyAttribute(lambda obj: obj.data_import.source_system)
    record_type = "invoice"
    external_id = factory.Sequence(lambda n: f"mock-invoice-{n}")
    schema_version = "1"
    payload_checksum = factory.Sequence(lambda n: f"{n:064x}")

    class Meta:
        model = models.SourceRecord


class CounterpartyFactory(factory.django.DjangoModelFactory):
    tenant = factory.SubFactory(multitenancy_factories.TenantFactory)
    name = factory.Sequence(lambda n: f"Counterparty {n}")
    tax_identifier = factory.Sequence(lambda n: f"{n:010d}")
    is_customer = True

    class Meta:
        model = models.Counterparty


class CategoryFactory(factory.django.DjangoModelFactory):
    tenant = factory.SubFactory(multitenancy_factories.TenantFactory)
    code = factory.Sequence(lambda n: f"category-{n}")
    name = factory.Sequence(lambda n: f"Category {n}")
    kind = models.CategoryKind.COST

    class Meta:
        model = models.Category


class InvoiceFactory(factory.django.DjangoModelFactory):
    tenant = factory.SubFactory(multitenancy_factories.TenantFactory)
    counterparty = factory.LazyAttribute(lambda obj: CounterpartyFactory(tenant=obj.tenant))
    invoice_type = models.InvoiceType.SALES
    document_number = factory.Sequence(lambda n: f"FV/{n:04d}")
    issue_date = date(2026, 6, 15)
    net_amount = Decimal("100.00")
    tax_amount = Decimal("23.00")
    gross_amount = Decimal("123.00")

    class Meta:
        model = models.Invoice


class InvoiceLineFactory(factory.django.DjangoModelFactory):
    invoice = factory.SubFactory(InvoiceFactory)
    tenant = factory.LazyAttribute(lambda obj: obj.invoice.tenant)
    position = factory.Sequence(lambda n: n + 1)
    description = "Service"
    net_amount = Decimal("100.00")
    tax_rate = Decimal("23.00")
    tax_amount = Decimal("23.00")
    gross_amount = Decimal("123.00")

    class Meta:
        model = models.InvoiceLine


class AccountingPeriodFactory(factory.django.DjangoModelFactory):
    tenant = factory.SubFactory(multitenancy_factories.TenantFactory)
    kind = models.PeriodKind.MONTH
    label = "June 2026"
    start_date = date(2026, 6, 1)
    end_date = date(2026, 6, 30)

    class Meta:
        model = models.AccountingPeriod
