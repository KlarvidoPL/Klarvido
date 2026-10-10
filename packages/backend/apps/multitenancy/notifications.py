from common import emails
from apps.notifications import sender
from apps.users.notifications import get_user_language
from . import constants
from . import models
from . import email_serializers


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

    def deliver(self):
        """Confirm actual delivery rather than merely submitting another task."""
        serializer = self.get_serializer(data=self.data)
        serializer.is_valid(raise_exception=True)
        result = emails.deliver_email_message(self.to, self.name, serializer.data, self.lang)
        if result.get('sent_emails_count', 0) < 1:
            raise RuntimeError('Email delivery was not confirmed')


def get_user_display_name(user) -> str:
    return str(user.profile) or str(user)


def send_tenant_invitation_notification(tenant_membership: models.TenantMembership, membership_id: str, token: str):
    if tenant_membership.user:
        sender.send_notification(
            user=tenant_membership.user,
            type=constants.Notification.TENANT_INVITATION_CREATED.value,
            data={
                "id": membership_id,
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
