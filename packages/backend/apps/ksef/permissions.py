"""
KSeF permissions. They live in the Security category, next to the SSO and passkey permissions, so the roles UI groups
them with the rest of the security settings.
"""

from typing import List

from apps.multitenancy.constants import CompanyCountry, PermissionCategory, SystemRoleType
from apps.multitenancy.permissions import (
    PermissionDefinition,
    register_app_permissions,
    register_system_role_permissions,
)

# Organization Admins can see the KSeF connection but not change the token; OWNER gets all permissions,
# and security.ksef.manage can be granted explicitly to custom roles.
register_system_role_permissions(SystemRoleType.ADMIN, ['security.ksef.view'])

KSEF_PERMISSIONS: List[PermissionDefinition] = [
    PermissionDefinition(
        code='security.ksef.view',
        name='View KSeF Connection',
        description='View whether a KSeF token is connected and when it was last verified',
        category=PermissionCategory.SECURITY,
        sort_order=15,
        countries=(CompanyCountry.POLAND,),
    ),
    PermissionDefinition(
        code='security.ksef.manage',
        name='Manage KSeF Connection',
        description='Add, test, replace or remove the KSeF token',
        category=PermissionCategory.SECURITY,
        sort_order=16,
        countries=(CompanyCountry.POLAND,),
    ),
]

register_app_permissions(KSEF_PERMISSIONS)
