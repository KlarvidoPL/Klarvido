from collections import defaultdict
from decimal import Decimal

import pytest

from .. import models
from ..adapters import MockDataAdapter


pytestmark = pytest.mark.django_db


def test_mock_adapter_matches_reference_dataset():
    dataset = MockDataAdapter().fetch()

    assert dataset.external_reference == "klarvido-mock:v1"
    assert dataset.company.legal_name == "Meble Kowalski Sp. z o.o."
    assert len(dataset.counterparties) == 23
    assert sum(item.is_customer for item in dataset.counterparties) == 12
    assert sum(item.is_supplier for item in dataset.counterparties) == 11
    assert len(dataset.categories) == 12
    assert len(dataset.periods) == 6
    assert len(dataset.invoices) == 209


def test_mock_adapter_invoice_totals_match_reference_monthly_series():
    dataset = MockDataAdapter().fetch()
    totals = defaultdict(Decimal)

    for invoice in dataset.invoices:
        totals[(invoice.invoice_type, invoice.issue_date.month)] += invoice.net_amount

    assert [totals[(models.InvoiceType.SALES, month)] for month in range(1, 7)] == [
        Decimal("195000"),
        Decimal("205000"),
        Decimal("203900"),
        Decimal("207000"),
        Decimal("203000"),
        Decimal("201900"),
    ]
    assert [totals[(models.InvoiceType.PURCHASE, month)] for month in range(1, 7)] == [
        Decimal("91890"),
        Decimal("95970"),
        Decimal("94050"),
        Decimal("101130"),
        Decimal("108010"),
        Decimal("123590"),
    ]


def test_mock_adapter_exposes_source_metadata_and_uncategorized_invoice():
    dataset = MockDataAdapter().fetch()
    first_invoice = dataset.invoices[0]

    assert first_invoice.source.source_system == models.SourceSystem.MOCK
    assert first_invoice.source.record_type == "invoice"
    assert first_invoice.source.raw_payload["document_number"] == first_invoice.document_number
    assert sum(line.category_code is None for invoice in dataset.invoices for line in invoice.lines) == 1
