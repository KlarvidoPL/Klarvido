import copy

from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from apps.sso.models import SSOSession

from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings
from django.contrib import auth as dj_auth
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext as _
from graphql_relay import from_global_id, to_global_id
from hashid_field import rest
from rest_framework import exceptions, serializers, validators
from rest_framework_simplejwt import serializers as jwt_serializers, tokens as jwt_tokens, exceptions as jwt_exceptions
from rest_framework_simplejwt.serializers import PasswordField
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.utils import get_md5_hash_password
from common.decorators import context_user_required

from apps.sso.services import passkey_management

from . import models, tokens, jwt, notifications
from .exceptions import OTPAttemptLimitExceeded, OTPVerificationFailure, PasswordBudgetExceeded
from .services.security import enqueue_email, record
from .services.password_recovery import admit_reset
from .services.password_policy import validate_password
from .services.password_budget import check_password as check_password_budget, clear as clear_password_budget
from .services.default_organization import accessible_organization
from .services.users import get_role_names
from .services import otp as otp_services
from .services.otp_login import begin_otp_login, consume_pending_login, find_pending_login

UPLOADED_AVATAR_SIZE_LIMIT = 5 * 1024 * 1024


class UserProfileSerializer(serializers.ModelSerializer):
    id = rest.HashidSerializerCharField(source_field="users.User.id", source="user.id", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    roles = serializers.SerializerMethodField()
    avatar = serializers.FileField(required=False)
    language = serializers.ChoiceField(
        choices=models.LanguageChoices.choices,
        required=False,
    )

    class Meta:
        model = models.UserProfile
        fields = ("id", "first_name", "last_name", "email", "roles", "avatar", "language")

    @staticmethod
    def validate_avatar(avatar):
        if avatar and avatar.size > UPLOADED_AVATAR_SIZE_LIMIT:
            raise exceptions.ValidationError({"avatar": _("Too large file")}, "too_large")

        return avatar

    def get_roles(self, obj):
        return get_role_names(obj.user)

    def to_representation(self, instance):
        self.fields["avatar"] = serializers.FileField(source="avatar.thumbnail", default="")
        return super().to_representation(instance)

    def update(self, instance, validated_data):
        avatar = validated_data.pop("avatar", None)
        if avatar:
            if not instance.avatar:
                instance.avatar = models.UserAvatar()
            instance.avatar.original = avatar
            instance.avatar.save()
        return super().update(instance, validated_data)


class UserSignupSerializer(serializers.ModelSerializer):
    ok = serializers.BooleanField(read_only=True)
    id = rest.HashidSerializerCharField(source_field="users.User.id", read_only=True)
    email = serializers.EmailField(
        validators=[validators.UniqueValidator(queryset=dj_auth.get_user_model().objects.all())],
    )
    password = serializers.CharField(write_only=True)
    # The locale the signup page was rendered in (e.g. from the /pl/auth/signup
    # URL) - plain CharField rather than a ChoiceField so an unrecognized value
    # never blocks signup itself; create() falls back to English instead.
    language = serializers.CharField(write_only=True, required=False, allow_blank=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    class Meta:
        model = dj_auth.get_user_model()
        fields = ("id", "email", "password", "language", "access", "refresh", "ok")

    def validate(self, attrs):
        try:
            validate_password(attrs['password'], models.User(email=attrs['email']))
        except DjangoValidationError as error:
            raise exceptions.ValidationError({'password': serializers.as_serializer_error(error)['non_field_errors']})
        return attrs

    def create(self, validated_data):
        language = validated_data.get("language") or ""
        if language not in models.LanguageChoices.values:
            language = models.LanguageChoices.ENGLISH

        user = dj_auth.get_user_model().objects.create_user(
            validated_data["email"],
            validated_data["password"],
            language=language,
        )

        refresh = jwt_tokens.RefreshToken.for_user(user)
        refresh['auth_method'] = 'password'

        if jwt_api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)

        enqueue_email(user, 'ACCOUNT_ACTIVATION')

        return {
            "ok": True,
            "id": user.id,
            "email": user.email,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class UserAccountConfirmationSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=models.User.objects.all(),
        pk_field=rest.HashidSerializerCharField(),
        write_only=True,
    )
    token = serializers.CharField(write_only=True)
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        token = attrs["token"]
        user = attrs["user"]

        # The token hash mixes in is_confirmed (see
        # tokens.AccountActivationTokenGenerator), so once an account is
        # confirmed the *original* token would otherwise stop matching
        # (Django's standard invalidate-after-use pattern) and even the
        # correct link would wrongly show "invalid token" on a re-click.
        # Check against the pre-confirmation state instead of bypassing
        # validation entirely - a wrong/mangled token must still be rejected
        # even after the account is already confirmed.
        check_user = user
        if user.is_confirmed:
            check_user = copy.copy(user)
            check_user.is_confirmed = False

        if not tokens.account_activation_token.check_token(check_user, token):
            raise exceptions.ValidationError(_("Malformed user account confirmation token"))

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Serialize with support recovery and recheck against current credentials.
        user = models.User.objects.select_for_update().get(pk=validated_data['user'].pk)
        self.validate({**validated_data, 'user': user})
        if not user.is_confirmed:
            user.is_confirmed = True
            user.save(update_fields=['is_confirmed'])
            record('auth_email_confirmation', request=self.context.get('request'), user=user)
        return {"ok": True}


class ResendConfirmationEmailSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    ok = serializers.BooleanField(read_only=True)

    def create(self, validated_data):
        user = validated_data["user"]

        if user.is_confirmed:
            return {"ok": False}

        notifications.AccountActivationEmail(
            user=user, data={"user_id": user.id.hashid, "token": tokens.account_activation_token.make_token(user)}
        ).send()

        return {"ok": True}


class RequestPasswordSetLinkSerializer(serializers.Serializer):
    """First password on a passwordless account with no passkey and no 2FA (E04) - the only
    case with no stronger factor available to prove freshness with a grant, so it gets a
    one-time emailed link instead, reusing the existing password-reset token/confirmation flow
    (the token is bound to the account's current - unusable - password hash exactly like a
    normal reset, so it works identically and dies the moment a password exists)."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        if attrs["user"].has_usable_password():
            raise exceptions.ValidationError(_("This account already has a password."))
        return attrs

    def create(self, validated_data):
        user = validated_data["user"]
        event = record('auth_password_set_link', request=self.context.get('request'), user=user)
        enqueue_email(user, 'PASSWORD_SET', event=event)
        return {"ok": True}


class UserAccountChangePasswordSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    old_password = serializers.CharField(write_only=True, required=False, allow_blank=True, help_text=_("Old password"))
    new_password = serializers.CharField(write_only=True, help_text=_("New password"))
    # Only meaningful when changing an *already-set* password on an account with 2FA enabled
    # (E04) - the old password alone is exactly what a hijacked session or a phished credential
    # already has; the current OTP code is the second factor that proves this is really the
    # account owner, not just whoever holds the old password.
    otp_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def validate(self, attrs):
        user = attrs["user"]
        request = self.context.get("request")

        # An OAuth-only account has no password to check against - Django sets it
        # "unusable" on signup, and check_password() would always return False for
        # it, so this is a first-time password *set*, not a change.
        if user.has_usable_password():
            old_password = attrs.get("old_password")
            if not old_password:
                raise exceptions.ValidationError({"old_password": _("This field is required.")}, "required")

            # Account-wide failure budget (E05), shared with login - guessing the old password
            # here is exactly as much a brute-force avenue as the login form itself.
            try:
                correct = check_password_budget(user.email, lambda: user.check_password(old_password))
            except PasswordBudgetExceeded as exc:
                raise exceptions.ValidationError({"old_password": str(exc)}, code="too_many_attempts")
            if not correct:
                raise exceptions.ValidationError({"old_password": _("Wrong old password")}, "wrong_password")

            if user.otp_enabled and user.otp_verified:
                otp_token = attrs.get("otp_token")
                if not otp_token:
                    raise exceptions.ValidationError({"otp_token": _("This field is required.")}, "required")
                try:
                    otp_services.validate_otp(user, otp_token, request)
                except (OTPVerificationFailure, OTPAttemptLimitExceeded) as exc:
                    raise exceptions.ValidationError({"otp_token": str(exc)}, code=exc.code)
        else:
            # First-ever password on a passwordless account (E04): a bare session is not
            # fresh-auth proof - a hijacked/left-open session could otherwise plant a
            # permanent password on an account the attacker doesn't actually own. Reuses the
            # same one-use, action-bound grant 2FA setup/disable already requires (passkey
            # ceremony, or - only when the account has no passkey either - its current OTP
            # code). An account with none of those (no password, no passkey, no 2FA) cannot
            # produce any grant and must use the emailed set-password link instead
            # (RequestPasswordSetLinkSerializer / the existing password-reset-confirm flow).
            with transaction.atomic():
                grant = passkey_management.require_grant(request, user, "password_set")
                passkey_management.consume_grant(grant)

        try:
            validate_password(attrs['new_password'], user)
        except DjangoValidationError as error:
            raise exceptions.ValidationError(
                {'new_password': serializers.as_serializer_error(error)['non_field_errors']}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = validated_data.pop("user")
        new_password = validated_data.pop("new_password")
        validated_data.pop("otp_token", None)
        was_passwordless = not user.has_usable_password()
        user.set_password(new_password)
        user.save()
        clear_password_budget(user.email)
        event = record(
            'auth_password_change',
            request=self.context.get('request'),
            user=user,
            outcome='password_set' if was_passwordless else 'changed',
        )
        enqueue_email(user, 'PASSWORD_CHANGED', event=event)

        refresh = jwt_tokens.RefreshToken.for_user(user)
        refresh['auth_method'] = 'password'

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True, help_text=_("User e-mail"))
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        user = None
        try:
            user = dj_auth.get_user_model().objects.get(email__iexact=attrs["email"].strip())
        except dj_auth.get_user_model().DoesNotExist:
            pass

        return {**attrs, "user": user}

    @transaction.atomic
    def create(self, validated_data):
        user = validated_data['user']
        outcome = admit_reset(
            self.context.get('request'), validated_data['email'], deliverable=bool(user and user.is_active)
        )
        event = record(
            'auth_password_reset_request',
            request=self.context.get('request'),
            user=user,
            email=validated_data.get('email', ''),
            outcome=outcome,
        )
        if outcome == 'accepted' and user and user.is_active:
            enqueue_email(user, 'PASSWORD_RESET', event=event)
        return {"ok": True}


class PasswordResetConfirmationSerializer(serializers.Serializer):
    # user field is a CharField by design to hide the information whether the user exists or not
    user = serializers.CharField(write_only=True)

    new_password = serializers.CharField(write_only=True, help_text=_("New password"))
    token = serializers.CharField(write_only=True, help_text=_("Token"))

    ok = serializers.BooleanField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def validate(self, attrs):
        token = attrs["token"]
        user_id = attrs["user"]

        try:
            user = models.User.objects.get(pk=user_id)
        except models.User.DoesNotExist:
            raise exceptions.ValidationError(_("Malformed password reset token"), "invalid_token")

        if not tokens.password_reset_token.check_token(user, token):
            raise exceptions.ValidationError(_("Malformed password reset token"), "invalid_token")

        try:
            validate_password(attrs['new_password'], user)
        except DjangoValidationError as error:
            raise exceptions.ValidationError(
                {'new_password': serializers.as_serializer_error(error)['non_field_errors']}
            )
        return {**attrs, "user": user}

    @transaction.atomic
    def create(self, validated_data):
        user = models.User.objects.select_for_update().get(pk=validated_data['user'].pk)
        if not tokens.password_reset_token.check_token(user, validated_data['token']):
            raise exceptions.ValidationError(_("Malformed password reset token"), "invalid_token")
        try:
            validate_password(validated_data['new_password'], user)
        except DjangoValidationError as error:
            raise exceptions.ValidationError(
                {'new_password': serializers.as_serializer_error(error)['non_field_errors']}
            )
        user.set_password(validated_data['new_password'])
        # Blacklist every outstanding token minted before this point - the browser that
        # completed this reset gets a brand-new one below instead (not blacklisted, since it
        # doesn't exist yet). Any other logged-in session's SSOSession row is separately
        # revoked in ChangePasswordMutation/PasswordResetConfirmationMutation.perform_mutate,
        # once the new session's ID is known to exclude from it.
        jwt.blacklist_user_tokens(user)
        user.save(update_fields=['password'])
        clear_password_budget(user.email)
        event = record('auth_password_reset', request=self.context.get('request'), user=user)
        enqueue_email(user, 'PASSWORD_CHANGED', event=event)

        self.user = user
        refresh = jwt_tokens.RefreshToken.for_user(user)
        refresh['auth_method'] = 'password'
        return {"ok": True, "access": str(refresh.access_token), "refresh": str(refresh)}


class CookieTokenObtainPairSerializer(jwt_serializers.TokenObtainPairSerializer):
    username_field = get_user_model().USERNAME_FIELD

    default_error_messages = {"no_active_account": _("No active account found with the given credentials")}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['auth_method'] = 'password'
        return token

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[self.username_field] = serializers.CharField(write_only=True)
        self.fields["password"] = PasswordField(write_only=True)
        self.fields["otp_auth_token"] = serializers.CharField(read_only=True, default=None)

    access = serializers.CharField(read_only=True, default=None)
    refresh = serializers.CharField(read_only=True, default=None)

    def validate(self, attrs):
        email = attrs.get(self.username_field, "")

        def attempt():
            try:
                return super(CookieTokenObtainPairSerializer, self).validate(attrs)
            except exceptions.AuthenticationFailed:
                return None

        # Account-wide failure budget (E05): the per-IP limit on this mutation lets a
        # distributed attacker spread guesses across many source addresses, never exhausting a
        # shared counter against one account. A locked account is rejected (generically) before
        # the real check runs at all - including a correct password, which is the whole point of
        # a real budget - and a failure's counter update commits independently of whatever the
        # calling mutation's transaction does afterward (see password_budget.check_password).
        try:
            data = check_password_budget(email, attempt)
        except PasswordBudgetExceeded as exc:
            raise exceptions.ValidationError({"non_field_errors": str(exc)}, code="too_many_attempts")

        if data is None:
            raise exceptions.ValidationError(self.error_messages["no_active_account"], code="no_active_account")

        return data

    def create(self, validated_data):
        if self.user.otp_enabled and self.user.otp_verified:
            return {"otp_auth_token": begin_otp_login(self.user, "password")}

        return validated_data


class CookieTokenRefreshSerializer(jwt_serializers.TokenRefreshSerializer):
    refresh = serializers.CharField(required=False)
    access = serializers.CharField(read_only=True)

    default_error_messages = {
        "invalid_token": _("No valid token found in cookie 'refresh_token' or field 'refresh'"),
    }

    @transaction.atomic
    def validate(self, attrs):
        request = self.context["request"]
        raw_token = request.COOKIES.get(settings.REFRESH_TOKEN_COOKIE) or attrs.get("refresh")

        if not raw_token:
            self.fail("invalid_token")

        try:
            refresh = jwt_tokens.RefreshToken(raw_token)
        except (jwt_exceptions.InvalidToken, jwt_exceptions.TokenError):
            self.fail("invalid_token")

        if refresh.get("auth_method") == "sso":
            self.fail("invalid_token")

        # Only refresh tokens this database issued itself. A token signed with the
        # right key but never recorded as outstanding here was minted elsewhere -
        # typically before the database was wiped, when its user ID belonged to a
        # different account (IDs start over after a wipe).
        old_jti = refresh.get("jti")
        if not old_jti or not OutstandingToken.objects.filter(jti=old_jti).exists():
            self.fail("invalid_token")

        # ...and only for the account it was issued to (CHECK_REVOKE_TOKEN: the
        # user's password-hash fingerprint must still match - also ends every
        # session once the password is changed or reset).
        user = (
            get_user_model()
            .objects.filter(**{jwt_api_settings.USER_ID_FIELD: refresh.get(jwt_api_settings.USER_ID_CLAIM)})
            .first()
        )
        if not user or not user.is_active:
            self.fail("invalid_token")
        if refresh.get(jwt_api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            self.fail("invalid_token")

        # Missing, expired, foreign, and revoked sessions cannot refresh. Lock
        # the row so rotation and revocation cannot leave an untracked token.
        # Reject the refresh if the session it belongs to has been revoked
        # (e.g. via "Sign out" on another device in Active Sessions). Without
        # this check, revoking a session only hides it from the session list
        # - the device itself would keep minting new access tokens forever.
        session = (
            SSOSession.objects.select_for_update()
            .filter(refresh_token_jti=old_jti, user=user, is_active=True, expires_at__gt=timezone.now())
            .first()
        )
        if not session:
            self.fail("invalid_token")

        if jwt_api_settings.ROTATE_REFRESH_TOKENS:
            if jwt_api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass

            auth_method = refresh.get('auth_method', 'password')
            new_refresh = jwt_tokens.RefreshToken.for_user(user)
            new_refresh['auth_method'] = auth_method
            new_refresh.access_token['auth_method'] = auth_method

            # Rotation mints a brand new refresh token (new jti) - re-point the
            # session's link so it stays revocable after this refresh too, and
            # extend its expiry / last activity along with it.
            session.extend(new_refresh.get("jti"))

            return {"access": str(new_refresh.access_token), "refresh": str(new_refresh)}

        return {"access": str(refresh.access_token)}


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False)
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        request = self.context["request"]
        # Try multiple sources for the refresh token (bulletproof for different proxy configs)
        raw_token = (
            request.COOKIES.get(settings.REFRESH_TOKEN_LOGOUT_COOKIE)
            or request.COOKIES.get(settings.REFRESH_TOKEN_COOKIE)
            or attrs.get("refresh")
        )

        if not raw_token:
            # No token found - still allow logout (just won't blacklist)
            return {"refresh": None}

        try:
            refresh = jwt_tokens.RefreshToken(raw_token)
            return {"refresh": refresh}
        except (jwt_exceptions.InvalidToken, jwt_exceptions.TokenError):
            # Token is invalid/expired - still allow logout
            return {"refresh": None}

    def create(self, validated_data):
        refresh = validated_data.get("refresh")
        if refresh:
            try:
                refresh.blacklist()
            except Exception:
                # Blacklisting failed - token might already be blacklisted
                pass

            # Also mark the linked SSOSession inactive, so a logged-out
            # device stops showing as "active" in Active Sessions.
            try:
                from apps.sso.models import SSOSession

                jti = refresh.get("jti")
                session = SSOSession.objects.filter(refresh_token_jti=jti, is_active=True).first()
                if session:
                    session.revoke(reason="User logged out")
            except Exception:
                # Session bookkeeping failing shouldn't block logout
                pass
        return {"ok": True}


def _otp_setup_requires_grant(user):
    # Replacing an already-active factor always needs fresh proof. First-time
    # enrollment only needs it when the account actually has a way to produce
    # proof - a password-less, passkey-less account (Google-only, 2FA never set
    # up) would otherwise be permanently unable to ever turn 2FA on.
    return user.otp_enabled or passkey_management.user_can_reauthenticate(user)


@context_user_required
class GenerateOTPSerializer(serializers.Serializer):
    base32 = serializers.CharField(read_only=True)
    otpauth_url = serializers.CharField(read_only=True)

    def validate(self, attrs):
        # Mirrors the passkey-registration "options" step: confirms a live grant
        # exists without consuming it, so the matching verifyOtp call can still
        # use it to promote the pending secret to active. require_grant() locks the
        # grant row, which needs an explicit transaction here (unlike the passkey
        # REST/GraphQL call sites, this validate() isn't already wrapped in one).
        if _otp_setup_requires_grant(self.context_user):
            with transaction.atomic():
                passkey_management.require_grant(self.context["request"], self.context_user, "otp_setup")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        otp_base32, otp_auth_url = otp_services.generate_otp(self.context_user)
        record(
            'auth_otp_management',
            request=self.context.get('request'),
            user=self.context_user,
            outcome='enrollment_started',
        )
        return {"base32": otp_base32, "otpauth_url": otp_auth_url}


@context_user_required
class VerifyOTPSerializer(serializers.Serializer):
    otp_verified = serializers.BooleanField(read_only=True)
    otp_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if _otp_setup_requires_grant(self.context_user):
            with transaction.atomic():
                grant = passkey_management.require_grant(self.context["request"], self.context_user, "otp_setup")
                passkey_management.consume_grant(grant)
        return attrs

    def create(self, validated_data):
        otp_services.verify_otp(self.context_user, validated_data.get("otp_token", ""), self.context.get('request'))
        return {"otp_verified": True}


class ValidateOTPSerializer(serializers.Serializer):
    user: models.User

    otp_token = serializers.CharField(write_only=True)
    otp_auth_token = serializers.CharField(required=False, write_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    default_error_messages = {
        "invalid_token": _(f"No valid token found in cookie '{settings.OTP_AUTH_TOKEN_COOKIE}'"),
    }

    def validate(self, attrs):
        request = self.context["request"]

        if not (
            raw_otp_auth_token := request.COOKIES.get(settings.OTP_AUTH_TOKEN_COOKIE) or attrs.get("otp_auth_token")
        ):
            self.fail("invalid_token")

        # find_pending_login rejects a missing/expired/used/foreign token, and - since
        # it was only ever created by begin_otp_login() for this exact account - also
        # anything that isn't a genuine pending-login proof (an ordinary access/refresh
        # token cannot satisfy this, unlike the previous self-signed-JWT design). It
        # also rejects a proof whose credential_version no longer matches: the account
        # was deactivated, its password changed/reset, or OTP enabled/disabled/replaced
        # since this proof was issued.
        pending = find_pending_login(raw_otp_auth_token)
        if pending is None:
            self.fail("invalid_token")
        self.user = pending.user
        if not self.user.is_active:
            self.fail("invalid_token")

        otp_services.validate_otp(self.user, attrs.get("otp_token", ""), request)
        self._raw_otp_auth_token = raw_otp_auth_token

        return attrs

    def create(self, validated_data):
        # Re-validate and consume under a row lock, in the same transaction as the
        # session this issues - so a concurrent duplicate submission of this same
        # proof cannot both succeed, and nothing can complete after credentials
        # changed between validate() and here.
        pending = consume_pending_login(self._raw_otp_auth_token)
        if pending is None:
            self.fail("invalid_token")

        self.auth_method = pending.auth_method
        refresh = RefreshToken.for_user(self.user)
        refresh['auth_method'] = pending.auth_method
        refresh.access_token['auth_method'] = pending.auth_method
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


@context_user_required
class DisableOTPSerializer(serializers.Serializer):
    ok = serializers.BooleanField(read_only=True)

    def validate(self, attrs):
        with transaction.atomic():
            grant = passkey_management.require_grant(self.context["request"], self.context_user, "otp_disable")
            passkey_management.consume_grant(grant)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        otp_services.disable_otp(self.context_user)
        event = record(
            'auth_otp_management', request=self.context.get('request'), user=self.context_user, outcome='disabled'
        )
        record('otp_disabled', request=self.context.get('request'), user=self.context_user)
        enqueue_email(self.context_user, 'OTP_DISABLED', event=event)
        return {"ok": True}


class OrganizationIdField(serializers.CharField):
    pass


class SetDefaultOrganizationSerializer(serializers.Serializer):
    organization_id = OrganizationIdField(required=False, allow_null=True, default=None, write_only=True)
    default_organization_id = OrganizationIdField(read_only=True, allow_null=True)

    def validate_organization_id(self, value):
        if value is None:
            return None
        node_type, node_id = from_global_id(value)
        if node_type and node_type != 'TenantType':
            raise exceptions.ValidationError(_('Organization is not available.'))
        organization = accessible_organization(self.context['request'], node_id if node_type else value)
        if not organization:
            raise exceptions.ValidationError(_('Organization is not available.'))
        return organization

    def create(self, validated_data):
        profile = self.context['request'].user.profile
        profile.default_organization = validated_data['organization_id']
        profile.save(update_fields=['default_organization'])
        return {
            'default_organization_id': (
                to_global_id('TenantType', str(profile.default_organization_id))
                if profile.default_organization_id
                else None
            )
        }
