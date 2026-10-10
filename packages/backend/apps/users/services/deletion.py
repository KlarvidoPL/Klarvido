"""Account deletion: preserve shared content and persist external cleanup before commit."""

from django.db import transaction
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.multitenancy.constants import ActionType, TenantType
from apps.notifications.models import Notification
from apps.multitenancy.models import ActionLog, ResourceCleanup, Tenant, TenantMembership
from apps.multitenancy.cleanup import schedule_resource_cleanup
from apps.multitenancy.services.ownership import owner_memberships
from apps.multitenancy.services.deletion import delete_organization
from apps.sso.services import passkey_management
from apps.sso.services.sessions import SessionService
from apps.users import jwt
from apps.users.models import AccountDeletion, SecurityEmailOutbox, User, UserAvatar
from apps.demo.models import DocumentDemoItem
from apps.users.services.security import enqueue_email, record
from common.action_logging.service import log_action


def deletion_blockers(user):
    tenants = Tenant.objects.filter(type=TenantType.ORGANIZATION, user_memberships__user=user).distinct()
    return [
        tenant
        for tenant in tenants
        if owner_memberships(tenant.pk).filter(user=user).exists()
        and not owner_memberships(tenant.pk).exclude(user=user).exists()
    ]


@transaction.atomic
def delete_account(user_id, request, *, via_admin=False, restoration=False):
    # Organization first, account second: membership operations share this order.
    tenant_ids = Tenant.objects.filter(Q(user_memberships__user_id=user_id) | Q(creator_id=user_id)).values('pk')
    tenants = list(Tenant.objects.select_for_update().filter(pk__in=tenant_ids).order_by('pk'))
    if User.objects.filter(pk=user_id, is_superuser=True).exists():
        # Serialize concurrent administrator departures as well as organization ownership.
        list(User.objects.select_for_update().filter(is_superuser=True, is_active=True).order_by('pk'))
    account = User.objects.select_for_update().get(pk=user_id)
    actor = User.objects.select_for_update().get(pk=request.user.pk)
    if via_admin or restoration:
        if not actor.is_active or not actor.is_superuser:
            raise PermissionDenied('permission_denied')
    elif actor.pk != account.pk:
        raise PermissionDenied('permission_denied')
    grant = None if restoration else passkey_management.require_grant(request, actor, 'account_delete')
    if (
        not restoration
        and actor.otp_enabled
        and actor.otp_verified
        and getattr(request, '_account_deletion_otp', None) != (str(actor.pk), actor.otp_last_used_code_hash)
    ):
        raise ValidationError({'otp_token': ['Fresh OTP confirmation is required.']})
    if not restoration and deletion_blockers(account):
        raise ValidationError({'confirmation': ['Transfer ownership or delete your organizations first.']})
    if (
        account.is_superuser
        and not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=account.pk).exists()
    ):
        raise ValidationError({'confirmation': ['The last active administrator cannot delete their account.']})
    for tenant in tenants:
        if tenant.type == TenantType.DEFAULT:
            if tenant.creator_id != account.pk or tenant.user_memberships.exclude(user=account).exists():
                raise ValidationError({'confirmation': ['Your personal organization requires administrator review.']})
            delete_organization(tenant.pk, request, private_account_id=str(account.pk))
        else:
            departing_membership = tenant.user_memberships.filter(user=account).first()
            if departing_membership:
                for membership in owner_memberships(tenant.pk).exclude(user=account):
                    Notification.objects.create(
                        user=membership.user,
                        type='MEMBER_ACCOUNT_DELETED',
                        data={'name': str(account.profile), 'tenant_name': tenant.name},
                    )
                log_action(
                    tenant_id=tenant.pk,
                    action_type=ActionType.DELETE,
                    entity_type='tenant_membership',
                    entity_id=str(departing_membership.pk),
                    entity_name=str(account.profile),
                    actor_user=actor,
                    metadata={'reason': 'account_deleted'},
                )

    # Backfill pre-feature historical activity before SET_NULL severs the relation.
    ActionLog.objects.filter(actor_user=account, actor_id_snapshot='').update(
        actor_id_snapshot=str(account.pk), actor_name_snapshot=str(account.profile)
    )
    avatar = account.profile.avatar
    avatars = list(UserAvatar.objects.filter(Q(account_id=str(account.pk)) | Q(pk=avatar.pk if avatar else None)))
    for image in avatars:
        for field in (image.original, image.thumbnail):
            if field.name:
                schedule_resource_cleanup(ResourceCleanup.ResourceType.AVATAR_FILE, resource_path=field.name)
    schedule_resource_cleanup(ResourceCleanup.ResourceType.USER_AVATAR_PREFIX, account_id=str(account.pk))
    for document in DocumentDemoItem.objects.filter(created_by=account, tenant__isnull=True):
        if document.file.name:
            schedule_resource_cleanup(ResourceCleanup.ResourceType.DOCUMENT_FILE, resource_path=document.file.name)
        document.delete()
    for kind in (ResourceCleanup.ResourceType.USER_EXPORT_PREFIX, ResourceCleanup.ResourceType.LEGACY_USER_EXPORT):
        schedule_resource_cleanup(kind, account_id=str(account.pk))
    # Pending invitations are email-bound; do not let a later registration inherit them.
    TenantMembership.objects.get_all().filter(is_accepted=False).filter(
        Q(user=account) | Q(invitee_email_address__iexact=account.email)
    ).delete()
    SecurityEmailOutbox.objects.filter(user=account, sent_at__isnull=True).update(cancelled_at=timezone.now())
    AccountDeletion.objects.get_or_create(account_id=str(account.pk), defaults={'actor_id': str(actor.pk)})
    schedule_resource_cleanup(ResourceCleanup.ResourceType.ACCOUNT_MARKER, account_id=str(account.pk))
    if not restoration:
        enqueue_email(account, 'ACCOUNT_DELETED')
    record('auth_account_deletion', request=request, user=account, actor=actor)
    if grant:
        passkey_management.consume_grant(grant)
    SessionService(account).revoke_all_sessions()
    jwt.blacklist_user_tokens(account)
    account.delete()
    for image in avatars:
        image.delete()
    if actor.pk == user_id:
        getattr(request, '_request', request).reset_auth_cookie = True
        request.user = AnonymousUser()
        getattr(request, '_request', request).user = request.user
