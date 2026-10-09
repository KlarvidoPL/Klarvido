"""Repair lost locale values while preserving administrator translations."""

import json
from pathlib import Path

from django.db import migrations


def restore_locale_translations(apps, schema_editor):
    key_model = apps.get_model('translations', 'TranslationKey')
    locale_model = apps.get_model('translations', 'Locale')
    translation_model = apps.get_model('translations', 'Translation')
    database = schema_editor.connection.alias
    payload = json.loads((Path(__file__).parent / 'data' / '0006_restore_locale_translations.json').read_text())
    locales = {locale.code: locale for locale in locale_model.objects.using(database).all()}
    for identifier, entry in payload.items():
        key, _ = key_model.objects.using(database).get_or_create(
            key=identifier, defaults={'default_message': entry['default_message']}
        )
        # Restored keys may have been deprecated by an incomplete extraction.
        key.is_deprecated = False
        if entry.get('update_default'):
            key.default_message = entry['default_message']
        key.save(using=database, update_fields=['is_deprecated', 'default_message'])
        for code, text in entry['values'].items():
            locale = locales.get(code)
            if locale is None:
                continue
            row, created = translation_model.objects.using(database).get_or_create(
                key=key, locale=locale, defaults={'value': text, 'status': 'published'}
            )
            if not created and (not row.value.strip() or row.value in entry['replace_values'].get(code, [])):
                row.value = text
                row.status = 'published'
                row.save(using=database, update_fields=['value', 'status'])


class Migration(migrations.Migration):
    dependencies = [('translations', '0005_social_security_translations')]
    operations = [migrations.RunPython(restore_locale_translations, migrations.RunPython.noop)]
