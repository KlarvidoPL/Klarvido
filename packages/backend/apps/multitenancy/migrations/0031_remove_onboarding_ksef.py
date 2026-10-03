from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0030_organizationonboardingprofile_company_data_and_more'),
    ]

    operations = [
        migrations.RemoveField(model_name='organizationonboardingprofile', name='ksef_demo_token_encrypted'),
        migrations.RemoveField(model_name='organizationonboardingprofile', name='ksef_status'),
    ]
