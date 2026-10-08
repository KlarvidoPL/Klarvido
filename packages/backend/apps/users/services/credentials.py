"""Shared "security version" fingerprint for an account's active credentials.

Used to invalidate server-side proofs (pending social-account links, pending OTP
logins) the instant the credentials they were issued against change - password
reset/change, OTP enabled/disabled/replaced - without having to track down and
revoke each proof individually.
"""

import hashlib


def credential_version(user):
    state = f'{user.password}:{user.otp_enabled}:{user.otp_verified}:{user.otp_base32}'
    return hashlib.sha256(state.encode()).hexdigest()
