from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .. import models


pytestmark = pytest.mark.django_db


class TestCanonicalModels:
    def test_invoice_preserves_decimal_amounts(self, invoice):
        assert invoice.net_amount == Decimal("100.00")
        assert invoice.tax_amount == Decimal("23.00")
        assert invoice.gross_amount == Decimal("123.00")

    def test_invoice_rejects_inconsistent_totals(self, invoice_factory):
        with pytest.raises(ValidationError, match="Gross amount must equal"):
            invoice_factory(gross_amount=Decimal("124.00"))

    def test_counterparty_requires_at_least_one_role(self, counterparty_factory):
        with pytest.raises(ValidationError, match="must be a customer"):
            counterparty_factory(is_customer=False, is_supplier=False)

    def test_accounting_period_rejects_reversed_dates(self, accounting_period_factory):
        with pytest.raises(ValidationError, match="End date cannot be before"):
            accounting_period_factory(start_date=date(2026, 6, 30), end_date=date(2026, 6, 1))

    def test_source_record_matches_import_source_system(self, data_import, source_record_factory):
        with pytest.raises(ValidationError, match="Source system must match"):
            source_record_factory(data_import=data_import, source_system=models.SourceSystem.KSEF)

    def test_invoice_line_rejects_inconsistent_totals(self, invoice_line_factory):
        with pytest.raises(ValidationError, match="Gross amount must equal"):
            invoice_line_factory(gross_amount=Decimal("124.00"))

    def test_invoice_line_requires_unassigned_source_without_category(self, invoice_line_factory):
        with pytest.raises(ValidationError, match="assignment source requires a category"):
            invoice_line_factory(
                category=None,
                category_assignment_source=models.CategoryAssignmentSource.SOURCE,
            )

    def test_source_record_is_idempotent_within_tenant(self, source_record, source_record_factory):
        with pytest.raises(IntegrityError):
            source_record_factory(
                tenant=source_record.tenant,
                data_import=source_record.data_import,
                source_system=source_record.source_system,
                record_type=source_record.record_type,
                external_id=source_record.external_id,
            )


class TestTenantIsolation:
    def test_source_record_rejects_import_from_another_tenant(
        self, tenant_factory, data_import_factory, source_record_factory
    ):
        tenant = tenant_factory()
        foreign_import = data_import_factory()

        with pytest.raises(ValidationError, match="same tenant"):
            source_record_factory(tenant=tenant, data_import=foreign_import)

    def test_invoice_rejects_counterparty_from_another_tenant(
        self, tenant_factory, counterparty_factory, invoice_factory
    ):
        invoice_tenant = tenant_factory()
        foreign_counterparty = counterparty_factory()

        with pytest.raises(ValidationError, match="same tenant"):
            invoice_factory(tenant=invoice_tenant, counterparty=foreign_counterparty)

    def test_line_rejects_category_from_another_tenant(self, invoice, category_factory, invoice_line_factory):
        foreign_category = category_factory()

        with pytest.raises(ValidationError, match="same tenant"):
            invoice_line_factory(tenant=invoice.tenant, invoice=invoice, category=foreign_category)

    def test_category_rejects_parent_from_another_tenant(self, tenant_factory, category_factory):
        tenant = tenant_factory()
        foreign_parent = category_factory()

        with pytest.raises(ValidationError, match="same tenant"):
            category_factory(tenant=tenant, parent=foreign_parent)

    def test_invoice_rejects_source_record_from_another_tenant(
        self, tenant_factory, source_record_factory, invoice_factory
    ):
        tenant = tenant_factory()
        foreign_source = source_record_factory()

        with pytest.raises(ValidationError, match="same tenant"):
            invoice_factory(tenant=tenant, source_record=foreign_source)


class TestCanonicalConstraints:
    def test_company_profile_is_unique_per_tenant(self, company_profile, company_profile_factory):
        with pytest.raises(IntegrityError):
            company_profile_factory(tenant=company_profile.tenant)

    def test_invoice_number_is_unique_within_counterparty_and_tenant(self, invoice, invoice_factory):
        with pytest.raises(IntegrityError):
            invoice_factory(
                tenant=invoice.tenant,
                counterparty=invoice.counterparty,
                invoice_type=invoice.invoice_type,
                document_number=invoice.document_number,
            )

    def test_same_invoice_number_is_allowed_for_another_tenant(self, invoice, invoice_factory):
        other_invoice = invoice_factory(document_number=invoice.document_number)

        assert other_invoice.tenant_id != invoice.tenant_id

    def test_invoice_line_position_is_unique_per_invoice(self, invoice_line, invoice_line_factory):
        with pytest.raises(IntegrityError):
            invoice_line_factory(
                tenant=invoice_line.tenant,
                invoice=invoice_line.invoice,
                position=invoice_line.position,
            )

    def test_category_code_is_unique_only_within_tenant(self, category, category_factory):
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                category_factory(tenant=category.tenant, code=category.code)

        category_for_other_tenant = category_factory(code=category.code)
        assert category_for_other_tenant.tenant_id != category.tenant_id
