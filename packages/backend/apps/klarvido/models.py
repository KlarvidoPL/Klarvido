from decimal import Decimal

import hashid_field
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from common.models import TimestampedMixin


class SourceSystem(models.TextChoices):
    MOCK = "MOCK", "Mock data"
    KSEF = "KSEF", "KSeF"
    GUS = "GUS", "GUS"
    REGON = "REGON", "REGON"
    NBP = "NBP", "NBP"
    MANUAL = "MANUAL", "Manual"


class ImportStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    PARTIAL = "PARTIAL", "Partial"
    FAILED = "FAILED", "Failed"


class ValidationStatus(models.TextChoices):
    VALID = "VALID", "Valid"
    INVALID = "INVALID", "Invalid"
    WARNING = "WARNING", "Warning"


class InvoiceType(models.TextChoices):
    SALES = "SALES", "Sales"
    PURCHASE = "PURCHASE", "Purchase"


class InvoiceStatus(models.TextChoices):
    ISSUED = "ISSUED", "Issued"
    CORRECTED = "CORRECTED", "Corrected"
    CANCELLED = "CANCELLED", "Cancelled"


class CategoryKind(models.TextChoices):
    REVENUE = "REVENUE", "Revenue"
    COST = "COST", "Cost"
    BOTH = "BOTH", "Revenue and cost"


class CategoryAssignmentSource(models.TextChoices):
    UNASSIGNED = "UNASSIGNED", "Unassigned"
    SOURCE = "SOURCE", "Source system"
    RULE = "RULE", "Classification rule"
    USER = "USER", "User"


class PeriodKind(models.TextChoices):
    MONTH = "MONTH", "Month"
    QUARTER = "QUARTER", "Quarter"
    HALF_YEAR = "HALF_YEAR", "Half year"
    YEAR = "YEAR", "Year"
    CUSTOM = "CUSTOM", "Custom"


class TenantOwnedModel(TimestampedMixin, models.Model):
    tenant = models.ForeignKey(
        "multitenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="klarvido_%(class)s_set",
    )
    tenant_relation_fields: tuple[str, ...] = ()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        for field_name in self.tenant_relation_fields:
            related = getattr(self, field_name, None)
            if related is not None and related.tenant_id != self.tenant_id:
                raise ValidationError({field_name: "Related object must belong to the same tenant."})


class CompanyProfile(TimestampedMixin, models.Model):
    id = hashid_field.HashidAutoField(primary_key=True)
    tenant = models.OneToOneField(
        "multitenancy.Tenant",
        on_delete=models.CASCADE,
        related_name="klarvido_company_profile",
    )
    legal_name = models.CharField(max_length=255)
    tax_identifier = models.CharField(max_length=32, blank=True)
    regon = models.CharField(max_length=20, blank=True)
    pkd_code = models.CharField(max_length=16, blank=True)
    country_code = models.CharField(max_length=2, default="PL")
    default_currency = models.CharField(max_length=3, default="PLN")

    class Meta:
        verbose_name = "Klarvido company profile"
        verbose_name_plural = "Klarvido company profiles"

    def __str__(self):
        return self.legal_name


class DataImport(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    source_system = models.CharField(max_length=16, choices=SourceSystem.choices)
    external_reference = models.CharField(max_length=255, blank=True)
    schema_version = models.CharField(max_length=32)
    status = models.CharField(max_length=16, choices=ImportStatus.choices, default=ImportStatus.PENDING)
    data_as_of = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "source_system", "-created_at"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self):
        return f"{self.source_system} import {self.id}"


class SourceRecord(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    tenant_relation_fields = ("data_import",)

    data_import = models.ForeignKey(DataImport, on_delete=models.CASCADE, related_name="records")
    source_system = models.CharField(max_length=16, choices=SourceSystem.choices)
    record_type = models.CharField(max_length=64)
    external_id = models.CharField(max_length=255)
    schema_version = models.CharField(max_length=32)
    effective_at = models.DateTimeField(null=True, blank=True)
    payload_checksum = models.CharField(max_length=64)
    raw_payload = models.JSONField(default=dict)
    validation_status = models.CharField(
        max_length=16,
        choices=ValidationStatus.choices,
        default=ValidationStatus.VALID,
    )
    validation_messages = models.JSONField(default=list, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant", "source_system", "record_type"]),
            models.Index(fields=["tenant", "validation_status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "source_system", "record_type", "external_id"],
                name="klarvido_unique_source_record",
            )
        ]

    def __str__(self):
        return f"{self.source_system}:{self.record_type}:{self.external_id}"

    def clean(self):
        super().clean()
        if self.data_import_id and self.source_system != self.data_import.source_system:
            raise ValidationError({"source_system": "Source system must match the import."})


class Counterparty(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    tax_identifier = models.CharField(max_length=32, blank=True)
    country_code = models.CharField(max_length=2, default="PL")
    is_customer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["tenant", "name"]),
            models.Index(fields=["tenant", "is_customer"]),
            models.Index(fields=["tenant", "is_supplier"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_customer=True) | Q(is_supplier=True),
                name="klarvido_counterparty_has_role",
            ),
            models.UniqueConstraint(
                fields=["tenant", "tax_identifier"],
                condition=~Q(tax_identifier=""),
                name="klarvido_unique_counterparty_tax_id",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.is_customer and not self.is_supplier:
            raise ValidationError("Counterparty must be a customer, a supplier, or both.")


class Category(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    tenant_relation_fields = ("parent",)

    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, choices=CategoryKind.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="klarvido_unique_category_code")]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "Category cannot be its own parent."})


class Invoice(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    tenant_relation_fields = ("counterparty", "source_record", "correction_of")

    counterparty = models.ForeignKey(Counterparty, on_delete=models.PROTECT, related_name="invoices")
    source_record = models.OneToOneField(
        SourceRecord,
        on_delete=models.PROTECT,
        related_name="invoice",
        null=True,
        blank=True,
    )
    correction_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="corrections",
        null=True,
        blank=True,
    )
    invoice_type = models.CharField(max_length=16, choices=InvoiceType.choices)
    status = models.CharField(max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED)
    document_number = models.CharField(max_length=128)
    issue_date = models.DateField()
    sale_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="PLN")
    net_amount = models.DecimalField(max_digits=20, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [
            models.Index(fields=["tenant", "invoice_type", "issue_date"]),
            models.Index(fields=["tenant", "counterparty", "issue_date"]),
            models.Index(fields=["tenant", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "invoice_type", "counterparty", "document_number"],
                name="klarvido_unique_invoice_number",
            ),
            models.CheckConstraint(
                condition=Q(gross_amount=F("net_amount") + F("tax_amount")),
                name="klarvido_invoice_totals_match",
            ),
        ]

    def __str__(self):
        return self.document_number

    def clean(self):
        super().clean()
        if self.gross_amount != self.net_amount + self.tax_amount:
            raise ValidationError({"gross_amount": "Gross amount must equal net amount plus tax amount."})
        if self.correction_of_id and self.correction_of_id == self.id:
            raise ValidationError({"correction_of": "Invoice cannot correct itself."})


class InvoiceLine(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    tenant_relation_fields = ("invoice", "category")

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="invoice_lines",
        null=True,
        blank=True,
    )
    position = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    unit = models.CharField(max_length=32, blank=True)
    unit_price_net = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=20, decimal_places=2)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    tax_amount = models.DecimalField(max_digits=20, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=20, decimal_places=2)
    category_assignment_source = models.CharField(
        max_length=16,
        choices=CategoryAssignmentSource.choices,
        default=CategoryAssignmentSource.UNASSIGNED,
    )
    category_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["tenant", "invoice"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "position"], name="klarvido_unique_invoice_line_position"),
            models.CheckConstraint(
                condition=Q(gross_amount=F("net_amount") + F("tax_amount")),
                name="klarvido_invoice_line_totals_match",
            ),
        ]

    def __str__(self):
        return f"{self.invoice.document_number} / {self.position}"

    def clean(self):
        super().clean()
        if self.gross_amount != self.net_amount + self.tax_amount:
            raise ValidationError({"gross_amount": "Gross amount must equal net amount plus tax amount."})
        if self.category is None and self.category_assignment_source != CategoryAssignmentSource.UNASSIGNED:
            raise ValidationError({"category_assignment_source": "An assignment source requires a category."})


class AccountingPeriod(TenantOwnedModel):
    id = hashid_field.HashidAutoField(primary_key=True)
    kind = models.CharField(max_length=16, choices=PeriodKind.choices)
    label = models.CharField(max_length=64)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_date", "end_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "start_date", "end_date"],
                name="klarvido_unique_accounting_period",
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="klarvido_period_dates_ordered",
            ),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
