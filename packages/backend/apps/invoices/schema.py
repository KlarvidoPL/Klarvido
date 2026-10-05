import csv
import io

import graphene
from graphene_django import DjangoObjectType
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.ksef.schema import get_checked_tenant
from common.acl.policies import IsTenantMemberAccess
from common.graphql.acl import permission_classes, requires
from common.graphql.mutations import SerializerMutation
from . import models, serializers, services
from .query import invoice_queryset, summary


class InvoiceCategoryType(DjangoObjectType):
    class Meta:
        model = models.InvoiceCategory
        fields = ('id', 'name')


class InvoiceLineType(DjangoObjectType):
    class Meta:
        model = models.InvoiceLine
        fields = ('position', 'description', 'unit', 'quantity', 'unit_price', 'net', 'vat_rate')


class InvoiceType(DjangoObjectType):
    corrected_ksef_numbers = graphene.List(graphene.NonNull(graphene.String), required=True)
    lines = graphene.List(graphene.NonNull(InvoiceLineType), required=True)

    class Meta:
        model = models.Invoice
        fields = (
            'id',
            'ksef_number',
            'number',
            'direction',
            'kind',
            'issue_date',
            'permanent_storage_date',
            'seller_name',
            'seller_nip',
            'buyer_name',
            'buyer_nip',
            'currency',
            'net',
            'vat',
            'gross',
            'category',
            'corrected_ksef_numbers',
            'created_at',
        )

    def resolve_lines(self, info):
        return self.lines.order_by('position')


class InvoicePage(graphene.ObjectType):
    items = graphene.List(graphene.NonNull(InvoiceType), required=True)
    total_count = graphene.Int(required=True)


class InvoiceSyncRunType(DjangoObjectType):
    class Meta:
        model = models.InvoiceSyncRun
        fields = ('id', 'status', 'imported_count', 'completed_subjects', 'error_code', 'created_at', 'finished_at')


class InvoiceSyncStatus(graphene.ObjectType):
    start_date = graphene.DateTime()
    last_success_at = graphene.DateTime()
    runs = graphene.List(graphene.NonNull(InvoiceSyncRunType), required=True)
    connected = graphene.Boolean(required=True)
    import_error_count = graphene.Int(required=True)


class InvoiceSummary(graphene.ObjectType):
    currency = graphene.String()
    direction = graphene.String()
    count = graphene.Int()
    net = graphene.Decimal()
    vat = graphene.Decimal()
    gross = graphene.Decimal()


class InvoiceFilters(graphene.InputObjectType):
    search = graphene.String()
    direction = graphene.String()
    date_from = graphene.Date()
    date_to = graphene.Date()
    category = graphene.String()
    sort = graphene.String()


def filtered(info, filters=None):
    return invoice_queryset(get_checked_tenant(info), **dict(filters or {}))


def safe_cell(value):
    text = str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


class Query(graphene.ObjectType):
    invoices = graphene.Field(
        InvoicePage,
        tenant_id=graphene.ID(required=True),
        filters=InvoiceFilters(),
        page=graphene.Int(default_value=1),
        page_size=graphene.Int(default_value=25),
    )
    invoice = graphene.Field(InvoiceType, tenant_id=graphene.ID(required=True), id=graphene.ID(required=True))
    invoice_categories = graphene.List(InvoiceCategoryType, tenant_id=graphene.ID(required=True))
    invoice_sync_status = graphene.Field(InvoiceSyncStatus, tenant_id=graphene.ID(required=True))
    invoice_summary = graphene.List(InvoiceSummary, tenant_id=graphene.ID(required=True), filters=InvoiceFilters())
    invoice_xml = graphene.String(tenant_id=graphene.ID(required=True), id=graphene.ID(required=True))
    invoice_csv = graphene.String(tenant_id=graphene.ID(required=True), filters=InvoiceFilters())

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view'))
    def resolve_invoices(root, info, tenant_id, filters=None, page=1, page_size=25):
        if page < 1 or not 1 <= page_size <= 100:
            raise ValidationError('INVALID_PAGE')
        qs = filtered(info, filters).select_related('category')
        return InvoicePage(items=qs[(page - 1) * page_size : page * page_size], total_count=qs.count())

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view'))
    def resolve_invoice(root, info, tenant_id, id):
        return get_object_or_404(filtered(info), pk=id)

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view'))
    def resolve_invoice_categories(root, info, tenant_id):
        return services.categories(get_checked_tenant(info))

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view'))
    def resolve_invoice_sync_status(root, info, tenant_id):
        tenant = get_checked_tenant(info)
        state = services.current_state(tenant)
        return InvoiceSyncStatus(
            start_date=state.start_date if state else None,
            last_success_at=state.last_success_at if state else None,
            runs=state.runs.order_by('-created_at')[:10] if state else [],
            connected=tenant.ksefcredential_set.exists(),
            import_error_count=models.InvoiceImportError.objects.filter(state=state).count() if state else 0,
        )

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view'))
    def resolve_invoice_summary(root, info, tenant_id, filters=None):
        return summary(filtered(info, filters))

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view', 'invoices.export', mode='all'))
    def resolve_invoice_xml(root, info, tenant_id, id):
        return get_object_or_404(filtered(info), pk=id).raw_xml

    @staticmethod
    @permission_classes(IsTenantMemberAccess, requires('invoices.view', 'invoices.export', mode='all'))
    def resolve_invoice_csv(root, info, tenant_id, filters=None):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(
            [
                'Number',
                'KSeF',
                'Direction',
                'Date',
                'Seller',
                'Seller NIP',
                'Buyer',
                'Buyer NIP',
                'Currency',
                'Net',
                'VAT',
                'Gross',
                'Category',
            ]
        )
        for inv in filtered(info, filters).select_related('category').iterator():
            writer.writerow(
                [
                    safe_cell(v)
                    for v in [
                        inv.number,
                        inv.ksef_number,
                        inv.direction,
                        inv.issue_date,
                        inv.seller_name,
                        inv.seller_nip,
                        inv.buyer_name,
                        inv.buyer_nip,
                        inv.currency,
                        inv.net,
                        inv.vat,
                        inv.gross,
                        inv.category.name if inv.category else '',
                    ]
                ]
            )
        return output.getvalue()


class StartInvoiceSync(SerializerMutation):
    class Meta:
        serializer_class = serializers.StartInvoiceSyncSerializer
        model_operations = ('create',)


class SetInvoiceCategory(SerializerMutation):
    class Meta:
        serializer_class = serializers.SetInvoiceCategorySerializer
        model_operations = ('create',)


class Mutation(graphene.ObjectType):
    start_invoice_sync = permission_classes(
        IsTenantMemberAccess, requires('invoices.view', 'invoices.sync', mode='all')
    )(StartInvoiceSync.Field())
    set_invoice_category = permission_classes(
        IsTenantMemberAccess, requires('invoices.view', 'invoices.categorize', mode='all')
    )(SetInvoiceCategory.Field())
