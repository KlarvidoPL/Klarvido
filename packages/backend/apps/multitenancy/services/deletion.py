"""Shared organization deletion workflow for GraphQL and Django Admin."""

import json
import logging

from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.finances.services import subscriptions
from apps.finances.serializers import CancelTenantActiveSubscriptionSerializer
from common.action_logging.service import get_request_actor, log_delete
from common.graphql.acl.decorators import PERMISSION_DENIED_MESSAGE
from .. import models
from ..deletion_notifications import schedule_deletion_notifications
from ..cleanup import schedule_organization_prefix_cleanup, schedule_resource_cleanup
from ..constants import ActionActorType, TenantType

logger = logging.getLogger(__name__)


def delete_organization(tenant_id, request, *, via_admin=False):
    """Lock, authorize, snapshot cleanup/audit work and delete in one transaction."""
    actor_type = (
        (ActionActorType.SUPERUSER if request.user.is_superuser else ActionActorType.USER)
        if via_admin
        else get_request_actor(request)
    )
    tenant_pk = str(tenant_id)
    deleter = request.user
    with transaction.atomic():
        # Workers acquire this same lock before encrypting/uploading and recording
        # file paths. Collect paths only after any in-flight publisher commits.
        tenant = models.Tenant.objects.select_for_update().filter(pk=tenant_pk).first()
        if tenant is None:
            raise PermissionDenied(PERMISSION_DENIED_MESSAGE)
        # Acquiring the lock can wait for an upload. Recheck authorization
        # rather than relying only on the permission check before that wait.
        if tenant.type == TenantType.DEFAULT:
            raise ValidationError('Cannot delete default type tenant.')
        if via_admin:
            if not (deleter.is_active and deleter.is_staff and deleter.has_perm('multitenancy.delete_tenant')):
                raise PermissionDenied(PERMISSION_DENIED_MESSAGE)
        elif not models.has_tenant_access(deleter, tenant) or not models.user_has_permission(
            deleter, tenant, 'org.delete'
        ):
            raise PermissionDenied(PERMISSION_DENIED_MESSAGE)
        tenant_name = tenant.name
        members = [
            membership.user
            for membership in tenant.user_memberships.filter(is_accepted=True, user__isnull=False).select_related(
                "user__profile"
            )
        ]
        file_paths = [
            *tenant.backuprecord_set.exclude(file_path="").values_list("file_path", flat=True),
            *tenant.action_log_exports.exclude(file_path="").values_list("file_path", flat=True),
        ]

        log_delete(
            tenant_id=tenant.pk,
            entity_type="tenant",
            instance=tenant,
            actor_user=request.user,
            actor_type=actor_type,
        )

        try:
            schedule = subscriptions.get_schedule(tenant)
            if schedule:
                cancel_subscription_serializer = CancelTenantActiveSubscriptionSerializer(instance=schedule, data={})
                if cancel_subscription_serializer.is_valid():
                    cancel_subscription_serializer.save()
        except Exception as e:
            logger.warning(f"Failed to cancel subscription for tenant {tenant.pk} during deletion: {e}")

        LogEntry.objects.create(
            user_id=request.user.pk,
            content_type=ContentType.objects.get_for_model(models.Tenant),
            object_id=tenant_pk,
            object_repr=tenant_name[:200],
            action_flag=DELETION,
            change_message=json.dumps(
                {
                    "operation": "organization_deleted",
                    "organization_id": tenant_pk,
                    "organization_name": tenant_name,
                    "actor_email": deleter.email,
                    "actor_type": actor_type,
                }
            ),
        )
        for file_path in file_paths:
            schedule_resource_cleanup(
                models.ResourceCleanup.ResourceType.EXPORT_FILE,
                organization_id=tenant_pk,
                resource_path=file_path,
            )
        schedule_resource_cleanup(models.ResourceCleanup.ResourceType.BACKUP_KEY, organization_id=tenant_pk)
        schedule_organization_prefix_cleanup(tenant_pk)
        schedule_deletion_notifications(tenant_pk, tenant_name, deleter, members)
        tenant.delete()
