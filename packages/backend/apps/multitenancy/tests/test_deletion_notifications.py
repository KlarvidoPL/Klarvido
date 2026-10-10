import uuid
from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.strategies import InAppNotificationStrategy
from ..deletion_notifications import (
    LEASE_DURATION,
    process_deletion_delivery,
    process_due_deletion_notifications,
    schedule_deletion_notifications,
)
from ..models import OrganizationDeletionDelivery

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def queue(mocker):
    return mocker.patch('apps.multitenancy.deletion_notifications.current_app.send_task')


def deliveries(actor, member):
    schedule_deletion_notifications('deleted-org', 'Deleted organization', actor, [actor, member])
    return OrganizationDeletionDelivery.objects.all()


def test_notifications_are_transactional_and_independent(user, user_factory, queue, django_capture_on_commit_callbacks):
    member = user_factory()
    with django_capture_on_commit_callbacks(execute=True):
        rows = deliveries(user, member)
        assert rows.count() == 3
        queue.assert_not_called()
    queue.assert_called_once()
    assert rows.filter(recipient=user, channel='in_app').count() == 0
    assert rows.filter(recipient=member).count() == 2
    assert not Notification.objects.filter(type='TENANT_DELETED').exists()


def test_rollback_discards_delivery_work(user, user_factory, queue, django_capture_on_commit_callbacks):
    member = user_factory()
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError), transaction.atomic():
        deliveries(user, member)
        raise RuntimeError('rollback')
    assert not OrganizationDeletionDelivery.objects.exists()
    queue.assert_not_called()


def test_broker_failure_is_recovered_by_periodic_sweep(
    user, user_factory, queue, mocker, django_capture_on_commit_callbacks
):
    member = user_factory()
    queue.side_effect = ConnectionError('broker offline')
    with django_capture_on_commit_callbacks(execute=True):
        rows = deliveries(user, member)
    assert set(rows.values_list('last_error', flat=True)) == {'queue_submission_failed'}
    email = mocker.patch('apps.multitenancy.notifications.TenantDeletedEmail.deliver')
    process_due_deletion_notifications()
    assert rows.filter(completed_at__isnull=True).count() == 0
    assert email.call_count == 2
    assert Notification.objects.filter(user=member, type='TENANT_DELETED').count() == 1


def test_email_failure_does_not_block_in_app_or_other_recipients(user, user_factory, mocker):
    member = user_factory()
    rows = deliveries(user, member)
    backend = mocker.patch('common.emails.deliver_email_message')

    def deliver(to, *args):
        if to == member.email:
            raise OSError('secret smtp details')
        return {'sent_emails_count': 1}

    backend.side_effect = deliver
    process_due_deletion_notifications()
    failed = rows.get(recipient=member, channel='email')
    assert failed.completed_at is None
    assert failed.last_error == 'OSError'
    assert failed.attempts == 1
    assert rows.filter(completed_at__isnull=False).count() == 2
    assert Notification.objects.filter(user=member, type='TENANT_DELETED').count() == 1
    assert not process_deletion_delivery(failed.pk)  # Respect backoff.
    backend.side_effect = None
    backend.return_value = {'sent_emails_count': 1}
    OrganizationDeletionDelivery.objects.filter(pk=failed.pk).update(next_attempt_at=timezone.now())
    assert process_deletion_delivery(failed.pk)
    assert backend.call_count == 3  # Successful channels were not retried.


def test_in_app_failure_rolls_back_creation_and_can_retry_once(user, user_factory, mocker):
    member = user_factory()
    row = deliveries(user, member).get(recipient=member, channel='in_app')
    actual_send = InAppNotificationStrategy.send_notification

    def fail_after_insert(*args):
        actual_send(*args)
        raise RuntimeError('after insert')

    send = mocker.patch.object(InAppNotificationStrategy, 'send_notification', side_effect=fail_after_insert)
    assert not process_deletion_delivery(row.pk)
    assert not Notification.objects.filter(user=member, type='TENANT_DELETED').exists()
    row.refresh_from_db()
    assert row.attempts == 1
    assert row.last_error == 'RuntimeError'
    send.side_effect = actual_send
    OrganizationDeletionDelivery.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now())
    assert process_deletion_delivery(row.pk)
    assert not process_deletion_delivery(row.pk)
    assert Notification.objects.filter(user=member, type='TENANT_DELETED').count() == 1


def test_worker_reclaims_expired_lease_and_fences_old_outcome(user, mocker):
    schedule_deletion_notifications('deleted-org', 'Deleted organization', user, [])
    row = OrganizationDeletionDelivery.objects.get()
    email = mocker.patch('apps.multitenancy.notifications.TenantDeletedEmail.deliver')

    def reclaim():
        OrganizationDeletionDelivery.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now() - LEASE_DURATION)
        email.side_effect = OSError('replacement failed')
        assert not process_deletion_delivery(row.pk)

    email.side_effect = reclaim
    assert not process_deletion_delivery(row.pk)
    row.refresh_from_db()
    assert row.completed_at is None
    assert row.attempts == 2
    assert row.last_error == 'OSError'


def test_unexpired_lease_cannot_be_claimed(user, mocker):
    schedule_deletion_notifications('deleted-org', 'Deleted organization', user, [])
    row = OrganizationDeletionDelivery.objects.get()
    OrganizationDeletionDelivery.objects.filter(pk=row.pk).update(
        lease_token=uuid.uuid4(), next_attempt_at=timezone.now() + timedelta(minutes=1)
    )
    email = mocker.patch('apps.multitenancy.notifications.TenantDeletedEmail.deliver')
    assert not process_deletion_delivery(row.pk)
    email.assert_not_called()


def test_email_requires_actual_acceptance_and_does_not_enqueue_another_task(user, mocker):
    schedule_deletion_notifications('deleted-org', 'Deleted organization', user, [])
    row = OrganizationDeletionDelivery.objects.get()
    backend = mocker.patch('common.emails.deliver_email_message', return_value={'sent_emails_count': 0})
    ordinary_queue = mocker.patch('common.emails.send_email.apply_async')
    assert not process_deletion_delivery(row.pk)
    row.refresh_from_db()
    assert row.last_error == 'RuntimeError'
    assert row.completed_at is None
    ordinary_queue.assert_not_called()
    backend.assert_called_once()


def test_recipient_address_and_language_are_snapshotted(user, mocker):
    user.profile.language = 'pl'
    user.profile.save(update_fields=['language'])
    original_email = user.email
    schedule_deletion_notifications('deleted-org', 'Deleted organization', user, [])
    row = OrganizationDeletionDelivery.objects.get()
    user.email = 'changed@example.test'
    user.save(update_fields=['email'])
    backend = mocker.patch('common.emails.deliver_email_message', return_value={'sent_emails_count': 1})
    assert process_deletion_delivery(row.pk)
    assert backend.call_args.args[0] == original_email
    assert backend.call_args.args[3] == 'pl'


def test_removed_recipient_is_skipped(user_factory, mocker):
    user = user_factory()
    schedule_deletion_notifications('deleted-org', 'Deleted organization', user, [])
    row = OrganizationDeletionDelivery.objects.get()
    user.delete()
    backend = mocker.patch('common.emails.deliver_email_message')
    assert process_deletion_delivery(row.pk)
    backend.assert_not_called()
    row.refresh_from_db()
    assert row.completed_at is not None
    assert row.recipient_id is None


def test_disabled_in_app_channel_is_respected(user, user_factory, mocker):
    member = user_factory()
    row = deliveries(user, member).get(recipient=member, channel='in_app')
    mocker.patch('apps.multitenancy.deletion_notifications.get_enabled_strategies', return_value=[])
    assert process_deletion_delivery(row.pk)
    assert not Notification.objects.filter(user=member, type='TENANT_DELETED').exists()
