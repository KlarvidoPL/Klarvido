from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('multitenancy', '0026_tenant_country'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationOnboardingProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('respondent_role', models.CharField(blank=True, default='', max_length=40)),
                ('customer_type', models.CharField(blank=True, default='', max_length=40)),
                ('revenue_models', models.JSONField(blank=True, default=list)),
                ('cost_drivers', models.JSONField(blank=True, default=list)),
                ('pricing', models.CharField(blank=True, default='', max_length=80)),
                ('main_goal', models.CharField(blank=True, default='', max_length=120)),
                ('current_step', models.PositiveSmallIntegerField(default=2)),
                ('ksef_demo_token_encrypted', models.TextField(blank=True, default='')),
                ('ksef_demo_connected', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'tenant',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='onboarding_profile',
                        to='multitenancy.tenant',
                    ),
                ),
            ],
        ),
    ]
