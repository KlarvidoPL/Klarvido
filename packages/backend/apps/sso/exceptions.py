"""Domain errors for passkey resource limits."""

from rest_framework.exceptions import PermissionDenied


class PasskeyReauthenticationError(PermissionDenied):
    """A safe, specific reason available only to the authenticated account."""

    def __init__(self, code):
        super().__init__('Fresh authentication failed', code=code)
        self.reason = code


class PasskeyChallengeCapacityExceeded(Exception):
    """No more challenge rows may be created until capacity is reclaimed."""
