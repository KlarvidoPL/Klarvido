import json
import logging
from unittest.mock import Mock

import pytest

from config.monitoring import processor, CredentialSafeFormatter
from config.tracing import CredentialSafeEmitter

pytestmark = pytest.mark.django_db


def event_with_secrets():
    return {
        'request': {
            'url': 'https://app.example.com/pl/auth/reset-password/confirm/user/private-reset',
            'headers': {'Cookie': 'private-cookie', 'Authorization': 'Bearer private-access'},
            'data': '{"password":"private-password"}',
        },
        'extra': {'serialized': '{"otpBase32":"private-seed"}', 'enrollment': 'otpauth://totp/app?secret=private-seed'},
        'breadcrumbs': [
            {'message': 'https://api.example.com/callback?code=private-code', 'data': {'token': 'private-reset'}}
        ],
        'transaction': '/pl/auth/confirm/user/private-reset',
        'message': 'Useful error without credentials',
        'extra_form': 'state=private-state&code=private-oauth',
        'extra_url': 'https://user:private-basic@api.example.com/path',
    }


def test_scrubs_all_event_surfaces_without_mutating_input():
    original = event_with_secrets()
    sanitized = processor(original, {})
    output = json.dumps(sanitized)
    for secret in (
        'private-reset',
        'private-cookie',
        'private-access',
        'private-password',
        'private-seed',
        'private-code',
        'private-state',
        'private-oauth',
        'private-basic',
    ):
        assert secret not in output
    assert sanitized['message'] == original['message']
    assert 'private-password' in json.dumps(original)


def test_logging_formatter_scrubs_serialized_body_and_url():
    formatter = CredentialSafeFormatter()
    record = logging.LogRecord(
        'auth', logging.ERROR, 'file', 1, 'Failure: %s', ('{"password":"private-password"}',), None
    )
    assert 'private-password' not in formatter.format(record)
    record = logging.LogRecord(
        'auth', logging.INFO, 'file', 1, 'GET %s', ('/pl/auth/confirm/user/private-reset',), None
    )
    assert 'private-reset' not in formatter.format(record)


def test_xray_redacts_at_export_boundary(mocker):
    emitter = CredentialSafeEmitter()
    send = mocker.patch.object(emitter, '_send_data')
    entity = Mock()
    entity.serialize.return_value = json.dumps(event_with_secrets())
    emitter.send_entity(entity)
    output = send.call_args.args[0]
    assert 'private-' not in output


def test_malformed_trace_is_dropped(mocker):
    emitter = CredentialSafeEmitter()
    send = mocker.patch.object(emitter, '_send_data')
    entity = Mock()
    entity.serialize.return_value = '{invalid'
    emitter.send_entity(entity)
    send.assert_not_called()
