from django.db import migrations


def revoke_admin_ksef_manage(apps, schema_editor):
    """ADMIN system roles keep ksef.view only; ksef.manage stays with OWNER and explicitly granted custom roles."""
    from apps.multitenancy.constants import SystemRoleType

    OrganizationRole = apps.get_model('multitenancy', 'OrganizationRole')
    OrganizationRolePermission = apps.get_model('multitenancy', 'OrganizationRolePermission')

    OrganizationRolePermission.objects.filter(
        role__in=OrganizationRole.objects.filter(system_role_type=SystemRoleType.ADMIN),
        permission__code='ksef.manage',
    ).delete()


def grant_admin_ksef_manage(apps, schema_editor):
    from apps.multitenancy.constants import SystemRoleType

    Permission = apps.get_model('multitenancy', 'Permission')
    OrganizationRole = apps.get_model('multitenancy', 'OrganizationRole')
    OrganizationRolePermission = apps.get_model('multitenancy', 'OrganizationRolePermission')

    permission = Permission.objects.filter(code='ksef.manage').first()
    if permission is None:
        return
    for role in OrganizationRole.objects.filter(system_role_type=SystemRoleType.ADMIN):
        OrganizationRolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [
        ('ksef', '0002_token_name'),
        ('multitenancy', '0027_delete_unused_dashboard_permissions'),
    ]

    operations = [
        migrations.RunPython(revoke_admin_ksef_manage, grant_admin_ksef_manage),
    ]
