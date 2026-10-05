import hashid_field
from django.db import models, transaction
from django.utils import timezone

from common.models import TenantDependentModelMixin, TimestampedMixin


class InvoiceCategory(TenantDependentModelMixin, TimestampedMixin):
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant', 'name'], name='invoice_category_tenant_name')]


class Invoice(TenantDependentModelMixin, TimestampedMixin):
    _backup_include_relations = True
    id = hashid_field.HashidAutoField(primary_key=True)
    environment = models.CharField(max_length=8)
    context_nip = models.CharField(max_length=20)
    ksef_number = models.CharField(max_length=64)
    number = models.CharField(max_length=256)
    direction = models.CharField(max_length=8)
    kind = models.CharField(max_length=20)
    issue_date = models.DateField()
    permanent_storage_date = models.DateTimeField()
    seller_name = models.CharField(max_length=512, blank=True)
    seller_nip = models.CharField(max_length=20, blank=True)
    buyer_name = models.CharField(max_length=512, blank=True)
    buyer_nip = models.CharField(max_length=20, blank=True)
    currency = models.CharField(max_length=3)
    net = models.DecimalField(max_digits=24, decimal_places=2)
    vat = models.DecimalField(max_digits=24, decimal_places=2)
    gross = models.DecimalField(max_digits=24, decimal_places=2)
    category = models.ForeignKey(InvoiceCategory, null=True, blank=True, on_delete=models.SET_NULL)
    corrected_ksef_numbers = models.JSONField(default=list, blank=True)
    raw_xml = models.TextField()

    @classmethod
    def _after_backup_restore(cls, tenant_id):
        # Restoring an old snapshot must not retain a checkpoint beyond its documents.
        with transaction.atomic():
            states = InvoiceSyncState.objects.select_for_update().filter(tenant_id=tenant_id)
            for state in states:
                state.runs.filter(status__in=['QUEUED', 'RUNNING']).update(
                    status='FAILED', error_code='RESTORE_REQUIRED', pending_export={}, finished_at=timezone.now()
                )
                state.checkpoints = {}
                state.save(update_fields=['checkpoints', 'updated_at'])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'environment', 'ksef_number'], name='invoice_ksef_unique')
        ]
        indexes = [models.Index(fields=['tenant', 'environment', 'issue_date'])]
        ordering = ['-issue_date', '-pk']


class InvoiceLine(TenantDependentModelMixin):
    _backup_include_relations = True
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    position = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=256, blank=True)
    quantity = models.DecimalField(max_digits=24, decimal_places=8, null=True)
    unit_price = models.DecimalField(max_digits=24, decimal_places=8, null=True)
    net = models.DecimalField(max_digits=24, decimal_places=2, null=True)
    vat_rate = models.CharField(max_length=32, blank=True)


class InvoiceSyncState(TenantDependentModelMixin, TimestampedMixin):
    environment = models.CharField(max_length=8)
    context_nip = models.CharField(max_length=20)
    start_date = models.DateTimeField()
    checkpoints = models.JSONField(default=dict)
    last_success_at = models.DateTimeField(null=True)
    _backup_excluded = True

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'environment', 'context_nip'], name='invoice_sync_context')
        ]


class InvoiceSyncRun(TenantDependentModelMixin, TimestampedMixin):
    state = models.ForeignKey(InvoiceSyncState, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=16, default='QUEUED')
    imported_count = models.PositiveIntegerField(default=0)
    completed_subjects = models.JSONField(default=list)
    error_code = models.CharField(max_length=64, blank=True)
    pending_export = models.JSONField(default=dict)
    attempts = models.PositiveIntegerField(default=0)
    execution_token = models.UUIDField(null=True)
    heartbeat_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    _backup_excluded = True

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['state'], condition=models.Q(status__in=['QUEUED', 'RUNNING']), name='one_active_invoice_sync'
            )
        ]


class InvoiceImportError(TenantDependentModelMixin, TimestampedMixin):
    state = models.ForeignKey(InvoiceSyncState, on_delete=models.CASCADE)
    ksef_number = models.CharField(max_length=64)
    raw_xml = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    error_code = models.CharField(max_length=64)
    _backup_excluded = True

    class Meta:
        constraints = [models.UniqueConstraint(fields=['state', 'ksef_number'], name='invoice_import_error_unique')]
