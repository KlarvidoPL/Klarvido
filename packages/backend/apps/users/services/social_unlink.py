"""Fresh, account-bound ownership proof for removing a social login method."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from social_django.models import UserSocialAuth

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, UserPasskey, WebAuthnChallenge
from apps.sso.services.passkey_management import validate_password_proof
from apps.sso.services.sessions import SessionService
from apps.sso.services.webauthn import WebAuthnService
from apps.users.models import User, SocialAccountUnlinkChallenge, PendingSocialAccountLink
from .social_linking import credential_version


def target(user, identifier):
    if not isinstance(identifier, str) or not identifier.isdecimal() or len(identifier) > 20:
        raise ValidationError('Invalid social account')
    association = UserSocialAuth.objects.filter(user=user, pk=identifier).first()
    if association is None:
        raise ValidationError('Invalid social account')
    return association


def can_unlink(user, association):
    return bool(
        user.has_usable_password()
        or UserPasskey.objects.filter(user=user, is_active=True).exists()
        or UserSocialAuth.objects.filter(user=user).exclude(pk=association.pk).exists()
    )


@transaction.atomic
def unlink_options(user, identifier):
    account = User.objects.select_for_update().get(pk=user.pk)
    association = target(account, identifier)
    if not account.is_active or not can_unlink(account, association):
        raise PermissionDenied('Another login method is required')
    if not UserPasskey.objects.filter(user=account, is_active=True).exists():
        raise PermissionDenied('An existing passkey is required')
    options, challenge = WebAuthnService(account).create_authentication_options()
    record = WebAuthnChallenge.objects.get(challenge=challenge)
    record.challenge_type = 'social-unlink'
    record.save(update_fields=['challenge_type'])
    SocialAccountUnlinkChallenge.objects.create(
        association=association, challenge=record, credential_version=credential_version(account)
    )
    return options


def unlink_account(user, data, ip_address):
    # Password/OTP failures must retain their attempt counters outside the mutation transaction.
    version = credential_version(user)
    if not data.get('challenge'):
        validate_password_proof(user, data)
    error = None
    with transaction.atomic():
        account = User.objects.select_for_update().get(pk=user.pk)
        association = target(account, data['associationId'])
        if not account.is_active or credential_version(account) != version:
            raise PermissionDenied('Fresh authentication failed')
        if not can_unlink(account, association):
            raise PermissionDenied('Another login method is required')
        if data.get('challenge'):
            pending = SocialAccountUnlinkChallenge.objects.filter(
                association=association, challenge__challenge=data['challenge']
            ).first()
            if pending is None or pending.credential_version != credential_version(account):
                raise PermissionDenied('Fresh authentication failed')
            try:
                WebAuthnService(account).verify_authentication(
                    challenge=data['challenge'],
                    credential_id=data['credentialId'],
                    authenticator_data=data['authenticatorData'],
                    client_data_json=data['clientDataJSON'],
                    signature=data['signature'],
                    user_handle=data.get('userHandle'),
                    ip_address=ip_address,
                    challenge_type='social-unlink',
                )
            except ValueError as exc:
                error = exc
        if error is None:
            provider, identifier = association.provider, str(association.pk)
            association.delete()
            # Also cancel in-flight links, so an old confirmation cannot reconnect the provider.
            PendingSocialAccountLink.objects.filter(user=account).delete()
            SessionService(account).revoke_all_sessions()
            SSOAuditLog.log_event(
                SSOAuditEventType.SSO_LOGIN_SUCCESS,
                user=account,
                ip_address=ip_address,
                description='Social login disconnected after fresh authentication; sessions revoked',
                metadata={'provider': provider, 'action': 'account_unlinked', 'association_id': identifier},
            )
    if error is not None:
        raise PermissionDenied('Fresh authentication failed')
