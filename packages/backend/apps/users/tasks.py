import importlib
from datetime import timedelta

from django.conf import settings
from celery import shared_task
from django.utils import timezone
from .models import (
    PasswordFailureBudget,
    PendingOTPLogin,
    PendingSocialAccountLink,
    SecurityEmailOutbox,
    SignupEmailCooldown,
    ResetEmailLimit,
)
from apps.sso.models import SSOAuditLog
from .services.security import AUTH_EVENTS, process_outbox
from .services.export.services import user as user_services

module_name, package = settings.LAMBDA_TASKS_BASE_HANDLER.rsplit(".", maxsplit=1)
LambdaTask = getattr(importlib.import_module(module_name), package)


class ExportUserData(LambdaTask):
    def __init__(self):
        super().__init__(name="EXPORT_USER_DATA", source="backend.export_user")


@shared_task(bind=True)
def export_user_data(self, user_ids, admin_email):
    user_services.process_user_data_export(user_ids=user_ids, admin_email=admin_email)


@shared_task(ignore_result=True)
def cleanup_social_link_confirmations():
    ids = list(
        PendingSocialAccountLink.objects.filter(expires_at__lt=timezone.now()).values_list('pk', flat=True)[:1000]
    )
    count, _ = PendingSocialAccountLink.objects.filter(pk__in=ids).delete()
    return count


@shared_task(ignore_result=True)
def cleanup_pending_otp_logins():
    ids = list(PendingOTPLogin.objects.filter(expires_at__lt=timezone.now()).values_list('pk', flat=True)[:1000])
    count, _ = PendingOTPLogin.objects.filter(pk__in=ids).delete()
    return count


@shared_task(ignore_result=True)
def deliver_security_emails():
    process_outbox()


@shared_task(ignore_result=True)
def cleanup_authentication_records():
    cutoff = timezone.now() - timedelta(days=max(1, settings.AUTH_AUDIT_RETENTION_DAYS))
    # Password-failure-budget rows (E05) are short-lived lockout counters, not audit history -
    # a day of inactivity is long past even the longest (60-minute) cooldown, so purge on a much
    # shorter horizon than the other, long-retention records cleaned up below.
    budget_cutoff = timezone.now() - timedelta(days=1)
    backlog = False
    for model, query in (
        (SSOAuditLog, SSOAuditLog.objects.filter(event_type__in=AUTH_EVENTS, created_at__lt=cutoff)),
        (SecurityEmailOutbox, SecurityEmailOutbox.objects.filter(created_at__lt=cutoff)),
        (SignupEmailCooldown, SignupEmailCooldown.objects.filter(day_started_at__lt=cutoff)),
        (ResetEmailLimit, ResetEmailLimit.objects.exclude(key="global").filter(window_started_at__lt=cutoff)),
        (PasswordFailureBudget, PasswordFailureBudget.objects.filter(last_failure_at__lt=budget_cutoff)),
    ):
        for _ in range(10):
            ids = list(query.values_list('pk', flat=True)[:1000])
            if not ids:
                break
            model.objects.filter(pk__in=ids).delete()
        backlog = backlog or query.exists()
    if backlog:
        # Keep each job bounded while draining heavy traffic instead of accumulating old records.
        cleanup_authentication_records.apply_async(countdown=60)
