from django.contrib import admin

from . import models


@admin.register(models.CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "tenant", "tax_identifier", "regon", "default_currency")
    search_fields = ("legal_name", "tax_identifier", "regon", "tenant__name")


@admin.register(models.DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "source_system", "status", "data_as_of", "created_at")
    list_filter = ("source_system", "status")


@admin.register(models.SourceRecord)
class SourceRecordAdmin(admin.ModelAdmin):
    list_display = ("external_id", "tenant", "source_system", "record_type", "validation_status")
    list_filter = ("source_system", "record_type", "validation_status")
    search_fields = ("external_id", "payload_checksum")


@admin.register(models.Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "tax_identifier", "is_customer", "is_supplier")
    list_filter = ("is_customer", "is_supplier", "country_code")
    search_fields = ("name", "tax_identifier")


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "code", "kind", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "code")


class InvoiceLineInline(admin.TabularInline):
    model = models.InvoiceLine
    extra = 0


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("document_number", "tenant", "invoice_type", "counterparty", "issue_date", "gross_amount")
    list_filter = ("invoice_type", "status", "currency")
    search_fields = ("document_number", "counterparty__name")
    inlines = (InvoiceLineInline,)


@admin.register(models.AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ("label", "tenant", "kind", "start_date", "end_date", "is_closed")
    list_filter = ("kind", "is_closed")
