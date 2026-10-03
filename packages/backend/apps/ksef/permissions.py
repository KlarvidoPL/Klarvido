"""
KSeF app permission definitions and category.

Category and description are defined locally and registered so the tenant roles UI can show them.
"""

from typing import List

from apps.multitenancy.constants import SystemRoleType
from apps.multitenancy.permissions import (
    PermissionDefinition,
    register_app_permissions,
    register_permission_category,
    register_system_role_permissions,
)

KSEF_CATEGORY = 'KSEF'
KSEF_CATEGORY_LABEL = 'KSeF'
KSEF_CATEGORY_DESCRIPTION = 'KSeF invoice system connection'

register_permission_category(KSEF_CATEGORY, KSEF_CATEGORY_LABEL, KSEF_CATEGORY_DESCRIPTION)

# Grant KSeF permissions to ADMIN (OWNER gets all permissions)
register_system_role_permissions(SystemRoleType.ADMIN, ['ksef.view', 'ksef.manage'])

KSEF_PERMISSIONS: List[PermissionDefinition] = [
    PermissionDefinition(
        code='ksef.view',
        name='View KSeF Connection',
        description='View whether a KSeF token is connected and when it was last verified',
        category=KSEF_CATEGORY,
        sort_order=10,
    ),
    PermissionDefinition(
        code='ksef.manage',
        name='Manage KSeF Connection',
        description='Add, test, replace or remove the KSeF token',
        category=KSEF_CATEGORY,
        sort_order=20,
    ),
]

register_app_permissions(KSEF_PERMISSIONS)
