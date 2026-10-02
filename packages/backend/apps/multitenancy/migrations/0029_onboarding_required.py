from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0028_onboarding_ksef_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationonboardingprofile',
            name='is_required',
            field=models.BooleanField(default=False),
        ),
    ]
