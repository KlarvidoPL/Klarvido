from django.db import migrations


def remove_from_other_countries(apps, schema_editor):
    """KSeF permissions are only offered to Polish organizations; drop them from roles elsewhere."""
    OrganizationRolePermission = apps.get_model('multitenancy', 'OrganizationRolePermission')

    OrganizationRolePermission.objects.filter(permission__code__startswith='security.ksef.').exclude(
        role__tenant__country='PL'
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ksef', '0004_security_category'),
        ('multitenancy', '0027_delete_unused_dashboard_permissions'),
    ]

    operations = [
        migrations.RunPython(remove_from_other_countries, migrations.RunPython.noop),
    ]
