"""Seed security-flow messages and replace English placeholders without overwriting reviewed translations."""

import json
from pathlib import Path

from django.db import migrations


def seed_security_translations(apps, schema_editor):
    key_model = apps.get_model('translations', 'TranslationKey')
    locale_model = apps.get_model('translations', 'Locale')
    translation_model = apps.get_model('translations', 'Translation')
    database = schema_editor.connection.alias
    payload = json.loads((Path(__file__).parent / 'data' / '0005_social_security_translations.json').read_text())
    texts = payload['translations']
    for identifier, english in texts['en'].items():
        key, _ = key_model.objects.using(database).get_or_create(
            key=identifier, defaults={'default_message': english}
        )
        for code, messages in texts.items():
            locale = locale_model.objects.using(database).filter(code=code).first()
            if locale is None:
                continue
            row, created = translation_model.objects.using(database).get_or_create(
                key=key, locale=locale, defaults={'value': messages[identifier], 'status': 'published'}
            )
            if not created and (not row.value.strip() or (code != 'en' and row.value == english)):
                row.value = messages[identifier]
                row.status = 'published'
                row.save(using=database, update_fields=['value', 'status'])


class Migration(migrations.Migration):
    dependencies = [('translations', '0004_remove_translation_unique_translation_key_locale_and_more')]
    operations = [migrations.RunPython(seed_security_translations, migrations.RunPython.noop)]
