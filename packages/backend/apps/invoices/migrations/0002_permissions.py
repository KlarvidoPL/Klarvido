from django.db import migrations


def seed_permissions(apps, schema_editor):
    from apps.multitenancy.permissions import get_all_permissions

    Permission = apps.get_model('multitenancy', 'Permission')
    Role = apps.get_model('multitenancy', 'OrganizationRole')
    RolePermission = apps.get_model('multitenancy', 'OrganizationRolePermission')
    for definition in get_all_permissions():
        if not definition.code.startswith('invoices.'):
            continue
        permission, _ = Permission.objects.update_or_create(
            code=definition.code,
            defaults=dict(name=definition.name, description=definition.description,
                          category=getattr(definition.category, 'value', definition.category),
                          sort_order=definition.sort_order, is_system=True),
        )
        role_types = ['OWNER', 'ADMIN'] if definition.code != 'invoices.sync' else ['OWNER']
        for role in Role.objects.filter(system_role_type__in=role_types):
            RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [('invoices', '0001_initial'), ('multitenancy', '0028_organization_onboarding_profile')]
    operations = [migrations.RunPython(seed_permissions, migrations.RunPython.noop)]
