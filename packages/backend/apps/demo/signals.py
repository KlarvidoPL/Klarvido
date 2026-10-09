from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from . import models
from . import notifications
from .tasks import delete_document_file


@receiver(post_delete, sender=models.DocumentDemoItem)
def remove_document_file(sender, instance, **kwargs):
    # Django cascades and queryset deletion bypass Model.delete(). Keep the path
    # before the row disappears, and never remove a file for a rolled-back delete.
    if instance.file.name:
        file_path = instance.file.name
        transaction.on_commit(lambda: delete_document_file.delay(file_path))


@receiver(post_save, sender=models.CrudDemoItem)
def notify_about_entry(sender, instance: models.CrudDemoItem, created, update_fields, **kwargs):
    if created:
        notifications.send_new_entry_created_notification(instance)
    else:
        notifications.send_entry_updated_notification(instance)
