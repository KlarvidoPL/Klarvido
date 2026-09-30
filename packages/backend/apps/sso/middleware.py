"""
Middleware keeping "last activity" in Active Sessions accurate.
"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import SSOSession

logger = logging.getLogger(__name__)

# How often (at most) a session's last_activity_at is written, so activity costs one small write per device per
# interval instead of one per request
SESSION_ACTIVITY_WRITE_INTERVAL_SECONDS = 60


class SessionActivityMiddleware:
    """
    Records activity on the user's session for every authenticated request, not only on token refresh (which happens
    at most every ACCESS_TOKEN_LIFETIME, so "last activity" would lag by up to that).

    Runs after the view: API/GraphQL requests are authenticated by DRF inside the view, which then sets request.user.
    The session is found through the session_id cookie set at login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        session_id = request.COOKIES.get(settings.SESSION_ID_COOKIE)
        user = getattr(request, "user", None)
        if session_id and user is not None and user.is_authenticated:
            self.record_activity(user, session_id)

        return response

    @staticmethod
    def record_activity(user, session_id: str):
        # cache.add only succeeds when the key doesn't exist yet: the first request in each interval writes
        if not cache.add(f"session-activity:{session_id}", 1, timeout=SESSION_ACTIVITY_WRITE_INTERVAL_SECONDS):
            return
        try:
            SSOSession.objects.filter(session_id=session_id, user=user, is_active=True).update(
                last_activity_at=timezone.now()
            )
        except Exception:  # noqa: BLE001 - activity tracking must never break the request itself
            logger.exception("Failed to record session activity")
