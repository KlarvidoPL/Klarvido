"""Durable, independent delivery of organization deletion emails and in-app notices."""

import logging
import uuid
from datetime import timedelta

from celery import current_app
from django.db import transaction
from django.utils import timezone

from apps.notifications.managers import DISABLED_NOTIFICATION_TYPES
from apps.notifications.sender import get_enabled_strategies
from apps.notifications.strategies import InAppNotificationStrategy
from apps.users.notifications import get_user_language
from .constants import Notification
from .models import OrganizationDeletionDelivery
from . import notifications

logger = logging.getLogger(__name__)
LEASE_DURATION = timedelta(minutes=10)


def schedule_deletion_notifications(organization_id, tenant_name, deleter, recipients):
    """Persist inside the deletion transaction; never depend on a deleted tenant FK."""
    deleted_by = notifications.get_user_display_name(deleter) if deleter else ''
    ids = []
    users = {str(user.pk): user for user in recipients if not deleter or user.pk != deleter.pk}
    if deleter:
        users[str(deleter.pk)] = deleter
    for user in users.values():
        is_deleter = bool(deleter and user.pk == deleter.pk)
        channels = [] if is_deleter else [OrganizationDeletionDelivery.Channel.IN_APP]
        if user.email:
            channels.append(OrganizationDeletionDelivery.Channel.EMAIL)
        for channel in channels:
            delivery = OrganizationDeletionDelivery.objects.create(
                organization_id=str(organization_id),
                recipient=user,
                issuer=deleter,
                channel=channel,
                recipient_email=user.email,
                language=get_user_language(user),
                payload={'tenant_name': tenant_name, 'deleted_by': deleted_by, 'is_deleter': is_deleter},
            )
            ids.append(str(delivery.pk))
    if ids:
        transaction.on_commit(lambda: enqueue_deletion_notifications(ids))


def enqueue_deletion_notifications(ids):
    try:
        current_app.send_task('apps.multitenancy.tasks.process_deletion_notifications', args=[ids], retry=False)
    except Exception as exc:
        logger.warning('Deletion notification queue failed: error_type=%s', type(exc).__name__)
        try:
            OrganizationDeletionDelivery.objects.filter(pk__in=ids, attempts=0, completed_at__isnull=True).update(
                last_error='queue_submission_failed', updated_at=timezone.now()
            )
        except Exception as persist_exc:
            logger.warning('Could not record notification queue failure: error_type=%s', type(persist_exc).__name__)


def _complete(delivery, token):
    return bool(
        OrganizationDeletionDelivery.objects.filter(
            pk=delivery.pk, lease_token=token, completed_at__isnull=True
        ).update(lease_token=None, completed_at=timezone.now(), last_error='', updated_at=timezone.now())
    )


def process_deletion_delivery(delivery_id):
    token = uuid.uuid4()
    delivery = None
    try:
        with transaction.atomic():
            delivery = (
                OrganizationDeletionDelivery.objects.select_for_update(skip_locked=True)
                .filter(pk=delivery_id, completed_at__isnull=True, next_attempt_at__lte=timezone.now())
                .first()
            )
            if delivery is None:
                return False
            delivery.attempts += 1
            delivery.lease_token = token
            delivery.next_attempt_at = timezone.now() + LEASE_DURATION
            delivery.save(update_fields=['attempts', 'lease_token', 'next_attempt_at', 'updated_at'])
            if delivery.recipient_id is None:
                # Do not notify a deleted account. SET_NULL preserves outcome history.
                return _complete(delivery, token)
        if delivery.channel == OrganizationDeletionDelivery.Channel.IN_APP:
            with transaction.atomic():
                owned = (
                    OrganizationDeletionDelivery.objects.select_for_update()
                    .filter(pk=delivery.pk, lease_token=token, completed_at__isnull=True)
                    .first()
                )
                if owned is None:
                    return False
                if owned.recipient_id is None:
                    return _complete(owned, token)
                notice_type = Notification.TENANT_DELETED.value
                if (
                    notice_type not in DISABLED_NOTIFICATION_TYPES
                    and InAppNotificationStrategy in get_enabled_strategies()
                    and InAppNotificationStrategy.should_send_notification(owned.recipient, notice_type)
                ):
                    # Creation and completion commit together under the delivery lock.
                    # A crash/retry cannot create a duplicate in-app notification.
                    InAppNotificationStrategy.send_notification(
                        owned.recipient,
                        notice_type,
                        {'tenant_name': delivery.payload['tenant_name'], 'name': delivery.payload['deleted_by']},
                        owned.issuer,
                    )
                return _complete(delivery, token)
        if delivery.channel != OrganizationDeletionDelivery.Channel.EMAIL:
            raise ValueError('Unknown deletion notification channel')

        email = notifications.TenantDeletedEmail(delivery.recipient, data=delivery.payload)
        email.to = delivery.recipient_email
        email.lang = delivery.language
        email.deliver()
        return _complete(delivery, token)
    except Exception as exc:
        if delivery is None:
            raise
        pending = OrganizationDeletionDelivery.objects.filter(
            pk=delivery.pk, completed_at__isnull=True, lease_token=token
        )
        delay = min(3600, 30 * 2 ** min(delivery.attempts - 1, 7))
        pending.update(
            attempts=delivery.attempts,
            lease_token=None,
            next_attempt_at=timezone.now() + timedelta(seconds=delay),
            last_error=type(exc).__name__[:120],
            updated_at=timezone.now(),
        )
        logger.warning(
            'Deletion notification will retry: delivery_id=%s error_type=%s', delivery.pk, type(exc).__name__
        )
        return False


def process_due_deletion_notifications():
    ids = list(
        OrganizationDeletionDelivery.objects.filter(completed_at__isnull=True, next_attempt_at__lte=timezone.now())
        .order_by('next_attempt_at', 'created_at')
        .values_list('pk', flat=True)[:100]
    )
    for delivery_id in ids:
        process_deletion_delivery(delivery_id)
