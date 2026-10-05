from apps.multitenancy.constants import SystemRoleType
from apps.multitenancy.permissions import (
    PermissionDefinition,
    register_app_permissions,
    register_permission_category,
    register_system_role_permissions,
)

register_permission_category('INVOICES', 'Invoices', 'Company invoices imported from KSeF')
register_app_permissions(
    [
        PermissionDefinition(
            code=f'invoices.{action}', name=name, description=name, category='INVOICES', sort_order=index
        )
        for index, (action, name) in enumerate(
            [
                ('view', 'View invoices'),
                ('categorize', 'Categorize invoices'),
                ('export', 'Export invoices'),
                ('sync', 'Synchronize invoices'),
            ]
        )
    ]
)
register_system_role_permissions(SystemRoleType.ADMIN, ['invoices.view', 'invoices.categorize', 'invoices.export'])
