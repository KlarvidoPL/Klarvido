import copy

from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings
from django.contrib import auth as dj_auth
from django.contrib.auth import password_validation, get_user_model
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext as _
from hashid_field import rest
from rest_framework import exceptions, serializers, validators
from rest_framework_simplejwt import serializers as jwt_serializers, tokens as jwt_tokens, exceptions as jwt_exceptions
from rest_framework_simplejwt.serializers import PasswordField
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.utils import get_md5_hash_password
from common.decorators import context_user_required

from . import models, tokens, jwt, notifications
from .services.users import get_role_names
from .services import otp as otp_services
from .utils import generate_otp_auth_token

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
        fields = ("id", "email", "password", "language", "access", "refresh")

    def validate_password(self, password):
        password_validation.validate_password(password)
        return password

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

        notifications.AccountActivationEmail(
            user=user, data={"user_id": user.id.hashid, "token": tokens.account_activation_token.make_token(user)}
        ).send()

        return {"id": user.id, "email": user.email, "access": str(refresh.access_token), "refresh": str(refresh)}


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

    def create(self, validated_data):
        user = validated_data.pop("user")
        user.is_confirmed = True
        user.save()
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


class UserAccountChangePasswordSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    old_password = serializers.CharField(write_only=True, required=False, allow_blank=True, help_text=_("Old password"))
    new_password = serializers.CharField(write_only=True, help_text=_("New password"))

    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)

    def validate_new_password(self, new_password):
        password_validation.validate_password(new_password)
        return new_password

    def validate(self, attrs):
        user = attrs["user"]

        # An OAuth-only account has no password to check against - Django sets it
        # "unusable" on signup, and check_password() would always return False for
        # it, so a first-time password set must skip this rather than being
        # permanently locked out of ever adding one.
        if user.has_usable_password():
            old_password = attrs.get("old_password")
            if not old_password:
                raise exceptions.ValidationError({"old_password": _("This field is required.")}, "required")
            if not user.check_password(old_password):
                raise exceptions.ValidationError({"old_password": _("Wrong old password")}, "wrong_password")

        return attrs

    def create(self, validated_data):
        user = validated_data.pop("user")
        new_password = validated_data.pop("new_password")
        user.set_password(new_password)
        user.save()

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
            user = dj_auth.get_user_model().objects.get(email=attrs["email"])
        except dj_auth.get_user_model().DoesNotExist:
            pass

        return {**attrs, "user": user}

    def create(self, validated_data):
        user = validated_data.pop("user")

        if user:
            notifications.PasswordResetEmail(
                user=user, data={"user_id": user.id.hashid, "token": tokens.password_reset_token.make_token(user)}
            ).send()

        return {"ok": True}


class PasswordResetConfirmationSerializer(serializers.Serializer):
    # user field is a CharField by design to hide the information whether the user exists or not
    user = serializers.CharField(write_only=True)

    new_password = serializers.CharField(write_only=True, help_text=_("New password"))
    token = serializers.CharField(write_only=True, help_text=_("Token"))

    ok = serializers.BooleanField(read_only=True)

    def validate_new_password(self, new_password):
        password_validation.validate_password(new_password)
        return new_password

    def validate(self, attrs):
        token = attrs["token"]
        user_id = attrs["user"]

        try:
            user = models.User.objects.get(pk=user_id)
        except models.User.DoesNotExist:
            raise exceptions.ValidationError(_("Malformed password reset token"), "invalid_token")

        if not tokens.password_reset_token.check_token(user, token):
            raise exceptions.ValidationError(_("Malformed password reset token"), "invalid_token")

        return {**attrs, "user": user}

    def create(self, validated_data):
        user = validated_data.pop("user")
        new_password = validated_data.pop("new_password")
        user.set_password(new_password)
        jwt.blacklist_user_tokens(user)
        user.save()
        return {"ok": True}


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
        try:
            data = super().validate(attrs)
        except exceptions.AuthenticationFailed as e:
            raise exceptions.ValidationError(e.detail)

        return data

    def create(self, validated_data):
        if self.user.otp_enabled and self.user.otp_verified:
            return {"otp_auth_token": str(generate_otp_auth_token(self.user))}

        return validated_data


class CookieTokenRefreshSerializer(jwt_serializers.TokenRefreshSerializer):
    refresh = serializers.CharField(required=False)
    access = serializers.CharField(read_only=True)

    default_error_messages = {
        "invalid_token": _("No valid token found in cookie 'refresh_token' or field 'refresh'"),
    }

    def validate(self, attrs):
        request = self.context["request"]
        raw_token = request.COOKIES.get(settings.REFRESH_TOKEN_COOKIE) or attrs.get("refresh")

        if not raw_token:
            self.fail("invalid_token")

        try:
            refresh = jwt_tokens.RefreshToken(raw_token)
        except (jwt_exceptions.InvalidToken, jwt_exceptions.TokenError):
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

        # Reject the refresh if the session it belongs to has been revoked
        # (e.g. via "Sign out" on another device in Active Sessions). Without
        # this check, revoking a session only hides it from the session list
        # - the device itself would keep minting new access tokens forever.
        from apps.sso.models import SSOSession

        session = SSOSession.objects.filter(refresh_token_jti=old_jti).first() if old_jti else None
        if session and not session.is_active:
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
            if session:
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


@context_user_required
class GenerateOTPSerializer(serializers.Serializer):
    base32 = serializers.CharField(read_only=True)
    otpauth_url = serializers.CharField(read_only=True)

    def create(self, validated_data):
        otp_base32, otp_auth_url = otp_services.generate_otp(self.context_user)
        return {"base32": otp_base32, "otpauth_url": otp_auth_url}


@context_user_required
class VerifyOTPSerializer(serializers.Serializer):
    otp_verified = serializers.BooleanField(read_only=True)
    otp_token = serializers.CharField(write_only=True)

    def create(self, validated_data):
        otp_services.verify_otp(self.context_user, validated_data.get("otp_token", ""))
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

        try:
            otp_auth_token = jwt_tokens.AccessToken(raw_otp_auth_token)
        except (jwt_exceptions.InvalidToken, jwt_exceptions.TokenError):
            self.fail("invalid_token")

        if not (user_id := otp_auth_token.get("user_id")):
            self.fail("invalid_token")

        try:
            self.user = models.User.objects.get(id=user_id)
        except models.User.DoesNotExist:
            self.fail("invalid_token")

        otp_services.validate_otp(self.user, attrs.get("otp_token", ""))

        return attrs

    def create(self, validated_data):
        refresh = RefreshToken.for_user(self.user)
        refresh['auth_method'] = 'password'
        refresh.access_token['auth_method'] = 'password'
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


@context_user_required
class DisableOTPSerializer(serializers.Serializer):
    ok = serializers.BooleanField(read_only=True)

    def create(self, validated_data):
        otp_services.disable_otp(self.context_user)
        return {"ok": True}
