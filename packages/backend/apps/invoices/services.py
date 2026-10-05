from datetime import datetime, time, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.ksef.models import KsefCredential
from apps.multitenancy.constants import ActionType
from common.action_logging.service import log_action
from .models import InvoiceCategory, InvoiceSyncState, InvoiceSyncRun
from .tasks import sync_invoices

CATEGORIES = [
    'Materiały produkcyjne',
    'Artykuły biurowe',
    'Artykuły gospodarcze',
    'Media',
    'Najem',
    'Subskrypcja',
    'Usł. telekomunikacyjna',
    'Usługa serwisowa',
    'Usługi obce',
    'Wyposażenie',
    'Inne',
    'Sprzedaż wyrobów gotowych',
    'Sprzedaż usług',
    'Sprzedaż towarów',
]


def current_state(tenant):
    return InvoiceSyncState.objects.filter(
        tenant=tenant, environment=settings.KSEF_ENVIRONMENT, context_nip=tenant.nip
    ).first()


def categories(tenant):
    for name in CATEGORIES:
        InvoiceCategory.objects.get_or_create(tenant=tenant, name=name)
    return InvoiceCategory.objects.filter(tenant=tenant).order_by('name')


def start_sync(tenant, user, start_date=None):
    if tenant.country != 'PL' or not tenant.nip:
        raise ValidationError('COUNTRY_OR_NIP_INVALID')
    if not KsefCredential.objects.filter(tenant=tenant).exists():
        raise ValidationError('NOT_CONFIGURED')
    now = timezone.now()
    start = datetime.combine(start_date, time.min, tzinfo=dt_timezone.utc) if start_date else None
    if start and start > now:
        raise ValidationError('INVALID_START_DATE')
    # Tenant row serializes initial state creation as well as concurrent requests.
    with transaction.atomic():
        type(tenant).objects.select_for_update().get(pk=tenant.pk)
        state = current_state(tenant)
        if state is None:
            if start is None:
                raise ValidationError('START_DATE_REQUIRED')
            state = InvoiceSyncState.objects.create(
                tenant=tenant, environment=settings.KSEF_ENVIRONMENT, context_nip=tenant.nip, start_date=start
            )
        state = InvoiceSyncState.objects.select_for_update().get(pk=state.pk)
        active = state.runs.filter(status__in=['QUEUED', 'RUNNING']).first()
        if active:
            return active
        if start and start < state.start_date:
            state.start_date = start
            state.checkpoints = {}
            state.save(update_fields=['start_date', 'checkpoints', 'updated_at'])
        run = InvoiceSyncRun.objects.create(tenant=tenant, state=state)
        transaction.on_commit(lambda: enqueue(run.pk))
    log_action(
        tenant_id=tenant.pk,
        action_type=ActionType.CREATE,
        entity_type='invoice_sync',
        entity_id=str(run.pk),
        entity_name='Invoice synchronization',
        actor_user=user,
        metadata={'operation': 'sync', 'start': state.start_date.isoformat()},
    )
    return run


def enqueue(run_id, countdown=0):
    sync_invoices.apply_async(args=[run_id], countdown=countdown)
