"""
Tests for AI Assistant GraphQL subscription.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from apps.integrations.ai_assistant.subscription import (
    AiChatSubscription,
    SendAiMessageMutation,
)


@pytest.mark.django_db
class TestAiChatSubscription:
    """Tests for AiChatSubscription."""

    def test_subscribe_returns_empty_for_unauthenticated(self):
        info = MagicMock()
        info.context.channels_scope = {"user": None}
        result = AiChatSubscription.subscribe(None, info, "conv-123")
        assert result == []

    def test_subscribe_returns_empty_for_anonymous_user(self):
        info = MagicMock()
        user = MagicMock()
        user.is_authenticated = False
        info.context.channels_scope = {"user": user}
        result = AiChatSubscription.subscribe(None, info, "conv-123")
        assert result == []

    def test_subscribe_returns_channel_for_authenticated_user(self, user):
        info = MagicMock()
        info.context.channels_scope = {"user": user}
        result = AiChatSubscription.subscribe(None, info, "conv-123")
        assert result == [f"ai_chat_{user.id}_conv-123"]

    @pytest.mark.django_db(transaction=True)
    def test_publish_returns_event(self, user):
        payload = {
            "event_type": "status",
            "message": "Connecting...",
        }
        info = MagicMock()
        info.context.channels_scope = {"user": user}
        result = asyncio.run(AiChatSubscription.publish(payload, info, "conv-123"))
        assert result.event is not None
        assert result.event.event_type == "status"
        assert result.event.message == "Connecting..."

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize('deleted', [False, True])
    def test_publish_drops_events_for_revoked_accounts(self, user, deleted):
        info = MagicMock()
        info.context.channels_scope = {'user': user}
        if deleted:
            user.__class__.objects.filter(pk=user.pk).delete()
        else:
            user.__class__.objects.filter(pk=user.pk).update(is_active=False)
        assert asyncio.run(AiChatSubscription.publish({'event_type': 'status'}, info, 'conv-123')) is None


@pytest.mark.django_db
class TestSendAiMessageMutation:
    """Tests for SendAiMessageMutation."""

    def test_mutate_returns_error_for_unauthenticated(self):
        info = MagicMock()
        info.context.user = None
        result = SendAiMessageMutation.mutate(None, info, "Hello", "tenant-1", "conv-1", history=None)
        assert result.ok is False
        assert "Authentication" in result.error

    def test_mutate_returns_ok_and_starts_processing(self, user):
        info = MagicMock()
        info.context.user = user
        info.context.COOKIES = {}
        info.context.channels_scope = {}

        with patch.object(SendAiMessageMutation, "_process_message_sync") as mock_process:
            result = SendAiMessageMutation.mutate(None, info, "Hello", "tenant-1", "conv-1", history=None)
            assert result.ok is True
            mock_process.assert_called_once()
            call_args = mock_process.call_args
            assert call_args[0][0] == user.id
            assert call_args[0][1] == "Hello"
            assert call_args[0][2] == "tenant-1"
            assert call_args[0][3] == "conv-1"
