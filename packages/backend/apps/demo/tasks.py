from celery import shared_task

from .models import DocumentDemoItem


@shared_task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5, ignore_result=True)
def delete_document_file(file_path: str):
    """Delete through the document's storage backend, including S3, after DB commit."""
    storage = DocumentDemoItem._meta.get_field('file').storage
    storage.delete(file_path)
