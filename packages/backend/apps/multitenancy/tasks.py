"""
Celery tasks for multitenancy app.

Handles async operations like action log exports.
"""

import csv
import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime

from celery import shared_task
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import cleanup
from .models import ResourceCleanup
from common.action_logging.service import log_action
from .constants import ActionActorType
from common.storages import get_exports_storage
from common.csv import spreadsheet_safe_cell

logger = logging.getLogger(__name__)


def log_export_result(export_job, operation):
    return log_action(
        tenant_id=export_job.tenant_id,
        action_type="UPDATE",
        entity_type="activity_log_export",
        entity_id=str(export_job.pk),
        actor_type=ActionActorType.SYSTEM_SCHEDULED,
        metadata={"operation": operation, "status": export_job.status, "log_count": export_job.log_count},
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def export_action_logs(self, export_id: str):
    """
    Process an action log export job.

    This task:
    1. Loads the export job configuration
    2. Queries all matching logs based on filters
    3. Creates CSV and JSON files with the data
    4. Zips the files
    5. Uploads to storage
    6. Creates a notification for the user
    """
    from .models import ActionLogExport, ActionLog, has_tenant_access, user_has_permission
    from apps.notifications.models import Notification

    # Load the export job
    try:
        export_job = ActionLogExport.objects.select_related("tenant", "requested_by").get(pk=export_id)
    except ActionLogExport.DoesNotExist:
        logger.error(f"Action log export {export_id} not found")
        return {"error": "Export job not found"}

    # Check if already processed
    if export_job.status in [ActionLogExport.Status.COMPLETED, ActionLogExport.Status.FAILED]:
        logger.info(f"Export {export_id} already {export_job.status}, skipping")
        return {"status": export_job.status}

    def requester_is_authorized():
        user = export_job.requested_by
        if user:
            user.refresh_from_db(fields=["is_active"])
        return bool(
            user
            and user.is_active
            and has_tenant_access(user, export_job.tenant)
            and user_has_permission(user, export_job.tenant, "security.logs.export")
        )

    def deny_export():
        export_job.status = ActionLogExport.Status.FAILED
        export_job.error_message = "permission_denied"
        export_job.completed_at = timezone.now()
        export_job.save(update_fields=["status", "error_message", "completed_at"])
        log_export_result(export_job, "export_failed")
        return {"error": "permission_denied"}

    # Recheck queued jobs: membership or permissions may have changed since enqueueing.
    if not requester_is_authorized():
        return deny_export()

    # Mark as processing
    export_job.status = ActionLogExport.Status.PROCESSING
    export_job.started_at = timezone.now()
    export_job.celery_task_id = self.request.id or ""
    export_job.save()

    try:
        # Build query based on filters
        filters = export_job.filters or {}
        qs = ActionLog.objects.filter(tenant_id=export_job.tenant_id)

        if filters.get("entity_type"):
            qs = qs.filter(entity_type=filters["entity_type"])
        if filters.get("action_type"):
            qs = qs.filter(action_type=filters["action_type"])
        if filters.get("actor_email"):
            qs = qs.filter(actor_email__icontains=filters["actor_email"])
        if filters.get("from_datetime"):
            from_dt = datetime.fromisoformat(filters["from_datetime"].replace("Z", "+00:00"))
            qs = qs.filter(created_at__gte=from_dt)
        if filters.get("to_datetime"):
            to_dt = datetime.fromisoformat(filters["to_datetime"].replace("Z", "+00:00"))
            qs = qs.filter(created_at__lte=to_dt)
        if filters.get("search"):
            from django.db.models import Q

            qs = qs.filter(Q(entity_name__icontains=filters["search"]) | Q(actor_email__icontains=filters["search"]))

        qs = qs.order_by("-created_at")

        # Collect all logs
        logs = list(
            qs.values(
                "id",
                "action_type",
                "entity_type",
                "entity_id",
                "entity_name",
                "actor_type",
                "actor_email",
                "changes",
                "metadata",
                "created_at",
            )
        )
        log_count = len(logs)

        logger.info(f"Exporting {log_count} logs for export {export_id}")

        # Prepare data for export
        export_data = []
        for log in logs:
            export_data.append(
                {
                    "id": str(log["id"]),
                    "action_type": log["action_type"],
                    "entity_type": log["entity_type"],
                    "entity_id": log["entity_id"],
                    "entity_name": log["entity_name"],
                    "actor_type": log["actor_type"],
                    "actor_email": log["actor_email"],
                    "changes": log["changes"],
                    "metadata": log["metadata"],
                    "created_at": log["created_at"].isoformat() if log["created_at"] else None,
                }
            )

        # Create CSV
        csv_buffer = io.StringIO()
        if export_data:
            # Flatten changes and metadata for CSV
            fieldnames = [
                "id",
                "created_at",
                "action_type",
                "entity_type",
                "entity_id",
                "entity_name",
                "actor_type",
                "actor_email",
                "changes",
                "metadata",
            ]
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in export_data:
                csv_row = row.copy()
                csv_row["changes"] = json.dumps(row["changes"], ensure_ascii=False)
                csv_row["metadata"] = json.dumps(row["metadata"], ensure_ascii=False)
                writer.writerow({key: spreadsheet_safe_cell(value) for key, value in csv_row.items()})

        csv_content = csv_buffer.getvalue()

        # Create JSON
        json_content = json.dumps(
            {
                "export_info": {
                    "tenant_id": str(export_job.tenant_id),
                    "tenant_name": export_job.tenant.name,
                    "exported_at": timezone.now().isoformat(),
                    "exported_by": export_job.requested_by.email,
                    "filters": filters,
                    "total_logs": log_count,
                },
                "logs": export_data,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("action_logs.csv", csv_content)
            zf.writestr("action_logs.json", json_content)

        zip_content = zip_buffer.getvalue()
        file_size = len(zip_content)

        # Generate unique filename with hash
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        content_hash = hashlib.sha256(zip_content).hexdigest()[:12]
        # Filename is relative to the storage location ('exports/')
        filename = f"action_logs/{export_job.tenant_id}/{timestamp}_{content_hash}.zip"

        if not requester_is_authorized():
            return deny_export()

        # Upload to storage using exports-specific backend (enforces SigV4 for R2)
        storage = get_exports_storage()
        saved_path = storage.save(filename, ContentFile(zip_content))
        logger.info(f"Saved export to {saved_path}")

        # Update export job
        export_job.status = ActionLogExport.Status.COMPLETED
        export_job.completed_at = timezone.now()
        export_job.file_path = saved_path
        export_job.file_size = file_size
        export_job.log_count = log_count
        export_job.save()

        if not requester_is_authorized():
            storage.delete(saved_path)
            export_job.file_path = ""
            export_job.save(update_fields=["file_path"])
            return deny_export()

        log_export_result(export_job, "export_completed")

        # Create notification for the user
        download_url = export_job.get_download_url()
        Notification.objects.create(
            user=export_job.requested_by,
            type="ACTION_LOG_EXPORT_READY",
            data={
                "export_id": str(export_job.id),
                "tenant_name": export_job.tenant.name,
                "log_count": log_count,
                "file_size": file_size,
                "download_url": download_url,
            },
        )

        logger.info(f"Export {export_id} completed successfully with {log_count} logs")
        return {
            "status": "completed",
            "log_count": log_count,
            "file_path": saved_path,
        }

    except Exception as exc:
        logger.exception(f"Export {export_id} failed: {exc}")
        export_job.status = ActionLogExport.Status.FAILED
        export_job.error_message = str(exc)
        export_job.completed_at = timezone.now()
        export_job.save()
        log_export_result(export_job, "export_failed")

        # Notify user of failure
        Notification.objects.create(
            user=export_job.requested_by,
            type="ACTION_LOG_EXPORT_FAILED",
            data={
                "export_id": str(export_job.id),
                "tenant_name": export_job.tenant.name,
                "error": str(exc),
            },
        )

        raise self.retry(exc=exc)


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5, ignore_result=True)
def delete_tenant_files(file_paths: list[str], tenant_id: str):
    """Compatibility for queued tasks from before the transactional cleanup outbox."""
    with transaction.atomic():
        jobs = [
            cleanup.schedule_resource_cleanup(
                ResourceCleanup.ResourceType.EXPORT_FILE, organization_id=tenant_id, resource_path=path
            )
            for path in file_paths
        ]
        jobs.append(
            cleanup.schedule_resource_cleanup(ResourceCleanup.ResourceType.BACKUP_KEY, organization_id=tenant_id)
        )
    for job in jobs:
        cleanup.process_resource_cleanup(job.pk)


@shared_task(ignore_result=True)
def process_resource_cleanup(cleanup_id: str):
    return cleanup.process_resource_cleanup(cleanup_id)


@shared_task(ignore_result=True)
def process_due_resource_cleanups():
    cleanup.process_due_resource_cleanups()
