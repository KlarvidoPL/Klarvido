from celery import shared_task

from apps.multitenancy.cleanup import schedule_resource_cleanup, process_resource_cleanup
from apps.multitenancy.models import ResourceCleanup


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5, ignore_result=True)
def delete_document_file(file_path: str):
    """Compatibility for document cleanup tasks queued before the durable outbox."""
    job = schedule_resource_cleanup(ResourceCleanup.ResourceType.DOCUMENT_FILE, resource_path=file_path)
    process_resource_cleanup(job.pk)
