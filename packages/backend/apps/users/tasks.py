import importlib

from django.conf import settings
from celery import shared_task
from django.utils import timezone
from .models import PendingOTPLogin, PendingSocialAccountLink
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
