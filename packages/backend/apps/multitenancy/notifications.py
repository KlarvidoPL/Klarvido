import logging

from common import emails
from apps.notifications import sender
from apps.users.notifications import get_user_language
from . import constants
from . import models
from . import email_serializers

logger = logging.getLogger(__name__)


class TenantInvitationEmail(emails.Email):
    name = "TENANT_INVITATION"
    serializer_class = email_serializers.TenantInvitationEmailSerializer

    def __init__(self, to, data=None, user=None):
        """
        Initialize tenant invitation email.

        Args:
            to: Email address to send to
            data: Email data
            user: Optional user object to get language preference from
        """
        lang = get_user_language(user) if user else emails.DEFAULT_EMAIL_LANGUAGE
        super().__init__(to=to, data=data, lang=lang)


class TenantDeletedEmail(emails.Email):
    name = "TENANT_DELETED"
    serializer_class = email_serializers.TenantDeletedEmailSerializer

    def __init__(self, user, data=None):
        super().__init__(to=user.email, data=data, lang=get_user_language(user))


def get_user_display_name(user) -> str:
    return str(user.profile) or str(user)


def send_tenant_deleted_notifications(tenant_name: str, deleter, recipients):
    """
    Tell the members that an organization is gone. Called after the delete has been committed, so everything needed is
    passed in rather than read from the (deleted) tenant.

    The other members get an in-app notification plus an email; the member who deleted it gets a confirmation email only
    (they just did it in the app, but an email leaves a trail should their account ever be misused).
    """
    deleted_by = get_user_display_name(deleter) if deleter else ""
    for user in recipients:
        if deleter and user.pk == deleter.pk:
            continue
        try:
            sender.send_notification(
                user=user,
                type=constants.Notification.TENANT_DELETED.value,
                data={"tenant_name": tenant_name, "name": deleted_by},
                issuer=deleter,
            )
            TenantDeletedEmail(
                user, data={"tenant_name": tenant_name, "deleted_by": deleted_by, "is_deleter": False}
            ).send()
        except Exception:  # One member failing must not stop the others from being told
            logger.exception("Failed to notify a member about a deleted organization")

    if deleter and deleter.email:
        try:
            TenantDeletedEmail(
                deleter, data={"tenant_name": tenant_name, "deleted_by": deleted_by, "is_deleter": True}
            ).send()
        except Exception:
            logger.exception("Failed to send the organization deletion confirmation")


def send_tenant_invitation_notification(tenant_membership: models.TenantMembership, membership_id: str, token: str):
    if tenant_membership.user:
        sender.send_notification(
            user=tenant_membership.user,
            type=constants.Notification.TENANT_INVITATION_CREATED.value,
            data={
                "id": membership_id,
                "token": token,
                "tenant_name": tenant_membership.tenant.name,
            },
            issuer=tenant_membership.creator,
        )


def send_accepted_tenant_invitation_notification(tenant_membership: models.TenantMembership, membership_id: str):
    if tenant_membership.creator:
        sender.send_notification(
            user=tenant_membership.creator,
            type=constants.Notification.TENANT_INVITATION_ACCEPTED.value,
            data={
                "id": membership_id,
                "name": str(tenant_membership.user.profile) or str(tenant_membership.user),
                "tenant_name": str(tenant_membership.tenant),
            },
            issuer=tenant_membership.user,
        )


def send_declined_tenant_invitation_notification(tenant_membership: models.TenantMembership, membership_id: str):
    if tenant_membership.creator:
        sender.send_notification(
            user=tenant_membership.creator,
            type=constants.Notification.TENANT_INVITATION_DECLINED.value,
            data={
                "id": membership_id,
                "name": str(tenant_membership.user.profile) or str(tenant_membership.user),
                "tenant_name": str(tenant_membership.tenant),
            },
            issuer=tenant_membership.user,
        )
