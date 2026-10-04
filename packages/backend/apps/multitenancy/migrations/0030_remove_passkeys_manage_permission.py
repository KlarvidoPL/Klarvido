from django.db import migrations

# Passkeys are personal (managed only from each user's Profile), so the organization-level
# "security.passkeys.manage" permission is removed. Deleting the Permission row also removes
# it from every role that had it (the through rows cascade).
PERMISSION_CODE = 'security.passkeys.manage'


def remove_passkeys_manage_permission(apps, schema_editor):
    Permission = apps.get_model('multitenancy', 'Permission')
    Permission.objects.filter(code=PERMISSION_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0029_reassign_custom_role_purple_color'),
    ]

    operations = [
        migrations.RunPython(remove_passkeys_manage_permission, migrations.RunPython.noop),
    ]
