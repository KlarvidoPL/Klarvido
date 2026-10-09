"""Guard against exporting English fallbacks over existing locale translations."""

import importlib
import json
from io import StringIO
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import connection

from apps.translations.models import Translation
from .factories import LocaleFactory, TranslationFactory, TranslationKeyFactory

pytestmark = pytest.mark.django_db


def test_export_marks_published_values_separately_from_english_fallbacks():
    locale = LocaleFactory(code='pl')
    published = TranslationKeyFactory(key='Example / Published', default_message='Published')
    missing = TranslationKeyFactory(key='Example / Missing', default_message='Missing')
    draft = TranslationKeyFactory(key='Example / Draft', default_message='Draft')
    TranslationFactory(key=published, locale=locale, value='Opublikowane')
    TranslationFactory(key=draft, locale=locale, value='Wersja robocza', status=Translation.Status.DRAFT)
    output = StringIO()
    call_command('export_translations', format='json-dump', stdout=output)
    payload = json.loads(output.getvalue())
    assert payload['translations']['pl'][published.key] == 'Opublikowane'
    assert payload['translations']['pl'][missing.key] == 'Missing'
    assert published.key in payload['published_keys']['pl']
    assert missing.key not in payload['published_keys']['pl']
    assert draft.key not in payload['published_keys']['pl']


def test_locale_repair_restores_placeholder_but_keeps_custom_admin_text():
    locale = LocaleFactory(code='pl')
    key = TranslationKeyFactory(
        key='Companies / Empty title', default_message="You don't have any organizations yet", is_deprecated=True
    )
    row = TranslationFactory(key=key, locale=locale, value=key.default_message)
    migration = importlib.import_module('apps.translations.migrations.0006_restore_locale_translations')
    migration.restore_locale_translations(apps, SimpleNamespace(connection=connection))
    row.refresh_from_db()
    key.refresh_from_db()
    assert row.value == 'Nie masz jeszcze organizacji'
    assert not key.is_deprecated
    row.value = 'Własny tekst administratora'
    row.save()
    migration.restore_locale_translations(apps, SimpleNamespace(connection=connection))
    row.refresh_from_db()
    assert row.value == 'Własny tekst administratora'


def test_auth_messages_replace_english_placeholders_but_preserve_custom_text():
    locale = LocaleFactory(code='pl')
    key = TranslationKeyFactory(key='Auth / Signup / Check email title', default_message='Check your email')
    row = TranslationFactory(key=key, locale=locale, value='Check your email')
    migration = importlib.import_module('apps.translations.migrations.0007_auth_security_translations')
    migration.add_messages(apps, SimpleNamespace(connection=connection))
    row.refresh_from_db()
    assert row.value == 'Sprawdź swoją skrzynkę e-mail'
    row.value = 'Własna treść administratora'
    row.save()
    migration.add_messages(apps, SimpleNamespace(connection=connection))
    row.refresh_from_db()
    assert row.value == 'Własna treść administratora'
