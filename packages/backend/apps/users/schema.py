import logging

from django.db import transaction
from apps.sso.services import SessionService
from rest_framework.exceptions import ValidationError

import graphene
from config import settings
from graphene import relay
from graphene_django.rest_framework.serializer_converter import get_graphene_type_from_serializer_field
from common.graphql.authorization import AuthorizedDjangoObjectType as DjangoObjectType

from common.acl import policies
from common.graphql import mutations
from common.graphql import ratelimit
from common.graphql.acl.decorators import permission_classes
from common.ratelimiting import RateLimitCategory, RateLimitKey
from apps.multitenancy.schema import TenantType
from .jwt import get_jti_from_refresh_token
from . import models
from . import serializers
from .services.security import audit_failures, record
from .services.default_organization import default_organization_id
from .services.users import get_user_from_resolver, get_role_names, get_user_avatar_url
from .services.social_linking import complete_link


logger = logging.getLogger(__name__)


def _create_session_for_user(user, request, refresh_token: str, *, link_social=False):
    """Authentication must have a durable, revocable session before setting cookies."""
    try:
        jti = get_jti_from_refresh_token(refresh_token)
        if not user or not jti:
            raise ValueError("Missing session owner or refresh token")
        _, session_id = SessionService(user).create_session(request, refresh_token_jti=jti)
        if link_social:
            complete_link(request, user)
        return session_id
    except Exception:
        logger.error("Authentication session creation failed")
        raise ValidationError("Unable to establish a session. Please try again.")


class CookieAuthenticationMutation(mutations.SerializerMutation):
    """Tokens remain internal to the mutation and are delivered only as HttpOnly cookies."""

    class Meta:
        abstract = True

    authenticated = graphene.Boolean(required=True)

    @staticmethod
    def resolve_authenticated(root, info):
        return bool(getattr(root, "access", None))

    @staticmethod
    def resolve_access(root, info):
        return None

    @staticmethod
    def resolve_refresh(root, info):
        return None


class ObtainTokenMutation(CookieAuthenticationMutation):
    otp_required = graphene.Boolean(required=True)

    @staticmethod
    def resolve_otp_required(root, info):
        return bool(root.otp_auth_token)

    @staticmethod
    def resolve_otp_auth_token(root, info):
        return None

    class Meta:
        serializer_class = serializers.CookieTokenObtainPairSerializer

    @classmethod
    @ratelimit.ratelimit(key="ip", rate="30/min", fail_closed=True)
    @audit_failures('auth_password_login')
    def mutate_and_get_payload(cls, root, info, **input):
        # A validation failure here (wrong password / locked budget) has no other side effect
        # that needs rolling back: CookieTokenObtainPairSerializer.validate() raises before any
        # token is minted, so the only write involved is the password failure budget's counter
        # (E05), committed from its own nested atomic block inside .validate(). That commit must
        # survive the ValidationError .validate() then raises - so it is caught *inside* the
        # `with` block below (letting the block exit normally and commit) and re-raised only
        # once we are safely outside it, instead of letting the exception propagate through the
        # `with` statement itself and roll everything in it back. A session-creation failure
        # below, by contrast, must still roll back the just-minted tokens together with it - so
        # it is deliberately NOT given the same treatment.
        failure = None
        with transaction.atomic():
            try:
                mutation = super().mutate_and_get_payload(root, info, **input)
            except ValidationError as exc:
                failure = exc
            else:
                if mutation.otp_auth_token:
                    account = models.User.objects.get(email__iexact=input['email'])
                    record(
                        'auth_otp_challenge',
                        request=info.context._request,
                        user=account,
                        outcome='first_factor_verified',
                        method='password',
                    )
                    otp_cookies = {
                        settings.OTP_AUTH_TOKEN_COOKIE: mutation.otp_auth_token,
                    }
                else:
                    # Create session for tracking
                    user = getattr(mutation, "_user", None)
                    if not user:
                        # Try to get user from serializer
                        serializer = cls._meta.serializer_class
                        if hasattr(serializer, "user"):
                            user = serializer.user

                    # Get user from validated data - need to look it up by email
                    email = input.get("email")
                    if email and not user:
                        try:
                            user = models.User.objects.get(email__iexact=email)
                        except models.User.DoesNotExist:
                            user = None

                    session_id = _create_session_for_user(
                        user, info.context._request, refresh_token=mutation.refresh, link_social=True
                    )

                    record('auth_password_login', request=info.context._request, user=user, method='password')
                    auth_cookies = {
                        settings.ACCESS_TOKEN_COOKIE: mutation.access,
                        settings.REFRESH_TOKEN_COOKIE: mutation.refresh,
                    }

                    auth_cookies[settings.SESSION_ID_COOKIE] = session_id

        if failure is not None:
            raise failure

        if mutation.otp_auth_token:
            info.context._request.set_cookies = otp_cookies
        else:
            info.context._request.set_auth_cookie = auth_cookies

        return mutation


class SingUpMutation(CookieAuthenticationMutation):
    ok = graphene.Boolean(required=True)

    class Meta:
        serializer_class = serializers.UserSignupSerializer

    @classmethod
    @ratelimit.ratelimit(key="ip", rate="10/min", fail_closed=True)
    @audit_failures('auth_signup')
    def mutate_and_get_payload(cls, root, info, **input):
        with transaction.atomic():
            mutation = super().mutate_and_get_payload(root, info, **input)

            # Create session for the new user
            email = input.get("email")
            user = None
            if email:
                try:
                    user = models.User.objects.get(email__iexact=email)
                except models.User.DoesNotExist:
                    pass

            session_id = _create_session_for_user(user, info.context._request, refresh_token=mutation.refresh)
            record(
                'auth_signup', request=info.context._request, user=user, method='password', outcome='account_created'
            )

        auth_cookies = {
            settings.ACCESS_TOKEN_COOKIE: mutation.access,
            settings.REFRESH_TOKEN_COOKIE: mutation.refresh,
        }

        auth_cookies[settings.SESSION_ID_COOKIE] = session_id

        info.context._request.set_auth_cookie = auth_cookies

        return mutation


class ConfirmEmailMutation(mutations.SerializerMutation):
    ok = graphene.Boolean()

    class Meta:
        serializer_class = serializers.UserAccountConfirmationSerializer

    @classmethod
    @audit_failures('auth_email_confirmation')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


class PasswordResetMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.PasswordResetSerializer

    @classmethod
    @audit_failures('auth_password_reset_request')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


class PasswordResetConfirmationMutation(CookieAuthenticationMutation):
    class Meta:
        serializer_class = serializers.PasswordResetConfirmationSerializer

    @classmethod
    @audit_failures('auth_password_reset')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)

    @classmethod
    def perform_mutate(cls, serializer, info):
        # Completing a reset - whether the ordinary "forgot password" flow or the emailed
        # "set your first password" link (E04) - previously left the browser that completed it
        # with no working session at all: the old access token stops authenticating the moment
        # the password changes (its embedded password-hash fingerprint no longer matches) and
        # the old refresh token is blacklisted below, but nothing replaced them. The app looked
        # logged in (stale client-side cache) until the next reload, which then failed outright.
        # A session proven by a validated password-reset token is exactly as trustworthy as one
        # proven by a password, so mint this browser a fresh one immediately, and properly
        # revoke every other still-active session (not just blacklist their tokens) so the
        # Active Sessions list doesn't keep showing an already-dead entry as current.
        with transaction.atomic():
            mutation = super().perform_mutate(serializer, info)
            session_id = _create_session_for_user(serializer.user, info.context._request, mutation.refresh)
            SessionService(serializer.user).revoke_all_sessions(except_session_id=session_id)

        info.context._request.set_auth_cookie = {
            settings.SESSION_ID_COOKIE: session_id,
            settings.ACCESS_TOKEN_COOKIE: mutation.access,
            settings.REFRESH_TOKEN_COOKIE: mutation.refresh,
        }

        return mutation


class GenerateOTPMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.GenerateOTPSerializer

    @classmethod
    @audit_failures('auth_otp_management')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


class VerifyOTPMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.VerifyOTPSerializer

    @classmethod
    @audit_failures('auth_otp_management')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


class ValidateOTPMutation(CookieAuthenticationMutation):
    class Meta:
        serializer_class = serializers.ValidateOTPSerializer

    @classmethod
    @ratelimit.ratelimit(key="ip", rate=ratelimit.ip_throttle_rate, fail_closed=True)
    @audit_failures('auth_otp_verification')
    def mutate_and_get_payload(cls, root, info, **input):
        # Failed OTP checks must commit their account-wide attempt counters.
        # Only token issuance and session creation belong in the atomic block.
        try:
            return super().mutate_and_get_payload(root, info, **input)
        except ValidationError:
            cls._delete_otp_auth_token_cookie(info)
            raise

    @classmethod
    def perform_mutate(cls, serializer, info):
        with transaction.atomic():
            mutation = super().perform_mutate(serializer, info)
            session_id = _create_session_for_user(
                serializer.user, info.context._request, refresh_token=mutation.refresh, link_social=True
            )
            record(
                'auth_otp_verification',
                request=info.context._request,
                user=serializer.user,
                method=serializer.auth_method,
                outcome='login_completed',
            )

        auth_cookies = {
            settings.ACCESS_TOKEN_COOKIE: mutation.access,
            settings.REFRESH_TOKEN_COOKIE: mutation.refresh,
        }

        auth_cookies[settings.SESSION_ID_COOKIE] = session_id

        info.context._request.set_auth_cookie = auth_cookies
        cls._delete_otp_auth_token_cookie(info)

        return mutation

    @classmethod
    def _delete_otp_auth_token_cookie(cls, info):
        info.context._request.delete_cookies = [
            *getattr(info.context._request, 'delete_cookies', []),
            settings.OTP_AUTH_TOKEN_COOKIE,
        ]


class DisableOTPMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.DisableOTPSerializer

    @classmethod
    @audit_failures('auth_otp_management')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


class MarkWelcomeModalSeenMutation(graphene.ClientIDMutation):
    ok = graphene.Boolean()

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        profile = get_user_from_resolver(info).profile
        profile.has_seen_welcome_modal = True
        profile.save(update_fields=["has_seen_welcome_modal"])
        return MarkWelcomeModalSeenMutation(ok=True)


class ResendConfirmationEmailMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.ResendConfirmationEmailSerializer

    @classmethod
    @ratelimit.ratelimit(key="ip", rate="10/min", fail_closed=True)
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


class RequestPasswordSetLinkMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.RequestPasswordSetLinkSerializer

    @classmethod
    @ratelimit.ratelimit(rate="3/hour", key=RateLimitKey.USER, fail_closed=True)
    @audit_failures('auth_password_set_link')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)


@permission_classes(policies.AnyoneFullAccess)
class AnyoneMutation(graphene.ObjectType):
    token_auth = ObtainTokenMutation.Field()
    sign_up = SingUpMutation.Field()
    confirm = ConfirmEmailMutation.Field()
    password_reset = PasswordResetMutation.Field()
    password_reset_confirm = PasswordResetConfirmationMutation.Field()
    validate_otp = ValidateOTPMutation.Field()


@get_graphene_type_from_serializer_field.register(serializers.OrganizationIdField)
def organization_id_graphene_type(field):
    return graphene.ID


class SetDefaultOrganizationMutation(mutations.SerializerMutation):
    class Meta:
        serializer_class = serializers.SetDefaultOrganizationSerializer


@permission_classes(policies.IsAuthenticatedFullAccess)
class AuthenticatedMutation(graphene.ObjectType):
    set_default_organization = SetDefaultOrganizationMutation.Field()
    generate_otp = GenerateOTPMutation.Field()
    verify_otp = VerifyOTPMutation.Field()
    disable_otp = DisableOTPMutation.Field()
    mark_welcome_modal_seen = MarkWelcomeModalSeenMutation.Field()
    resend_confirmation_email = ResendConfirmationEmailMutation.Field()
    request_password_set_link = RequestPasswordSetLinkMutation.Field()


class CurrentUserType(DjangoObjectType):
    default_organization_id = graphene.ID()
    first_name = graphene.String()
    last_name = graphene.String()
    language = graphene.String()
    roles = graphene.List(of_type=graphene.String)
    tenants = graphene.List(of_type=TenantType)
    avatar = graphene.String()
    has_usable_password = graphene.Boolean(
        description="False for an OAuth-only account that has never set a password - "
        "the frontend uses this to show a "
        "'Set password' flow instead of 'Change password' (no old password to ask for)."
    )
    has_seen_welcome_modal = graphene.Boolean(
        description="False until markWelcomeModalSeen is called once for this account - "
        "the frontend uses this instead of client-side storage so the modal is driven "
        "by durable, per-account state rather than a one-shot sessionStorage/cookie flag."
    )

    class Meta:
        model = models.User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "language",
            "roles",
            "avatar",
            "otp_enabled",
            "otp_verified",
            "has_usable_password",
            "has_seen_welcome_modal",
            "is_confirmed",
            "tenants",
            "is_superuser",
        )

    @staticmethod
    def resolve_default_organization_id(parent, info):
        user = get_user_from_resolver(info)
        return default_organization_id(user, info.context)

    @staticmethod
    def resolve_first_name(parent, info):
        return get_user_from_resolver(info).profile.first_name

    @staticmethod
    def resolve_last_name(parent, info):
        return get_user_from_resolver(info).profile.last_name

    @staticmethod
    def resolve_language(parent, info):
        return get_user_from_resolver(info).profile.language

    @staticmethod
    def resolve_roles(parent, info):
        return get_role_names(get_user_from_resolver(info))

    @staticmethod
    def resolve_avatar(parent, info):
        return get_user_avatar_url(get_user_from_resolver(info))

    @staticmethod
    def resolve_has_usable_password(parent, info):
        return get_user_from_resolver(info).has_usable_password()

    @staticmethod
    def resolve_has_seen_welcome_modal(parent, info):
        return get_user_from_resolver(info).profile.has_seen_welcome_modal

    @staticmethod
    def resolve_tenants(parent, info):
        from apps.multitenancy.models import get_visible_tenants_for_user, is_superuser_bypass_eligible

        user = get_user_from_resolver(info)
        if is_superuser_bypass_eligible(user):
            # SUPERUSER BYPASS: owner-equivalent access to every tenant in the system,
            # without a real TenantMembership row - see apps.multitenancy.models.
            tenants = get_visible_tenants_for_user(user)
            return tenants

        tenants = user.tenants.all()
        return tenants


class UserProfileType(DjangoObjectType):
    # Convenience fields that proxy to the user model
    email = graphene.String()
    avatar = graphene.String()
    user_id = graphene.String(description="The hashid of the associated user")

    class Meta:
        model = models.UserProfile
        interfaces = (relay.Node,)
        exclude = ("default_organization",)

    def resolve_email(self, info):
        """Return the user's email."""
        return self.user.email if self.user else None

    def resolve_avatar(self, info):
        """Return the user's avatar URL."""
        if self.avatar and hasattr(self.avatar, "thumbnail"):
            try:
                return self.avatar.thumbnail.url
            except ValueError:
                return None
        return None

    def resolve_user_id(self, info):
        """Return the user's hashid."""
        return str(self.user.id) if self.user else None


class CurrentUserConnection(graphene.Connection):
    class Meta:
        node = UserProfileType


class UpdateCurrentUserMutation(mutations.UpdateModelMutation):
    class Meta:
        serializer_class = serializers.UserProfileSerializer
        edge_class = CurrentUserConnection.Edge
        only_fields = ("first_name", "last_name", "avatar", "language")
        model_operations = ("update",)

    @classmethod
    def get_queryset(cls, model_class: models.User, root, info, **input):
        return get_user_from_resolver(info).profile

    @classmethod
    def get_object(cls, model_class, root, info, **input):
        return get_user_from_resolver(info).profile


class ChangePasswordMutation(CookieAuthenticationMutation):
    class Meta:
        serializer_class = serializers.UserAccountChangePasswordSerializer
        exclude = ("user",)

    @classmethod
    @ratelimit.ratelimit(rate=RateLimitCategory.AUTH_PASSWORD_CHANGE, key=RateLimitKey.USER, fail_closed=True)
    @audit_failures('auth_password_change')
    def mutate_and_get_payload(cls, root, info, **input):
        return super().mutate_and_get_payload(root, info, **input)

    @classmethod
    def perform_mutate(cls, serializer, info):
        # Only perform_mutate (called once is_valid() already succeeded) is atomic, together
        # with session creation - never .validate() itself. See the matching comment on
        # ObtainTokenMutation.perform_mutate: the password failure budget (E05) must commit even
        # when validation ultimately raises (wrong old password), but a successful password
        # change must still roll back together with session creation if that fails.
        with transaction.atomic():
            mutation = super().perform_mutate(serializer, info)
            session_id = _create_session_for_user(info.context.user, info.context._request, mutation.refresh)
            # Keep this session (just minted above) working; properly revoke every other one -
            # same reasoning as PasswordResetConfirmationMutation.perform_mutate.
            SessionService(info.context.user).revoke_all_sessions(except_session_id=session_id)
        info.context._request.set_auth_cookie = {
            settings.SESSION_ID_COOKIE: session_id,
            settings.ACCESS_TOKEN_COOKIE: mutation.access,
            settings.REFRESH_TOKEN_COOKIE: mutation.refresh,
        }

        return mutation


@permission_classes(policies.AnyoneFullAccess)
class Query(graphene.ObjectType):
    current_user = graphene.Field(CurrentUserType)

    @staticmethod
    def resolve_current_user(root, info, **kwargs):
        return info.context.user if info.context.user.is_authenticated else None


class Mutation(graphene.ObjectType):
    change_password = ChangePasswordMutation.Field()
    update_current_user = UpdateCurrentUserMutation.Field()
