from django.db import migrations

# Purple is reserved for the Owner system role. Custom roles that were given it before the restriction
# are moved to blue so they can still be edited with the color picker.
PURPLE = 'purple'
BLUE = 'blue'


def reassign_custom_purple_roles(apps, schema_editor):
    OrganizationRole = apps.get_model('multitenancy', 'OrganizationRole')
    OrganizationRole.objects.filter(system_role_type='', color=PURPLE).update(color=BLUE)


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0028_organization_onboarding_profile'),
    ]

    operations = [
        migrations.RunPython(reassign_custom_purple_roles, migrations.RunPython.noop),
    ]
