from graphql_relay import to_global_id

from apps.multitenancy.constants import TenantType
from apps.multitenancy.models import Tenant, has_tenant_access
from apps.sso.enforcement import filter_tenants_for_password_session


def accessible_organization(request, organization_id):
    if not organization_id:
        return None
    try:
        organization = Tenant.objects.filter(pk=organization_id, type=TenantType.ORGANIZATION).first()
    except (ValueError, TypeError):
        return None
    if not organization or not has_tenant_access(request.user, organization):
        return None
    if not filter_tenants_for_password_session(request, Tenant.objects.filter(pk=organization.pk)).exists():
        return None
    return organization


def default_organization_id(user, request):
    organization = accessible_organization(request, user.profile.default_organization_id)
    return to_global_id('TenantType', str(organization.pk)) if organization else None
