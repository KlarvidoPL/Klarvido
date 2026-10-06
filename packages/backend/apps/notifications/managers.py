from django.db import models
from django.utils import timezone

DISABLED_NOTIFICATION_TYPES = ("SSO_CONNECTION_ACTIVATED", "SSO_CONNECTION_DEACTIVATED", "SSO_LOGIN_FROM_NEW_DEVICE")


class NotificationQuerySet(models.QuerySet):
    def filter_by_user(self, user):
        return self.filter(user=user)

    def filter_unread(self):
        return self.filter(read_at__isnull=True)

    def mark_read(self):
        self.update(read_at=timezone.now())


class NotificationManager(models.Manager.from_queryset(NotificationQuerySet)):
    def get_queryset(self):
        # Preserve historical records, but do not expose retired SSO notifications.
        return super().get_queryset().exclude(type__in=DISABLED_NOTIFICATION_TYPES)
