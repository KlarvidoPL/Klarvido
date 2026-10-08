import logging

from django.db import transaction

from common import emails
from . import email_serializers

logger = logging.getLogger(__name__)


def send_after_commit(email):
    """Queue an email once the current transaction actually commits, without letting
    a failure to queue it affect the caller.

    A notification is a side effect of a security-sensitive action (account reclaim,
    social-account linking) succeeding - it must never roll back that action, and it
    must never fire for a change that itself gets rolled back for an unrelated reason.
    transaction.on_commit() alone gets the ordering right; the try/except is needed
    on top of it because an on_commit callback that raises still propagates into the
    request/response cycle, which would turn a successful mutation into a 500 just
    because the notification could not be queued (e.g. the broker is unreachable).
    """

    def _send():
        try:
            email.send()
        except Exception:
            logger.exception("Failed to queue %s notification to %s", email.name, email.to)

    transaction.on_commit(_send)


def get_user_language(user):
    """Get user's preferred language, with fallback to default."""
    try:
        if hasattr(user, "profile") and user.profile and user.profile.language:
            return user.profile.language
    except Exception:
        pass
    return emails.DEFAULT_EMAIL_LANGUAGE


class UserEmail(emails.Email):
    def __init__(self, user, data=None):
        lang = get_user_language(user)
        super().__init__(to=user.email, data=data, lang=lang)


class AccountActivationEmail(UserEmail):
    name = "ACCOUNT_ACTIVATION"
    serializer_class = email_serializers.AccountActivationEmailSerializer


class PasswordResetEmail(UserEmail):
    name = "PASSWORD_RESET"
    serializer_class = email_serializers.PasswordResetEmailSerializer


class SocialAccountLinkedEmail(UserEmail):
    name = "SOCIAL_ACCOUNT_LINKED"
    serializer_class = email_serializers.SocialAccountLinkedEmailSerializer


class OtpEnabledEmail(UserEmail):
    name = "OTP_ENABLED"
    serializer_class = email_serializers.NoDataEmailSerializer


class OtpDisabledEmail(UserEmail):
    name = "OTP_DISABLED"
    serializer_class = email_serializers.NoDataEmailSerializer
