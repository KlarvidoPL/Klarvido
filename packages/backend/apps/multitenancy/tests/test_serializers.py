import pytest
from unittest.mock import Mock

from ..models import TenantMembership, OrganizationRole, TenantMembershipRole, Permission
from ..constants import TenantUserRole, TenantType, SystemRoleType
from ..serializers import (
    CreateTenantInvitationSerializer,
    ResendTenantInvitationSerializer,
    UpdateTenantMembershipSerializer,
)


pytestmark = pytest.mark.django_db


class TestCreateTenantInvitationSerializer:
    def test_create_invitation_existing_user(self, mocker, user, user_factory, tenant_factory):
        make_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token"
        )
        creator = user_factory()

        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)

        data = {
            "email": user.email,
            "role": TenantUserRole.ADMIN,
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=creator)})
        assert serializer.is_valid()

        result = serializer.create(serializer.validated_data)

        assert result['ok']
        assert (
            TenantMembership.objects.get_not_accepted()
            .filter(user=user, tenant=tenant, role=TenantUserRole.ADMIN)
            .exists()
        )
        make_token.assert_called_once()

    def test_create_invitation_new_user(self, mocker, user_factory, tenant_factory):
        make_token = mocker.patch(
            "apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token"
        )
        creator = user_factory()
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)

        data = {
            "email": "new_user@example.com",
            "role": TenantUserRole.MEMBER,
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=creator)})
        assert serializer.is_valid()

        result = serializer.create(serializer.validated_data)

        assert result['ok']
        assert (
            TenantMembership.objects.get_not_accepted()
            .filter(
                invitee_email_address='new_user@example.com',
                tenant=tenant,
                role=TenantUserRole.MEMBER,
                user__isnull=True,
            )
            .exists()
        )
        make_token.assert_called_once()

    def test_create_invitation_for_default_tenant_new_user(self, tenant_factory):
        tenant = tenant_factory(name="Test Tenant", type=TenantType.DEFAULT)

        data = {
            "email": "new_user@example.com",
            "role": TenantUserRole.MEMBER,
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant)})
        assert not serializer.is_valid()
        assert "Invitation for personal tenant cannot be created." in serializer.errors['non_field_errors'][0]

    def test_create_invitation_existing_user_duplicate(self, user, tenant_factory):
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        TenantMembership.objects.create(user=user, tenant=tenant, role=TenantUserRole.ADMIN)

        data = {
            "email": user.email,
            "role": TenantUserRole.MEMBER,
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant)})

        assert not serializer.is_valid()
        assert 'Invitation already exists' in serializer.errors['non_field_errors'][0]

    def test_cannot_invite_with_role_granting_permissions_inviter_lacks(
        self, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        """
        SECURITY: A non-owner inviter cannot invite a new member with a role that grants
        permissions the inviter doesn't personally have - mirrors AssignRolesToMemberMutation's
        equivalent check in schema.py, which previously had no counterpart here.
        """
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        inviter = user_factory()
        # Legacy ADMIN role auto-assigns the system Administrator RBAC role, which does not
        # include 'billing.manage' (owner-only permission).
        tenant_membership_factory(user=inviter, tenant=tenant, role=TenantUserRole.ADMIN, is_accepted=True)

        billing_permission, _ = Permission.objects.get_or_create(
            code="billing.manage", defaults={"name": "Manage Billing", "category": "billing"}
        )
        billing_role = OrganizationRole.objects.create(tenant=tenant, name="Billing Manager")
        billing_role.permissions.add(billing_permission)

        data = {
            "email": "new_user@example.com",
            "organization_role_ids": [str(billing_role.id)],
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=inviter)})

        assert not serializer.is_valid()
        error_text = str(serializer.errors).lower()
        assert "permissions you don't have" in error_text
        assert "billing.manage" in error_text

    def test_cannot_invite_with_legacy_owner_role_as_non_owner(
        self, user_factory, tenant_factory, tenant_membership_factory
    ):
        """
        SECURITY: The legacy 'role' field is a separate input from organization_role_ids and
        bypasses it entirely, so without its own Owner-role check a non-owner inviter could
        hand a brand new member the legacy OWNER role directly - which every Owner-gate in the
        app treats as a valid "is owner" signal, granting real owner-bypass privileges with no
        check at all.
        """
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        inviter = user_factory()
        tenant_membership_factory(user=inviter, tenant=tenant, role=TenantUserRole.ADMIN, is_accepted=True)

        data = {
            "email": "new_user@example.com",
            "role": TenantUserRole.OWNER,
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=inviter)})

        assert not serializer.is_valid()
        assert "Only organization owners can invite members with the Owner role." in str(
            serializer.errors['non_field_errors'][0]
        )
        assert not TenantMembership.objects.get_not_accepted().filter(tenant=tenant, role=TenantUserRole.OWNER).exists()

    def test_owner_can_invite_with_legacy_owner_role(self, user, tenant_factory, tenant_membership_factory):
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True)

        data = {
            "email": "new_user@example.com",
            "role": TenantUserRole.OWNER,
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=user)})

        assert serializer.is_valid(), serializer.errors

    def test_owner_can_invite_with_role_granting_any_permission(self, user, tenant_factory, tenant_membership_factory):
        """An owner inviter is exempt from the permission-coverage check."""
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        owner = user
        tenant_membership_factory(user=owner, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True)

        billing_permission, _ = Permission.objects.get_or_create(
            code="billing.manage", defaults={"name": "Manage Billing", "category": "billing"}
        )
        billing_role = OrganizationRole.objects.create(tenant=tenant, name="Billing Manager")
        billing_role.permissions.add(billing_permission)

        data = {
            "email": "new_user@example.com",
            "organization_role_ids": [str(billing_role.id)],
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=owner)})

        assert serializer.is_valid(), serializer.errors

    def test_superuser_without_membership_can_invite_with_owner_role(self, user_factory, tenant_factory):
        """
        SECURITY: The superuser cross-tenant bypass grants owner-equivalent access without
        a real membership row - a superuser with no real membership in the tenant must still
        be able to invite a new member with the Owner role, same as a real owner.
        """
        from ..permissions import create_system_roles_for_tenant

        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        create_system_roles_for_tenant(tenant)
        owner_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)

        superuser = user_factory(is_superuser=True)

        data = {
            "email": "new_user@example.com",
            "organization_role_ids": [str(owner_role.id)],
            "tenant_id": str(tenant.id),
        }
        serializer = CreateTenantInvitationSerializer(
            data=data, context={'request': Mock(tenant=tenant, user=superuser)}
        )

        assert serializer.is_valid(), serializer.errors


class TestResendTenantInvitationSerializer:
    def test_resend_invitation_for_existing_user(self, mocker, user, user_factory, tenant_factory):
        mocker.patch("apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token")
        # Mock where it's imported - the serializer imports notifications module and then imports from it in create()
        mock_email_instance = mocker.Mock()
        mock_send_email = mocker.patch(
            "apps.multitenancy.serializers.notifications.TenantInvitationEmail", return_value=mock_email_instance
        )
        mock_send_notification = mocker.patch(
            "apps.multitenancy.serializers.notifications.send_tenant_invitation_notification"
        )
        creator = user_factory()

        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        membership = TenantMembership.objects.create(
            user=user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=False, creator=creator
        )

        data = {
            "id": str(membership.id),
            "tenant_id": str(tenant.id),
        }
        serializer = ResendTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=creator)})
        assert serializer.is_valid()

        result = serializer.create(serializer.validated_data)

        assert result['ok']
        mock_send_email.assert_called_once()
        mock_send_notification.assert_called_once()

    def test_resend_invitation_for_invitee_email(self, mocker, user_factory, tenant_factory):
        mocker.patch("apps.multitenancy.tokens.TenantInvitationTokenGenerator.make_token", return_value="token")
        # Mock where it's imported - the serializer imports notifications module and then imports from it in create()
        mock_email_instance = mocker.Mock()
        mock_send_email = mocker.patch(
            "apps.multitenancy.serializers.notifications.TenantInvitationEmail", return_value=mock_email_instance
        )
        mock_send_notification = mocker.patch(
            "apps.multitenancy.serializers.notifications.send_tenant_invitation_notification"
        )
        creator = user_factory()

        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        membership = TenantMembership.objects.create(
            invitee_email_address="test@example.com",
            tenant=tenant,
            role=TenantUserRole.MEMBER,
            is_accepted=False,
            creator=creator,
        )

        data = {
            "id": str(membership.id),
            "tenant_id": str(tenant.id),
        }
        serializer = ResendTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=creator)})
        assert serializer.is_valid()

        result = serializer.create(serializer.validated_data)

        assert result['ok']
        mock_send_email.assert_called_once()
        # For invitee emails without user, notification is not sent
        mock_send_notification.assert_not_called()

    def test_resend_invitation_not_found(self, user_factory, tenant_factory):
        creator = user_factory()
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)

        data = {
            "id": "nonexistent-id",
            "tenant_id": str(tenant.id),
        }
        serializer = ResendTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=creator)})

        # Should fail validation because the membership doesn't exist
        assert not serializer.is_valid()

    def test_resend_invitation_already_accepted(self, user, user_factory, tenant_factory):
        creator = user_factory()
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        membership = TenantMembership.objects.create(
            user=user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True, creator=creator
        )

        data = {
            "id": membership.id,
            "tenant_id": str(tenant.id),
        }
        serializer = ResendTenantInvitationSerializer(data=data, context={'request': Mock(tenant=tenant, user=creator)})

        # Should fail because it's already accepted
        assert not serializer.is_valid()


class TestUpdateTenantMembershipSerializerSecurity:
    """
    SECURITY: Tests for owner demotion protection in UpdateTenantMembershipSerializer.
    """

    def test_cannot_demote_last_legacy_owner(self, user, tenant_factory, tenant_membership_factory):
        """
        SECURITY: The last legacy owner cannot be demoted to a non-owner role.
        """
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        owner_membership = tenant_membership_factory(
            user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True
        )
        TenantMembershipRole.objects.filter(membership=owner_membership).delete()

        request = Mock(tenant=tenant, user=user)
        data = {'id': str(owner_membership.pk), 'role': TenantUserRole.MEMBER}
        serializer = UpdateTenantMembershipSerializer(data=data, context={'request': request})

        assert not serializer.is_valid()
        assert "at least one owner" in str(serializer.errors).lower()

    def test_can_demote_owner_when_other_legacy_owners_exist(
        self, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        """
        An owner can be demoted when other legacy owners exist.
        """
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)
        owner2 = user_factory(email="owner2@test.com")

        tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True)
        owner2_membership = tenant_membership_factory(
            user=owner2, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True
        )

        request = Mock(tenant=tenant, user=user)
        data = {'id': str(owner2_membership.pk), 'role': TenantUserRole.MEMBER}
        serializer = UpdateTenantMembershipSerializer(
            instance=owner2_membership, data=data, context={'request': request}, partial=True
        )

        assert serializer.is_valid(), serializer.errors

    def test_changing_legacy_role_preserves_rbac_owner_status(
        self, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        """
        Test that changing legacy role doesn't remove RBAC owner status.
        If a user has RBAC owner role, they remain an owner regardless of legacy role changes.
        """
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)

        # Create a member (not legacy owner) who is also an RBAC owner
        membership = tenant_membership_factory(user=user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True)

        from ..permissions import create_system_roles_for_tenant

        create_system_roles_for_tenant(tenant)
        owner_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)
        TenantMembershipRole.objects.get_or_create(membership=membership, role=owner_role)

        request = Mock(tenant=tenant, user=user)
        # Changing from MEMBER to ADMIN legacy role should be allowed
        # because the user still has RBAC owner role
        data = {'id': str(membership.pk), 'role': TenantUserRole.ADMIN}
        serializer = UpdateTenantMembershipSerializer(
            instance=membership, data=data, context={'request': request}, partial=True
        )

        # Should pass because user remains owner through RBAC role
        assert serializer.is_valid(), serializer.errors

        # Verify user is still counted as an owner
        owner_count = TenantMembershipRole.objects.filter(
            membership__tenant=tenant, role__system_role_type=SystemRoleType.OWNER, membership__is_accepted=True
        ).count()
        assert owner_count == 1

    def test_can_demote_when_rbac_owner_exists(self, user, user_factory, tenant_factory, tenant_membership_factory):
        """
        A legacy owner can be demoted when an RBAC owner exists.
        """
        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)

        # Legacy owner to be demoted
        legacy_owner_membership = tenant_membership_factory(
            user=user, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True
        )

        from ..permissions import create_system_roles_for_tenant

        create_system_roles_for_tenant(tenant)
        owner_role = OrganizationRole.objects.get(tenant=tenant, system_role_type=SystemRoleType.OWNER)
        other_user = user_factory(email="rbac_owner@test.com")
        other_membership = tenant_membership_factory(
            user=other_user, tenant=tenant, role=TenantUserRole.MEMBER, is_accepted=True
        )
        TenantMembershipRole.objects.create(membership=other_membership, role=owner_role)

        request = Mock(tenant=tenant, user=other_user)
        data = {'id': str(legacy_owner_membership.pk), 'role': TenantUserRole.MEMBER}
        serializer = UpdateTenantMembershipSerializer(
            instance=legacy_owner_membership, data=data, context={'request': request}, partial=True
        )

        # Should pass because there's still an RBAC owner
        assert serializer.is_valid(), serializer.errors

    def test_non_owner_cannot_modify_owner_membership(
        self, user, user_factory, tenant_factory, tenant_membership_factory
    ):
        """
        SECURITY: Non-owners should not be able to modify owner memberships.
        """
        from rest_framework.exceptions import PermissionDenied

        tenant = tenant_factory(name="Test Tenant", type=TenantType.ORGANIZATION)

        # Owner membership to modify
        owner = user_factory(email="owner@test.com")
        owner_membership = tenant_membership_factory(
            user=owner, tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True
        )

        # Non-owner trying to modify
        non_owner = user
        tenant_membership_factory(user=non_owner, tenant=tenant, role=TenantUserRole.ADMIN, is_accepted=True)

        request = Mock(tenant=tenant, user=non_owner)
        data = {'id': str(owner_membership.pk), 'role': TenantUserRole.MEMBER}
        serializer = UpdateTenantMembershipSerializer(
            instance=owner_membership, data=data, context={'request': request}, partial=True
        )

        # Should raise PermissionDenied due to permission check
        with pytest.raises(PermissionDenied) as exc_info:
            serializer.is_valid(raise_exception=True)

        assert "owner" in str(exc_info.value).lower()
