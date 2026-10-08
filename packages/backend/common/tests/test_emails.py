from email.utils import formataddr
from unittest.mock import Mock, patch, MagicMock
import json
import subprocess
from celery.exceptions import Ignore

import pytest
from django.conf import settings

from django.core import mail
from ..emails import send_email

pytestmark = pytest.mark.django_db


class TestSendEmail:
    @patch('common.emails.subprocess.run')
    @patch('common.emails.send_email.update_state')
    def test_send_example_email(self, mock_update_state, mock_subprocess):
        # Mock the node subprocess to return a valid email JSON
        mock_process = Mock()
        mock_process.stdout = json.dumps(
            {
                'subject': 'Activate your account',
                'html': f'<p>Click <a href="http://localhost:3000/en/auth/confirm/test-user/test-token">here</a> to activate</p>',
            }
        ).encode('utf-8')
        mock_subprocess.return_value = mock_process

        to = 'test@example.org'
        email_type = 'ACCOUNT_ACTIVATION'
        email_data = {'token': 'test-token', 'user_id': 'test-user'}

        # Call the run method - celery binds self automatically, so we don't pass it
        send_email.run(to, email_type, email_data)

        assert len(mail.outbox) == 1

        sent_email = mail.outbox[0]
        assert sent_email.to == [to]
        assert sent_email.from_email == formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM_ADDRESS))
        assert f"http://localhost:3000/en/auth/confirm/{email_data['user_id']}/{email_data['token']}" in sent_email.body

    @patch('common.emails.subprocess.run')
    @patch('common.emails.send_email.update_state')
    def test_from_header_shows_klarvido_display_name_by_default(self, mock_update_state, mock_subprocess):
        mock_process = Mock()
        mock_process.stdout = json.dumps({'subject': 'Hello', 'html': '<p>Hi</p>'}).encode('utf-8')
        mock_subprocess.return_value = mock_process

        send_email.run('test@example.org', 'ACCOUNT_ACTIVATION', {})

        sent_email = mail.outbox[0]
        assert sent_email.from_email == f"Klarvido <{settings.EMAIL_FROM_ADDRESS}>"

    @patch('common.emails.subprocess.run')
    @patch('common.emails.send_email.update_state')
    def test_from_header_falls_back_to_bare_address_when_name_is_blank(
        self, mock_update_state, mock_subprocess, settings
    ):
        settings.EMAIL_FROM_NAME = ""
        mock_process = Mock()
        mock_process.stdout = json.dumps({'subject': 'Hello', 'html': '<p>Hi</p>'}).encode('utf-8')
        mock_subprocess.return_value = mock_process

        send_email.run('test@example.org', 'ACCOUNT_ACTIVATION', {})

        sent_email = mail.outbox[0]
        assert sent_email.from_email == settings.EMAIL_FROM_ADDRESS


def test_renderer_failures_do_not_log_credential_links(caplog):
    secret = 'private-reset-token-value'
    with patch(
        'common.emails.subprocess.run',
        side_effect=subprocess.CalledProcessError(
            1,
            ['node'],
            output=secret.encode(),
            stderr=secret.encode(),
        ),
    ), patch('common.emails.send_email.update_state') as state:
        with pytest.raises(Ignore):
            send_email.run('private@example.com', 'PASSWORD_RESET', {'token': secret})
    assert secret not in caplog.text
    assert 'private@example.com' not in caplog.text
    assert state.call_args.kwargs['meta'] == {'reason': 'email_rendering_failed'}
