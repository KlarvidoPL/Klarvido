from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0027_organization_onboarding_profile'),
    ]

    operations = [
        migrations.RemoveField(model_name='organizationonboardingprofile', name='ksef_demo_connected'),
        migrations.AddField(
            model_name='organizationonboardingprofile',
            name='ksef_status',
            field=models.CharField(default='not_connected', max_length=20),
        ),
    ]
