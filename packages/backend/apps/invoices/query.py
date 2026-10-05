from django.conf import settings
from django.db.models import Q, Sum, Count, Case, When, F, CharField
from rest_framework.exceptions import ValidationError

from .models import Invoice


def invoice_queryset(tenant, search='', direction='', date_from=None, date_to=None, category='', sort='-issue_date'):
    qs = Invoice.objects.filter(tenant=tenant, environment=settings.KSEF_ENVIRONMENT, context_nip=tenant.nip)
    if search:
        qs = qs.filter(
            Q(number__icontains=search)
            | Q(ksef_number__icontains=search)
            | Q(seller_name__icontains=search)
            | Q(buyer_name__icontains=search)
            | Q(seller_nip__icontains=search)
            | Q(buyer_nip__icontains=search)
        )
    if direction:
        if direction not in ['SALE', 'PURCHASE']:
            raise ValidationError('INVALID_DIRECTION')
        qs = qs.filter(direction=direction)
    if date_from:
        qs = qs.filter(issue_date__gte=date_from)
    if date_to:
        qs = qs.filter(issue_date__lte=date_to)
    if category == 'uncategorized':
        qs = qs.filter(category__isnull=True)
    elif category:
        qs = qs.filter(category_id=category)
    fields = {'issue_date', 'number', 'net', 'vat', 'gross', 'currency', 'direction', 'category__name', 'counterparty'}
    if sort.removeprefix('-') not in fields:
        raise ValidationError('INVALID_SORT')
    if sort.removeprefix('-') == 'counterparty':
        qs = qs.annotate(
            counterparty=Case(
                When(direction='SALE', then=F('buyer_name')),
                default=F('seller_name'),
                output_field=CharField(),
            )
        )
    return qs.order_by(sort, '-pk')


def summary(qs):
    return list(
        qs.order_by()
        .values('currency', 'direction')
        .annotate(count=Count('pk'), net=Sum('net'), vat=Sum('vat'), gross=Sum('gross'))
    )
