"""Support-assisted recovery for an unconfirmed account someone else claims as theirs.

Google login never reclaims an unconfirmed account automatically (see
apps.users.services.social_linking.begin_link) - a genuine user who just
forgot to confirm their email could already hold real org memberships or data,
and silently wiping that on a bare email match would be its own account-takeover
risk. This is the deliberate, audited alternative: a superuser confirms ownership
out of band (support conversation) and strips everything the original registrant
could have planted, while leaving organization data for support to review by hand.

Every outstanding authentication proof for the account must fail after this runs,
not just sessions/refresh tokens. Some of that is explicit here (passkeys, passkey
management grants, WebAuthn challenges, pending social links); the rest happens
because changing the password is itself a revocation signal elsewhere in the
system, and is only correct *because* those mechanisms exist independently of this
function - worth spelling out so a future reader doesn't assume it's a gap:
  - Any already-issued access token (covers every IsAuthenticated action, including
    a passkey registration mid-ceremony via PasskeyRegistrationVerifyView) is
    rejected on its very next use: SIMPLE_JWT's CHECK_REVOKE_TOKEN embeds a
    password-hash claim in every access token and checks it against the current
    password on each authenticated request (apps.users.authentication,
    REVOKE_TOKEN_CLAIM="hash_password") - set_unusable_password() below changes
    that hash immediately.
  - The separate pending-OTP-login proof (PendingOTPLogin, looked up by hash in
    ValidateOTPSerializer rather than going through the access-token auth class
    above) is explicitly deleted below, and would be rejected even if it weren't:
    its stored credential_version stops matching the moment the password changes.
  - A passkey authentication (login) challenge against a passkey this function
    just deactivated fails because WebAuthnService.verify_authentication's
    credential lookup filters is_active=True.
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from social_django.models import UserSocialAuth

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog, UserPasskey, WebAuthnChallenge, PasskeyManagementGrant
from apps.sso.services.sessions import SessionService
from apps.users import notifications, tokens, jwt
from apps.users.models import PendingOTPLogin, PendingSocialAccountLink, User
from apps.users.services import otp as otp_services


@transaction.atomic
def reclaim_unconfirmed_account(user: User, actor: User) -> User:
    """Strip an unconfirmed account's credentials so its rightful owner can claim it.

    Only the account's identity (email) and non-security data (profile, org
    memberships) survive. Must be called only after support has verified the
    requester owns the mailbox out of band - this function itself has no way
    to verify that.
    """
    if not actor.is_superuser:
        raise PermissionDenied("Only a superuser can reclaim an account.")

    account = User.objects.select_for_update().get(pk=user.pk)
    if account.is_confirmed:
        raise ValidationError("Only an unconfirmed account can be reclaimed.")

    account.set_unusable_password()
    account.save(update_fields=["password"])

    otp_services.disable_otp(account)
    UserPasskey.objects.filter(user=account, is_active=True).update(is_active=False)
    PasskeyManagementGrant.objects.filter(user=account).delete()
    WebAuthnChallenge.objects.filter(user=account).delete()
    SessionService(account).revoke_all_sessions()
    jwt.blacklist_user_tokens(account)
    PendingSocialAccountLink.objects.filter(user=account).delete()
    PendingOTPLogin.objects.filter(user=account).delete()
    UserSocialAuth.objects.filter(user=account).delete()

    SSOAuditLog.log_event(
        SSOAuditEventType.ACCOUNT_RECLAIMED,
        user=account,
        description="Unconfirmed account reclaimed by support: password, OTP, passkeys, "
        "sessions and social links revoked",
        metadata={"actor_id": str(actor.pk), "actor_email": actor.email},
    )

    notifications.send_after_commit(
        notifications.PasswordResetEmail(
            user=account,
            data={"user_id": account.id.hashid, "token": tokens.password_reset_token.make_token(account)},
        )
    )

    return account
