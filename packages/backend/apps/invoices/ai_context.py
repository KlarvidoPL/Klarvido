"""Resolve component context from authorized database records, never client amounts."""
import graphene
from graphql_relay import from_global_id
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.multitenancy.middleware import get_current_tenant_with_membership_check
from apps.multitenancy.models import user_has_permission
from .query import invoice_queryset, summary
from .schema import InvoiceFilters


class ComponentKind(graphene.Enum):
    INVOICE_LIST = 'INVOICE_LIST'
    INVOICE_DETAILS = 'INVOICE_DETAILS'
    INVOICE_SELECTION = 'INVOICE_SELECTION'


class ComponentContextInput(graphene.InputObjectType):
    kind = graphene.Field(ComponentKind, required=True)
    invoice_ids = graphene.List(graphene.NonNull(graphene.ID))
    filters = graphene.InputField(InvoiceFilters)


def resolve_tenant(user, tenant_id, request=None):
    type_name, decoded = from_global_id(tenant_id)
    tenant = get_current_tenant_with_membership_check(
        decoded if type_name == 'TenantType' else tenant_id, user, request
    )
    if not tenant or not user_has_permission(user, tenant, 'features.ai.use'):
        raise PermissionDenied('permission_denied')
    return tenant


def invoice_context(tenant, user, attachments):
    if not attachments:
        return []
    if len(attachments) > 10:
        raise ValidationError('TOO_MUCH_CONTEXT')
    if not user_has_permission(user, tenant, 'invoices.view'):
        raise PermissionDenied('permission_denied')
    result = []
    for attachment in attachments:
        kind = attachment['kind']
        kind = getattr(kind, 'value', kind)
        ids = list(dict.fromkeys(attachment.get('invoice_ids') or []))
        if kind == 'INVOICE_LIST':
            qs = invoice_queryset(tenant, **dict(attachment.get('filters') or {}))
        elif kind in ['INVOICE_DETAILS', 'INVOICE_SELECTION'] and ids and len(ids) <= 100:
            try:
                qs = invoice_queryset(tenant).filter(pk__in=ids)
            except (TypeError, ValueError):
                raise PermissionDenied('permission_denied')
            if qs.count() != len(ids):
                raise PermissionDenied('permission_denied')
        else:
            raise ValidationError('INVALID_CONTEXT')
        items = []
        for invoice in qs.select_related('category')[:50]:
            item = {
                field: str(getattr(invoice, field))
                for field in [
                    'id',
                    'number',
                    'ksef_number',
                    'direction',
                    'kind',
                    'issue_date',
                    'seller_name',
                    'seller_nip',
                    'buyer_name',
                    'buyer_nip',
                    'currency',
                    'net',
                    'vat',
                    'gross',
                ]
            }
            item['source'] = f'invoice:{invoice.pk}'
            item['category'] = invoice.category.name if invoice.category else None
            item['corrected_ksef_numbers'] = invoice.corrected_ksef_numbers
            if kind != 'INVOICE_LIST':
                item['lines'] = [
                    {
                        field: str(getattr(line, field))[:2000]
                        for field in ['description', 'quantity', 'unit', 'unit_price', 'net', 'vat_rate']
                    }
                    for line in invoice.lines.all()[:100]
                ]
            items.append(item)
        result.append(
            {
                'kind': kind,
                'filters': dict(attachment.get('filters') or {}),
                'total_count': qs.count(),
                'summary_by_currency': summary(qs),
                'invoices': items,
                'sample_limit': 50,
            }
        )
    return result
