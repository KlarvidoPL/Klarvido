# Generated manually
"""
Delete the 'dashboard.view' and 'management.view' permissions entirely.

Neither gates any actual feature: the main app Home route/component has no permission
check at all (dashboard access is intentionally open to all tenant members), and
'management.view' is a leftover from an earlier rename (see
0015_rename_dashboard_to_management.py) with no corresponding "Management Dashboard"
page ever built. Deleting these Permission rows cascades to OrganizationRolePermission,
removing them from any system or custom role that had them assigned.
"""

from django.db import migrations


def delete_permissions(apps, schema_editor):
    Permission = apps.get_model('multitenancy', 'Permission')
    Permission.objects.filter(code__in=['dashboard.view', 'management.view']).delete()


def noop_reverse(apps, schema_editor):
    """Not reversible - neither permission carried any functionality, nothing to restore."""


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0026_tenant_country'),
    ]

    operations = [
        migrations.RunPython(delete_permissions, noop_reverse),
    ]
