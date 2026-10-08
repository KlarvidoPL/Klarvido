"""Publish authentication UI and notification translations without replacing custom text."""

import json
from pathlib import Path
from django.db import migrations


def add_messages(apps, schema_editor):
    keys = apps.get_model('translations', 'TranslationKey')
    locales = apps.get_model('translations', 'Locale')
    translations = apps.get_model('translations', 'Translation')
    db = schema_editor.connection.alias
    payload = json.loads((Path(__file__).parent / 'data' / '0007_auth_security_translations.json').read_text())
    for identifier, entry in payload.items():
        key, _ = keys.objects.using(db).get_or_create(
            key=identifier, defaults={'default_message': entry['default_message']},
        )
        for locale in locales.objects.using(db).filter(code__in=entry['values']):
            row, created = translations.objects.using(db).get_or_create(
                key=key, locale=locale,
                defaults={'value': entry['values'][locale.code], 'status': 'published'},
            )
            if not created and (not row.value.strip() or (
                locale.code != 'en' and row.value == entry['default_message']
            )):
                row.value = entry['values'][locale.code]
                row.status = 'published'
                row.save(using=db, update_fields=['value', 'status'])


class Migration(migrations.Migration):
    dependencies = [('translations', '0006_restore_locale_translations')]
    operations = [migrations.RunPython(add_messages, migrations.RunPython.noop)]
