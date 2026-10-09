"""Context-aware password validation without changing existing login credentials."""
from types import SimpleNamespace

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ApplicationPasswordValidator:
    # A local supplement to Django's maintained common-password corpus.
    blocked = frozenset(
        {'klarvido', 'klarvido123', 'klarvido123!', 'klarvidopassword', 'apptension', 'saasboilerplate'}
    )

    def validate(self, password, user=None):
        if password.casefold() in self.blocked:
            raise ValidationError(_('This password is too common.'), code='password_too_common')

    def get_help_text(self):
        return _('Your password cannot be a commonly used password.')


def validate_password(password, user):
    profile = getattr(user, 'profile', None)
    context = SimpleNamespace(
        _meta=user._meta,
        email=user.email,
        first_name=getattr(profile, 'first_name', ''),
        last_name=getattr(profile, 'last_name', ''),
        username=user.email.split('@', 1)[0],
    )
    password_validation.validate_password(password, user=context)
