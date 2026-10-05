import logging
import uuid
from datetime import timedelta

import httpx
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.ksef import crypto
from apps.ksef.models import KsefCredential
from .ksef import KsefSession, KsefSyncError
from .models import Invoice, InvoiceLine, InvoiceSyncRun, InvoiceImportError, InvoiceSyncState
from .parser import parse_invoice, InvoiceParseError

logger = logging.getLogger(__name__)
SUBJECTS = ['Subject1', 'Subject2']


class LeaseLost(Exception):
    pass


def owned_run(run):
    current = InvoiceSyncRun.objects.select_for_update().get(pk=run.pk)
    if current.status != 'RUNNING' or current.execution_token != run.execution_token:
        raise LeaseLost
    return current


def save_owned(run, fields=None):
    with transaction.atomic():
        owned_run(run)
        run.save(update_fields=fields)


def import_document(state, meta, xml, subject, run=None):
    data = parse_invoice(xml)
    if data['gross'] is None:
        raise InvoiceParseError('INVALID_XML')
    lines = data.pop('lines')
    with transaction.atomic():
        if run is not None:
            owned_run(run)
        invoice, created = Invoice.objects.update_or_create(
            tenant=state.tenant,
            environment=state.environment,
            ksef_number=meta['ksefNumber'],
            defaults={
                **data,
                'context_nip': state.context_nip,
                'direction': 'SALE' if subject == 'Subject1' else 'PURCHASE',
                'permanent_storage_date': parse_datetime(meta['permanentStorageDate']),
                'raw_xml': xml,
            },
        )
        invoice.lines.all().delete()
        InvoiceLine.objects.bulk_create([InvoiceLine(invoice=invoice, tenant=state.tenant, **line) for line in lines])
        InvoiceImportError.objects.filter(state=state, ksef_number=meta['ksefNumber']).delete()
    return created


def defer(run, delay, error=''):
    run.status = 'QUEUED'
    run.error_code = error
    run.heartbeat_at = timezone.now()
    save_owned(run)
    sync_invoices.apply_async(args=[run.pk], countdown=delay)


@shared_task(ignore_result=True)
def sync_invoices(run_id):
    with transaction.atomic():
        run = InvoiceSyncRun.objects.select_for_update(of=('self',)).select_related('state__tenant').get(pk=run_id)
        if run.status not in ['QUEUED', 'RUNNING']:
            return
        if run.status == 'RUNNING' and run.heartbeat_at and run.heartbeat_at > timezone.now() - timedelta(minutes=30):
            return
        run.status, run.heartbeat_at = 'RUNNING', timezone.now()
        run.execution_token = uuid.uuid4()
        run.save()
    state = run.state
    try:
        if state.environment != settings.KSEF_ENVIRONMENT or state.context_nip != state.tenant.nip:
            raise KsefSyncError('CONTEXT_CHANGED')
        credential = KsefCredential.objects.filter(tenant=state.tenant).first()
        if not credential:
            raise KsefSyncError('NOT_CONFIGURED')
        subject = next((s for s in SUBJECTS if s not in run.completed_subjects), None)
        if subject is None:
            run.status = 'COMPLETED'
            run.error_code = ''
            run.finished_at = timezone.now()
            save_owned(run)
            state.last_success_at = run.finished_at
            state.save(update_fields=['last_success_at', 'updated_at'])
            return
        token = crypto.decrypt_token(state.tenant_id, credential.encrypted_token)
        with KsefSession(state.context_nip, token) as session:
            if not run.pending_export:
                run.pending_export = session.start_export(
                    subject,
                    state.checkpoints.get(subject, state.start_date.isoformat()),
                    state.tenant_id,
                    run.created_at.isoformat(),
                )
                save_owned(run, fields=['pending_export', 'updated_at'])
                defer(run, 15)
                return
            package = session.export_status(run.pending_export)
            if package is None:
                if timezone.now() - run.created_at > timedelta(hours=6):
                    raise KsefSyncError('EXPORT_TIMEOUT')
                defer(run, 30)
                return
            documents = session.read_package(package, run.pending_export, state.tenant_id)
            if not InvoiceSyncRun.objects.filter(
                pk=run.pk, status='RUNNING', execution_token=run.execution_token
            ).exists():
                return
            errors = False
            for meta, xml in documents:
                try:
                    run.imported_count += int(import_document(state, meta, xml, subject, run=run))
                    run.heartbeat_at = timezone.now()
                    save_owned(run, fields=['imported_count', 'heartbeat_at', 'updated_at'])
                except InvoiceParseError as exc:
                    errors = True
                    InvoiceImportError.objects.update_or_create(
                        state=state,
                        tenant=state.tenant,
                        ksef_number=meta['ksefNumber'],
                        defaults={'raw_xml': xml, 'metadata': meta, 'error_code': str(exc)},
                    )
            if errors:
                raise KsefSyncError('DOCUMENT_IMPORT_FAILED')
            checkpoint = (
                package.get('lastPermanentStorageDate')
                if package['isTruncated']
                else package.get('permanentStorageHwmDate')
            )
            if not checkpoint:
                raise KsefSyncError('INVALID_PACKAGE')
            # An explicit upper bound can precede HWM; never skip the interval after it.
            checkpoint_date = parse_datetime(checkpoint)
            if not checkpoint_date:
                raise KsefSyncError('INVALID_PACKAGE')
            if not package['isTruncated']:
                checkpoint = min(checkpoint_date, run.created_at).isoformat()
            with transaction.atomic():
                InvoiceSyncState.objects.select_for_update().get(pk=state.pk)
                owned_run(run)
                state.checkpoints[subject] = checkpoint
                state.save(update_fields=['checkpoints', 'updated_at'])
                if not package['isTruncated']:
                    run.completed_subjects.append(subject)
                run.pending_export = {}
                run.attempts = 0
                transaction.on_commit(lambda: sync_invoices.apply_async(args=[run.pk], countdown=30))
                run.status = 'QUEUED'
                run.heartbeat_at = timezone.now()
                save_owned(run)
    except LeaseLost:
        return
    except (KsefSyncError, httpx.HTTPError, crypto.KsefDecryptionError, crypto.KsefEncryptionNotConfigured) as exc:
        if not InvoiceSyncRun.objects.filter(pk=run.pk, status='RUNNING', execution_token=run.execution_token).exists():
            return
        code = (
            exc.code
            if isinstance(exc, KsefSyncError)
            else 'SERVICE_UNAVAILABLE'
            if isinstance(exc, httpx.HTTPError)
            else 'DECRYPTION_FAILED'
        )
        delay = exc.retry_after if isinstance(exc, KsefSyncError) else 60 if isinstance(exc, httpx.HTTPError) else 0
        if code in ['EXPORT_EXPIRED', 'HWM_NOT_READY']:
            run.pending_export = {}
        if delay and run.attempts < 5:
            run.attempts += 1
            defer(run, max(delay, 30 * 2**run.attempts), code)
            return
        run.status = 'PARTIAL' if run.completed_subjects or run.imported_count else 'FAILED'
        run.error_code, run.finished_at = code, timezone.now()
        run.pending_export = {}
        save_owned(run)
        logger.warning('Invoice sync %s failed: %s', run.pk, code)
    except Exception as exc:
        if not InvoiceSyncRun.objects.filter(pk=run.pk, status='RUNNING', execution_token=run.execution_token).exists():
            return
        # Never report request URLs, XML, tokens or local variables here.
        run.status = 'PARTIAL' if run.completed_subjects or run.imported_count else 'FAILED'
        run.error_code, run.finished_at, run.pending_export = 'IMPORT_FAILED', timezone.now(), {}
        save_owned(run)
        logger.warning('Invoice sync %s failed: %s', run.pk, type(exc).__name__)


@shared_task(ignore_result=True)
def schedule_invoice_syncs():
    now = timezone.now()
    states = (
        InvoiceSyncState.objects.filter(environment=settings.KSEF_ENVIRONMENT, tenant__ksefcredential_set__isnull=False)
        .select_related('tenant')
        .distinct()
    )
    for state in states:
        if state.context_nip != state.tenant.nip:
            continue
        with transaction.atomic():
            InvoiceSyncState.objects.select_for_update().get(pk=state.pk)
            active = state.runs.filter(status__in=['QUEUED', 'RUNNING']).first()
            if active:
                stale_at = active.heartbeat_at or active.created_at
                if stale_at < now - timedelta(minutes=30):
                    sync_invoices.apply_async(args=[active.pk])
                continue
            latest = state.runs.order_by('-created_at').first()
            if latest and latest.created_at > now - timedelta(hours=2):
                continue
            run = InvoiceSyncRun.objects.create(state=state, tenant=state.tenant)
            transaction.on_commit(lambda run_id=run.pk: sync_invoices.delay(run_id))
