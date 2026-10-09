import six
from django.conf import settings
from django.utils.http import base36_to_int
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return "".join(map(six.text_type, [user.pk, timestamp, user.is_confirmed, user.password, user.email]))


class PasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def check_token(self, user, token):
        if not super().check_token(user, token):
            return False
        try:
            timestamp = base36_to_int(token.split('-', 1)[0])
        except (ValueError, IndexError):
            return False
        return self._num_seconds(self._now()) - timestamp <= settings.AUTH_PASSWORD_RESET_TIMEOUT

    def _make_hash_value(self, user, timestamp):
        last_login = "" if user.last_login is None else user.last_login.replace(microsecond=0, tzinfo=None)
        keys = [user.pk, user.password, last_login, timestamp, user.is_confirmed]
        return "".join(map(six.text_type, keys))


account_activation_token = AccountActivationTokenGenerator()
password_reset_token = PasswordResetTokenGenerator()
