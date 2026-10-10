"""Distinct accepted owners and the shared lock used by ownership-changing operations."""

from functools import wraps

from django.db import transaction
from django.db.models import Q
from graphql_relay import from_global_id

from apps.multitenancy.constants import SystemRoleType, TenantUserRole
from apps.multitenancy.models import Tenant, TenantMembership


def owner_memberships(tenant_id):
    return (
        TenantMembership.objects.get_all()
        .filter(tenant_id=tenant_id, is_accepted=True, user__is_active=True)
        .filter(Q(role=TenantUserRole.OWNER) | Q(membership_roles__role__system_role_type=SystemRoleType.OWNER))
        .distinct()
    )


def lock_ownership_change(function):
    """Hold the organization lock across authorization, validation and mutation."""

    @wraps(function)
    def wrapped(cls, root, info, *args, **kwargs):
        with transaction.atomic():
            tenant_id = kwargs.get('tenant_id')
            if tenant_id:
                _, decoded = from_global_id(tenant_id)
                tenant_id = decoded or tenant_id
            else:
                tenant_id = info.context.tenant.pk
            Tenant.objects.select_for_update().get(pk=tenant_id)
            return function(cls, root, info, *args, **kwargs)

    return wrapped
