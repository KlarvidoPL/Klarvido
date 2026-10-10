from .services.ownership import owner_memberships
from apps.multitenancy.disabled_permissions import DISABLED_PERMISSION_CODES
from hashid_field import rest as hidrest
from rest_framework import serializers, exceptions
from django.contrib.auth import get_user_model
from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.utils import timezone
from graphql_relay import to_global_id, from_global_id

from common.action_logging.service import log_request_action
from common.graphql.field_conversions import TextChoicesFieldType
from . import models, notifications
from .constants import CompanyCountry, TenantType, TenantUserRole, SystemRoleType
from .services.membership import create_tenant_membership
from .tokens import tenant_invitation_token
from .validators import normalize_tax_id, validate_regon, validate_tax_id


def log_invitation(request, membership, operation, action_type="UPDATE"):
    roles = [
        {"name": assignment.role.name, "system_role_type": assignment.role.system_role_type}
        for assignment in membership.membership_roles.select_related("role").order_by("role__name")
    ]
    if not roles:
        roles = [{"name": membership.role, "system_role_type": membership.role}]
    log_request_action(
        request,
        tenant_id=membership.tenant_id,
        action_type=action_type,
        entity_type="tenant_invitation",
        entity_id=str(membership.pk),
        entity_name=membership.user.email if membership.user else membership.invitee_email_address,
        metadata={
            "operation": operation,
            "roles": roles,
        },
    )


def decode_role_id(role_id: str) -> str:
    """
    Decode a role ID that could be either a GraphQL relay ID or a hashid.
    Returns the hashid format.
    """
    # Check if it's a GraphQL relay ID (base64 encoded)
    try:
        type_name, decoded_id = from_global_id(role_id)
        if type_name == "OrganizationRoleType":
            return decoded_id
    except Exception:
        pass
    # Return as-is if not a relay ID (assume it's already a hashid)
    return role_id


class TenantSerializer(serializers.ModelSerializer):
    id = hidrest.HashidSerializerCharField(source_field="multitenancy.Tenant.id", read_only=True)
    # Looser than the model's max_length: input may contain separators ("972-138-23-73") that validate_* strips
    nip = serializers.CharField(required=False, allow_blank=True, max_length=20)
    regon = serializers.CharField(required=False, allow_blank=True, max_length=20)
    REQUIRED_COMPANY_FIELDS = {
        "nip": _("NIP is required"),
        "company_name": _("Company name is required"),
        "regon": _("REGON is required"),
        "address": _("Address is required"),
        "vat_status": _("VAT status is required"),
    }
    # The country goes with the tax ID: both identify the registered company, so neither changes once stored
    IMMUTABLE_COMPANY_FIELDS = ("country", "nip", "regon")

    def validate_regon(self, value):
        return validate_regon(value)

    def validate(self, attrs):
        errors = {}

        # The tax ID's format depends on the company's country, so it's validated here rather than in a field
        # validator. Empty is allowed on update (organizations created before NIP existed); required on create below.
        if "nip" in attrs:
            country = attrs.get("country") or getattr(self.instance, "country", None) or CompanyCountry.POLAND
            if normalize_tax_id(attrs["nip"], country):
                try:
                    attrs["nip"] = validate_tax_id(attrs["nip"], country)
                except serializers.ValidationError as e:
                    errors["nip"] = e.detail
            else:
                attrs["nip"] = ""

        for field, message in self.REQUIRED_COMPANY_FIELDS.items():
            # Create: every company field is required. Update: fields left out stay as they are (e.g. renaming the
            # personal default tenant), but one that's sent can't be blanked.
            if field not in errors and (self.instance is None or field in attrs) and not attrs.get(field):
                errors[field] = [serializers.ErrorDetail(message, code="required")]

        # NIP and REGON never change for a company: once stored they're locked (a wrong one is fixed by a superuser in
        # Django admin). Still empty - organizations created before these fields existed - they can be set once.
        if self.instance is not None:
            for field in self.IMMUTABLE_COMPANY_FIELDS:
                stored = getattr(self.instance, field)
                if field in attrs and field not in errors and stored and attrs[field] != stored:
                    errors[field] = [
                        serializers.ErrorDetail(_("This value can't be changed once set"), code="immutable")
                    ]

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        from .permissions import create_system_roles_for_tenant

        validated_data["creator"] = self.context["request"].user
        validated_data["type"] = TenantType.ORGANIZATION
        tenant = super().create(validated_data)

        # Create membership for the creator
        membership = create_tenant_membership(
            user=validated_data["creator"], tenant=tenant, role=TenantUserRole.OWNER, is_accepted=True
        )

        # Create system roles (OWNER, ADMIN, MEMBER) for the new tenant
        system_roles = create_system_roles_for_tenant(tenant)

        # Assign the OWNER role to the creator's membership
        owner_role = next((r for r in system_roles if r.system_role_type == SystemRoleType.OWNER), None)
        if owner_role:
            models.TenantMembershipRole.objects.create(
                membership=membership,
                role=owner_role,
                assigned_by=validated_data["creator"],
            )

        models.OrganizationOnboardingProfile.objects.create(tenant=tenant, is_required=True)

        return tenant

    class Meta:
        model = models.Tenant
        fields = (
            "id",
            "name",
            "billing_email",
            "country",
            "nip",
            "company_name",
            "regon",
            "address",
            "vat_status",
        )


class UpdateTenantSerializer(TenantSerializer):
    # Not stored - only here so TenantUserRoleMiddleware resolves (and membership/RBAC-checks) the tenant being
    # updated. The middleware deliberately never treats a generic `id` input as a tenant id.
    tenant_id = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        attrs.pop("tenant_id", None)
        return super().validate(attrs)

    class Meta(TenantSerializer.Meta):
        fields = TenantSerializer.Meta.fields + ("tenant_id",)


class TenantInvitationActionSerializer(serializers.Serializer):
    """
    Parent serializer for Accept and Decline serializers.

    It validates if invitation exists and if token is correct before proceeding with invitation action.
    """

    id = hidrest.HashidSerializerCharField(source_field="multitenancy.TenantMembership.id", write_only=True)
    token = serializers.CharField(write_only=True, help_text=_("Token"))
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        membership_id = attrs["id"]
        user = self.context["request"].user
        membership = models.TenantMembership.objects.get_not_accepted().filter(pk=membership_id, user=user).first()

        if not membership:
            raise exceptions.NotFound("Invitation not found.")

        if "token" in attrs and not tenant_invitation_token.check_token(user.email, attrs["token"], membership):
            raise exceptions.ValidationError(_("Malformed tenant invitation token"))

        return attrs


class AcceptTenantInvitationSerializer(TenantInvitationActionSerializer):
    """
    Updates not accepted invitation membership object to be accepted one.
    """

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not self.context["request"].user.is_confirmed:
            raise exceptions.ValidationError(_("Confirm your email before accepting an organization invitation."))
        return attrs

    def create(self, validated_data):
        membership_id = validated_data["id"]
        user = self.context["request"].user
        membership = models.TenantMembership.objects.get_not_accepted().filter(pk=membership_id, user=user).first()
        if membership:
            models.TenantMembership.objects.get_not_accepted().filter(pk=membership_id, user=user).update(
                is_accepted=True, invitation_accepted_at=timezone.now()
            )
            log_invitation(self.context["request"], membership, "invitation_accepted")
            notifications.send_accepted_tenant_invitation_notification(
                membership, to_global_id("TenantMembershipType", membership_id)
            )
        return {"ok": True}


class DeclineTenantInvitationSerializer(TenantInvitationActionSerializer):
    """
    Removes membership object if user decides to decline invitation.
    """

    # Declining grants no access; authenticated ownership of a pending invitation is sufficient.
    token = serializers.CharField(write_only=True, required=False, help_text=_("Token"))

    def create(self, validated_data):
        membership_id = validated_data["id"]
        user = self.context["request"].user
        membership = models.TenantMembership.objects.get_not_accepted().filter(pk=membership_id, user=user).first()
        if membership:
            log_invitation(self.context["request"], membership, "invitation_declined", "DELETE")
            membership.delete()
            notifications.send_declined_tenant_invitation_notification(
                membership, to_global_id("TenantMembershipType", membership_id)
            )
        return {"ok": True}


class CreateTenantInvitationSerializer(serializers.Serializer):
    """
    Serializer for creating a not-yet-accepted membership invitation.

    This serializer is designed to handle the creation of a membership invitation within a tenant.
    It validates the input data, ensuring that the connection between the specified user or invitee email
    and the tenant does not already exist. If the connection is valid, it creates a new not accepted membership object.

    Supports both legacy role field and new organization_role_ids for RBAC.

    SECURITY:
    - Validates that the requesting user has 'members.invite' permission
    - Prevents assigning owner roles unless the inviter is an owner
    - Validates all role IDs belong to the tenant
    - Ensures users can only assign roles with permissions they also have
    """

    # Input fields (write_only)
    email = serializers.EmailField(required=True, write_only=True)
    role = TextChoicesFieldType(
        choices=TenantUserRole.choices, choices_class=TenantUserRole, required=False, write_only=True
    )
    organization_role_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True,
        help_text=_("List of organization role IDs to assign to the invited member"),
    )
    tenant_id = serializers.CharField(write_only=True)

    # Output fields (read_only)
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        """
        Validate the invitation data.

        Note: Permission checks (members.invite) are handled at the mutation level via
        requires("members.invite") on create_tenant_invitation, combined with the
        @permission_classes(policies.IsTenantAdminAccess) class-level gate on TenantOwnerMutation
        (apps/multitenancy/schema.py).
        """
        email = BaseUserManager.normalize_email(attrs["email"])
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)

        if not tenant:
            raise serializers.ValidationError(_("Tenant is required."))

        if tenant.type == TenantType.DEFAULT:
            raise serializers.ValidationError(_("Invitation for personal tenant cannot be created."))

        if (
            models.TenantMembership.objects.get_all()
            .filter(Q(user__email=email, tenant=tenant) | Q(invitee_email_address=email, tenant=tenant))
            .exists()
        ):
            raise serializers.ValidationError(_("Invitation already exists"))

        # A superuser already has owner-equivalent access to every tenant via the
        # cross-tenant bypass (see apps.multitenancy.models.is_superuser_bypass_eligible)
        # - inviting them as a real, role-scoped member would only ever narrow their
        # access, which defeats the point of an invitation and would be confusing.
        # NOTE: deliberately don't reveal *why* in the message/code - just that they
        # can't be invited - so a tenant owner can't use this as a way to fingerprint
        # which email addresses belong to platform superusers.
        if get_user_model().objects.filter(email=email, is_superuser=True).exists():
            raise serializers.ValidationError(
                _("This user cannot be a member of this organization."), code="user_cannot_be_invited"
            )

        # Check if inviter is an owner (needed for owner role assignment validation, for both
        # the legacy role field below and organization_role_ids further down). The superuser
        # cross-tenant bypass grants owner-equivalent access without a real membership row -
        # OR it in the same way get_user_permissions_for_tenant already does for the general
        # permission set.
        inviter = request.user if request else None
        is_inviter_owner = False
        if inviter:
            inviter_membership = models.TenantMembership.objects.filter(
                user=inviter, tenant=tenant, is_accepted=True
            ).first()
            is_inviter_owner = models.is_superuser_bypass_eligible(inviter) or bool(
                inviter_membership
                and (
                    inviter_membership.role == TenantUserRole.OWNER
                    or models.TenantMembershipRole.objects.filter(
                        membership=inviter_membership, role__system_role_type=SystemRoleType.OWNER
                    ).exists()
                )
            )

        # SECURITY: Only owners can invite with the legacy Owner role too - this field bypasses
        # organization_role_ids entirely, so without this check a non-owner with just
        # members.invite could hand a brand new member real owner-bypass privileges (the legacy
        # role field is treated as a valid "is owner" signal throughout the app) with no check
        # at all, same class of gap as organization_role_ids below.
        if attrs.get("role") == TenantUserRole.OWNER and not is_inviter_owner:
            raise serializers.ValidationError(_("Only organization owners can invite members with the Owner role."))

        # Validate and decode organization role IDs if provided
        org_role_ids = attrs.get("organization_role_ids", [])
        if org_role_ids:
            valid_roles = {str(r.id): r for r in models.OrganizationRole.objects.filter(tenant=tenant)}
            decoded_role_ids = []
            inviter_permissions = models.get_user_permissions_for_tenant(inviter, tenant) if inviter else set()

            for role_id in org_role_ids:
                decoded_id = decode_role_id(role_id)

                # Ensure role belongs to this tenant
                if decoded_id not in valid_roles:
                    raise serializers.ValidationError(_(f"Invalid organization role ID: {role_id}"))

                # SECURITY: Only owners can invite with the Owner role
                role = valid_roles[decoded_id]
                if role.is_owner_role and not is_inviter_owner:
                    raise serializers.ValidationError(
                        _("Only organization owners can invite members with the Owner role.")
                    )

                # SECURITY: Users can only invite members with roles whose permissions they also have
                # (owners can invite with any role) - mirrors AssignRolesToMemberMutation in schema.py.
                if not is_inviter_owner:
                    role_permissions = set(
                        role.permissions.exclude(code__in=DISABLED_PERMISSION_CODES).values_list("code", flat=True)
                    )
                    missing_permissions = role_permissions - inviter_permissions
                    if missing_permissions:
                        permissions_list = ", ".join(list(missing_permissions)[:3])
                        raise serializers.ValidationError(
                            _(f"You cannot invite a member with permissions you don't have: {permissions_list}")
                        )

                decoded_role_ids.append(decoded_id)

            # Store decoded IDs and role objects for use in create()
            attrs["_decoded_role_ids"] = decoded_role_ids
            attrs["_valid_roles"] = valid_roles

        # Require either legacy role or organization_role_ids
        if not attrs.get("role") and not org_role_ids:
            raise serializers.ValidationError(_("Either 'role' or 'organization_role_ids' must be provided"))

        return super().validate(attrs)

    def create(self, validated_data):
        email = BaseUserManager.normalize_email(validated_data["email"])
        role = validated_data.get("role", TenantUserRole.MEMBER)  # Default to MEMBER for backward compatibility
        decoded_role_ids = validated_data.get("_decoded_role_ids", [])
        valid_roles = validated_data.get("_valid_roles", {})

        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        creator = getattr(request, "user", None)

        User = get_user_model()

        tenant_membership_data = {
            "role": role,
            "tenant": tenant,
            "creator": creator,
        }
        try:
            tenant_membership_data["user"] = User.objects.get(email=email)
        except User.DoesNotExist:
            tenant_membership_data["invitee_email_address"] = email

        membership = create_tenant_membership(**tenant_membership_data)

        # Assign organization roles if provided (using decoded hashid IDs)
        if decoded_role_ids:
            for role_id in decoded_role_ids:
                org_role = valid_roles.get(role_id)
                if not org_role:
                    org_role = models.OrganizationRole.objects.filter(id=role_id, tenant=tenant).first()
                    if not org_role:
                        continue  # Skip invalid roles

                models.TenantMembershipRole.objects.get_or_create(
                    membership=membership, role=org_role, defaults={"assigned_by": creator}
                )

        log_invitation(request, membership, "invitation_sent", "CREATE")

        # Return only the response fields (ok is read_only)
        return {"ok": True}


class ResendTenantInvitationSerializer(serializers.Serializer):
    """
    Serializer for resending an invitation email to a pending membership.

    This serializer finds an existing not-accepted membership and resends the invitation email
    with a fresh token.
    """

    id = hidrest.HashidSerializerCharField(source_field="multitenancy.TenantMembership.id", write_only=True)
    tenant_id = serializers.CharField(write_only=True)
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        membership_id = attrs["id"]
        tenant = self.context["request"].tenant

        membership = models.TenantMembership.objects.get_not_accepted().filter(pk=membership_id, tenant=tenant).first()

        if not membership:
            raise exceptions.NotFound(_("Pending invitation not found."))

        attrs["membership"] = membership
        return super().validate(attrs)

    def create(self, validated_data):
        from .notifications import TenantInvitationEmail, send_tenant_invitation_notification

        membership = validated_data["membership"]
        email = membership.user.email if membership.user else membership.invitee_email_address

        token = tenant_invitation_token.make_token(user_email=email, tenant_membership=membership)
        global_tenant_membership_id = to_global_id("TenantMembershipType", membership.id)

        TenantInvitationEmail(
            to=email,
            data={"tenant_membership_id": global_tenant_membership_id, "token": token},
            user=membership.user,
        ).send()

        if membership.user:
            send_tenant_invitation_notification(membership, global_tenant_membership_id, token)

        log_invitation(self.context["request"], membership, "invitation_resent")
        return {"ok": True}


class UpdateTenantMembershipSerializer(serializers.ModelSerializer):
    """
    Serializer for updating a tenant membership.

    This serializer is designed to handle the update of a membership within a tenant.

    SECURITY:
    - Prevents demoting the last owner to a non-owner role
    - Checks both legacy roles AND RBAC owner roles for complete protection
    - Only owners can modify owner memberships
    """

    id = hidrest.HashidSerializerCharField(source_field="multitenancy.TenantMembership.id", write_only=True)
    role = TextChoicesFieldType(choices=TenantUserRole.choices, choices_class=TenantUserRole)

    def validate(self, attrs):
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        acting_user = getattr(request, "user", None)

        membership = models.TenantMembership.objects.get_all().filter(pk=attrs["id"]).first()
        if not membership:
            raise exceptions.NotFound("Membership not found.")

        if tenant and tenant.type == TenantType.DEFAULT:
            raise exceptions.ValidationError("Cannot change roles in a personal tenant.")

        new_role = attrs.get("role")

        if acting_user and membership.user_id == acting_user.id:
            acting_membership = models.TenantMembership.objects.filter(
                user=acting_user, tenant=tenant, is_accepted=True
            ).first()
            is_acting_user_owner = models.is_superuser_bypass_eligible(acting_user) or bool(
                acting_membership
                and (
                    acting_membership.role == TenantUserRole.OWNER
                    or models.TenantMembershipRole.objects.filter(
                        membership=acting_membership, role__system_role_type=SystemRoleType.OWNER
                    ).exists()
                )
            )
            if not is_acting_user_owner:
                raise exceptions.PermissionDenied("permission_denied")

        # Check if target is currently an owner (legacy OR RBAC)
        is_currently_legacy_owner = membership.role == TenantUserRole.OWNER
        is_currently_rbac_owner = models.TenantMembershipRole.objects.filter(
            membership=membership, role__system_role_type=SystemRoleType.OWNER
        ).exists()
        is_currently_owner = is_currently_legacy_owner or is_currently_rbac_owner

        # Check if acting user is an owner
        if acting_user and tenant:
            acting_membership = models.TenantMembership.objects.filter(
                user=acting_user, tenant=tenant, is_accepted=True
            ).first()
            is_acting_user_legacy_owner = acting_membership and acting_membership.role == TenantUserRole.OWNER
            is_acting_user_rbac_owner = (
                acting_membership
                and models.TenantMembershipRole.objects.filter(
                    membership=acting_membership, role__system_role_type=SystemRoleType.OWNER
                ).exists()
            )
            is_acting_user_owner = (
                models.is_superuser_bypass_eligible(acting_user)
                or is_acting_user_legacy_owner
                or is_acting_user_rbac_owner
            )

            # SECURITY: Only owners can modify owner memberships
            if is_currently_owner and not is_acting_user_owner:
                raise exceptions.PermissionDenied("Only owners can modify the role of other owners.")

            # SECURITY: Only owners can promote a member to Owner. Without this, a non-owner
            # with just members.roles.edit could set another member's legacy role straight to
            # OWNER - which every Owner-gate in the app (this one included) treats as a valid
            # "is owner" signal, handing that member real owner-bypass privileges everywhere.
            if new_role == TenantUserRole.OWNER and not is_currently_owner and not is_acting_user_owner:
                raise exceptions.PermissionDenied("Only organization owners can assign the Owner role.")

        # SECURITY: Prevent demoting the last owner
        if (
            is_currently_owner
            and new_role != TenantUserRole.OWNER
            and (
                not is_currently_rbac_owner
                and not owner_memberships(tenant.pk).exclude(user_id=membership.user_id).exists()
            )
        ):
            raise exceptions.ValidationError("There must be at least one owner in the organization.")

        return super().validate(attrs)

    class Meta:
        model = models.TenantMembership
        fields = (
            "id",
            "role",
        )
