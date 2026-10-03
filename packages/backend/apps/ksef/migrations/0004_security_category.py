from django.db import migrations

RENAMES = {
    'ksef.view': 'security.ksef.view',
    'ksef.manage': 'security.ksef.manage',
}


def move_to_security(apps, schema_editor):
    """Rename the KSeF permissions to the security.* namespace and move them into the Security category."""
    Permission = apps.get_model('multitenancy', 'Permission')
    for old_code, new_code in RENAMES.items():
        Permission.objects.filter(code=old_code).update(code=new_code, category='security')
    Permission.objects.filter(code='security.ksef.view').update(sort_order=15)
    Permission.objects.filter(code='security.ksef.manage').update(sort_order=16)


def move_to_ksef(apps, schema_editor):
    Permission = apps.get_model('multitenancy', 'Permission')
    for old_code, new_code in RENAMES.items():
        Permission.objects.filter(code=new_code).update(code=old_code, category='KSEF')


class Migration(migrations.Migration):
    dependencies = [
        ('ksef', '0003_admin_ksef_view_only'),
        ('multitenancy', '0027_delete_unused_dashboard_permissions'),
    ]

    operations = [
        migrations.RunPython(move_to_security, move_to_ksef),
    ]
