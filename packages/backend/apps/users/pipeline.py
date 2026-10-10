import logging

import requests
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from social_core.exceptions import AuthForbidden

from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog

from .models import User, UserAvatar
from .services.social_linking import begin_link

logger = logging.getLogger(__name__)

AVATAR_DOWNLOAD_TIMEOUT_SECONDS = 5


def _deny_social_account_creation(backend, reason):
    SSOAuditLog.log_event(
        SSOAuditEventType.SSO_LOGIN_FAILED,
        description="Social login account creation denied",
        metadata={"provider": backend.name, "reason": reason},
        success=False,
    )
    raise AuthForbidden(backend)


def _provider_email_verified(backend, response):
    """Only trust a provider's email as proof of ownership when it explicitly says so.

    Google's userinfo response includes a boolean `email_verified` claim. Facebook
    Login is configured (SOCIAL_AUTH_FACEBOOK_*) but not yet enabled in
    AUTHENTICATION_BACKENDS - when it is, add its own verified-email signal here
    rather than defaulting new providers to trusted.
    """
    if backend.name == "google-oauth2":
        return response.get("email_verified") is True
    return False


def create_social_user(backend, details, response=None, user=None, social=None, uid=None, *args, **kwargs):
    """Resolve accounts by provider identity, never by an implicitly matching email.

    Bypass social-django's legacy get-or-create fallback: a concurrent password
    signup must cause a collision, not silently become the social user's account.
    Explicit account linking requires a separate fresh-authentication flow.
    """
    if user is not None:
        if social is None or social.user_id != user.pk:
            _deny_social_account_creation(backend, "unverified_account_link")
        return {"is_new": False, "user": user}

    if not _provider_email_verified(backend, response or {}):
        _deny_social_account_creation(backend, "unverified_provider_email")

    email = details.get("email")
    if not email:
        _deny_social_account_creation(backend, "missing_provider_email")
    existing = User.objects.filter(email__iexact=email).first()
    if existing is not None:
        return begin_link(backend, existing, uid)

    try:
        with transaction.atomic():
            account = User.objects.create_user(email=email, password=None)
    except IntegrityError:
        # Do not reveal the account's identity or fall back to it on a collision.
        _deny_social_account_creation(backend, "email_collision")

    return {"is_new": True, "user": account}


@transaction.atomic
def populate_profile_from_social(
    details, response, user=None, is_new=False, backend=None, social=None, *args, **kwargs
):
    """Fill in name/avatar from the social provider's profile data, and mark the
    account's email as confirmed - but only when the provider actually verified
    the email that matches this account, rather than trusting that reaching this
    step is proof enough by itself. New accounts and previously associated
    identities may reach this helper. An email match without a resolved provider
    identity instead goes through begin_link; it cannot establish ownership here.
    Name and avatar are filled unconditionally on first signup
    (is_new - fields are blank there by definition), and additionally
    backfilled on a later login only when currently blank (both first *and*
    last name; no avatar set) - never overwrites a name/avatar the user has
    already set or deliberately cleared."""
    if not user:
        return
    user = User.objects.select_for_update().get(pk=user.pk)

    provider_email = (details.get("email") or response.get("email") or "").lower()
    email_confirmed_by_provider = (
        backend is not None
        and provider_email
        and provider_email == user.email.lower()
        and _provider_email_verified(backend, response)
    )

    if not user.is_confirmed and email_confirmed_by_provider:
        user.is_confirmed = True
        user.save(update_fields=["is_confirmed"])

    if is_new and email_confirmed_by_provider and social is not None and social.user_id == user.pk:
        SSOAuditLog.log_event(
            SSOAuditEventType.SSO_LOGIN_SUCCESS,
            user=user,
            description='Social signup completed with a verified provider identity',
            metadata={
                'provider': backend.name,
                'action': 'account_linked',
                'association_id': str(social.pk),
                'method': 'verified_provider_signup',
            },
        )

    profile = user.profile
    changed_fields = []

    if is_new or (not profile.first_name and not profile.last_name):
        first_name = details.get("first_name") or ""
        last_name = details.get("last_name") or ""
        if first_name or last_name:
            profile.first_name = first_name
            profile.last_name = last_name
            changed_fields += ["first_name", "last_name"]

    if is_new or not profile.avatar:
        picture_url = _get_picture_url(response)
        if picture_url:
            avatar = _download_avatar(picture_url, account_id=str(user.pk))
            if avatar:
                profile.avatar = avatar
                changed_fields.append("avatar")

    if changed_fields:
        profile.save(update_fields=changed_fields)


def _get_picture_url(response):
    picture = response.get("picture")
    if isinstance(picture, dict):
        # Facebook: {"data": {"url": "..."}}
        return picture.get("data", {}).get("url")
    if isinstance(picture, str):
        # Google: plain URL string
        return picture
    return None


def _download_avatar(url, account_id=''):
    try:
        image_response = requests.get(url, timeout=AVATAR_DOWNLOAD_TIMEOUT_SECONDS)
        image_response.raise_for_status()
    except requests.RequestException:
        logger.warning("Failed to download social login avatar from %s", url)
        return None

    file_name = url.split("/")[-1].split("?")[0] or "avatar"
    if "." not in file_name:
        file_name += ".jpg"

    avatar = UserAvatar(account_id=account_id)
    avatar.original.save(file_name, ContentFile(image_response.content), save=False)
    try:
        # Also generates the thumbnail (ImageWithThumbnailMixin.save()) - raises
        # GraphQlValidationError on an unsupported/unrecognized image format, which
        # must not be allowed to break login just because the avatar didn't work.
        avatar.save()
    except Exception:
        logger.warning("Failed to save social login avatar downloaded from %s", url)
        return None
    return avatar
