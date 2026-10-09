"""
KSeF tokens must never reach error reporting: Sentry must not capture local variables (where the plaintext token
lives while it is checked) and request data is redacted for token-like keys at any depth.
"""

from unittest.mock import patch

import pytest

from config import monitoring

pytestmark = pytest.mark.django_db


def test_sentry_does_not_capture_local_variables():
    with patch.object(monitoring.sentry_sdk, "init") as init:
        monitoring.init(dsn="https://key@example.invalid/1", environment_name="test", traces_sample_rate=0)

    assert init.call_args.kwargs["include_local_variables"] is False


def test_request_data_redacts_token_keys_at_any_depth():
    data = {
        "query": "mutation { setKsefToken }",
        "variables": {"tenantId": "VGVuYW50VHlwZTox", "token": "plaintext-ksef-token"},
        "batch": [{"nested": {"KSEF_TOKEN": "another-token"}}],
    }

    redacted = monitoring._redact(data)

    # Serialized GraphQL bodies are withheld entirely, including non-secret variables.
    assert redacted["variables"] == "[Filtered]"
    assert redacted["query"] == "[Filtered]"
    assert redacted["batch"][0]["nested"]["KSEF_TOKEN"] == "[Filtered]"
    assert "plaintext-ksef-token" not in str(redacted)
    assert data["variables"]["token"] == "plaintext-ksef-token"
