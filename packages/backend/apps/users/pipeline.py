import logging

import requests
from django.core.files.base import ContentFile

from .models import UserAvatar

logger = logging.getLogger(__name__)

AVATAR_DOWNLOAD_TIMEOUT_SECONDS = 5


def populate_profile_from_social(details, response, user=None, is_new=False, *args, **kwargs):
    """Fill in name/avatar from the social provider's profile data, and mark the
    account's email as confirmed - Google/Facebook already verified it, so
    there's nothing left to confirm, whether this is a brand new signup or a
    Google login later linked (by email) to an existing password-signup
    account. Name is filled unconditionally on first signup (is_new - fields
    are blank there by definition), and additionally backfilled on a later
    login only when currently blank (both first *and* last name) - never
    overwrites a name the user has already set or deliberately cleared. Avatar
    stays first-signup-only (is_new) - unlike name/confirmation, silently
    re-downloading it on every later login could clobber one the user set
    themselves."""
    if not user:
        return

    if not user.is_confirmed:
        user.is_confirmed = True
        user.save(update_fields=["is_confirmed"])

    profile = user.profile
    changed_fields = []

    if is_new or (not profile.first_name and not profile.last_name):
        first_name = details.get("first_name") or ""
        last_name = details.get("last_name") or ""
        if first_name or last_name:
            profile.first_name = first_name
            profile.last_name = last_name
            changed_fields += ["first_name", "last_name"]

    if is_new:
        picture_url = _get_picture_url(response)
        if picture_url:
            avatar = _download_avatar(picture_url)
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


def _download_avatar(url):
    try:
        image_response = requests.get(url, timeout=AVATAR_DOWNLOAD_TIMEOUT_SECONDS)
        image_response.raise_for_status()
    except requests.RequestException:
        logger.warning("Failed to download social login avatar from %s", url)
        return None

    file_name = url.split("/")[-1].split("?")[0] or "avatar"
    if "." not in file_name:
        file_name += ".jpg"

    avatar = UserAvatar()
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
