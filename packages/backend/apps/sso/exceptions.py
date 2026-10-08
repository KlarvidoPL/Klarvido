"""Domain errors for passkey resource limits."""


class PasskeyChallengeCapacityExceeded(Exception):
    """No more challenge rows may be created until capacity is reclaimed."""
