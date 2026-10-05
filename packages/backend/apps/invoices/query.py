from django.conf import settings
from django.db.models import Q, Sum, Count
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
    if sort not in ['issue_date', '-issue_date', 'number', '-number', 'net', '-net', 'gross', '-gross']:
        raise ValidationError('INVALID_SORT')
    return qs.order_by(sort, '-pk')


def summary(qs):
    return list(
        qs.order_by()
        .values('currency', 'direction')
        .annotate(count=Count('pk'), net=Sum('net'), vat=Sum('vat'), gross=Sum('gross'))
    )
