from io import BytesIO
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from apps.users.pipeline import populate_profile_from_social

pytestmark = pytest.mark.django_db


def _tiny_jpeg_bytes():
    buffer = BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, "JPEG")
    return buffer.getvalue()


class TestPopulateProfileFromSocial:
    """Name and email-confirmation are backfilled whenever they're still blank -
    on the account's first signup, or when an existing password-signup account
    is later linked (by email) to a Google/Facebook login - but never overwrite
    a name the user has already set. Avatar remains first-signup-only (is_new):
    unlike name/confirmation, silently re-downloading it on every later login
    could clobber one the user set themselves."""

    def test_confirms_email_and_fills_blank_name_for_existing_account_on_later_login(self, user):
        """E.g. signed up with email+password, later uses "Sign in with Google"
        with the same address - is_new is False (no new user is created, just
        linked by email), but the fields should still be backfilled."""
        user.profile.first_name = ""
        user.profile.last_name = ""
        user.profile.save(update_fields=["first_name", "last_name"])
        user.is_confirmed = False
        user.save(update_fields=["is_confirmed"])

        populate_profile_from_social(
            details={"first_name": "Jan", "last_name": "Kowalski"}, response={}, user=user, is_new=False
        )

        user.profile.refresh_from_db()
        user.refresh_from_db()
        assert user.profile.first_name == "Jan"
        assert user.profile.last_name == "Kowalski"
        assert user.is_confirmed is True

    def test_does_not_overwrite_an_existing_name_on_later_login(self, user):
        user.profile.first_name = "Existing"
        user.profile.last_name = ""
        user.profile.save(update_fields=["first_name", "last_name"])

        populate_profile_from_social(
            details={"first_name": "Jan", "last_name": "Kowalski"}, response={}, user=user, is_new=False
        )

        user.profile.refresh_from_db()
        assert user.profile.first_name == "Existing"
        assert user.profile.last_name == ""

    def test_confirms_email_on_first_social_signup(self, user):
        user.is_confirmed = False
        user.save(update_fields=["is_confirmed"])

        populate_profile_from_social(details={}, response={}, user=user, is_new=True)

        user.refresh_from_db()
        assert user.is_confirmed is True

    def test_does_nothing_without_a_user(self):
        # Should not raise even though there's nothing to fill.
        populate_profile_from_social(details={"first_name": "Jan"}, response={}, user=None, is_new=True)

    def test_fills_name_on_first_signup(self, user):
        user.profile.first_name = ""
        user.profile.last_name = ""
        user.profile.save(update_fields=["first_name", "last_name"])

        populate_profile_from_social(
            details={"first_name": "Jan", "last_name": "Kowalski"}, response={}, user=user, is_new=True
        )

        user.profile.refresh_from_db()
        assert user.profile.first_name == "Jan"
        assert user.profile.last_name == "Kowalski"

    @patch("apps.users.pipeline.requests.get")
    def test_downloads_google_style_avatar(self, mock_get, user):
        mock_get.return_value = Mock(status_code=200, content=_tiny_jpeg_bytes(), raise_for_status=Mock())

        populate_profile_from_social(
            details={}, response={"picture": "https://lh3.googleusercontent.com/a/photo.jpg"}, user=user, is_new=True
        )

        user.profile.refresh_from_db()
        assert user.profile.avatar is not None
        assert user.profile.avatar.original

    @patch("apps.users.pipeline.requests.get")
    def test_downloads_facebook_style_avatar(self, mock_get, user):
        mock_get.return_value = Mock(status_code=200, content=_tiny_jpeg_bytes(), raise_for_status=Mock())

        populate_profile_from_social(
            details={},
            response={"picture": {"data": {"url": "https://platform-lookaside.fbsbx.com/photo.jpg"}}},
            user=user,
            is_new=True,
        )

        user.profile.refresh_from_db()
        assert user.profile.avatar is not None

    @patch("apps.users.pipeline.requests.get")
    def test_avatar_download_failure_does_not_break_login(self, mock_get, user):
        mock_get.side_effect = requests.RequestException("boom")

        populate_profile_from_social(
            details={"first_name": "Jan"}, response={"picture": "https://example.com/photo.jpg"}, user=user, is_new=True
        )

        user.profile.refresh_from_db()
        assert user.profile.avatar is None
        assert user.profile.first_name == "Jan"

    def test_does_not_redownload_avatar_after_user_clears_it_on_a_later_login(self, user):
        """Avatar keeps the old guarantee: is_new gates it, not "is it currently
        blank" - otherwise deleting a synced avatar would just bring it back on
        the next Google/Facebook login. (Name has no such guarantee - see
        test_confirms_email_and_fills_blank_name_for_existing_account_on_later_login
        above - only avatar is signup-gated.)"""
        user.profile.first_name = "Existing"
        user.profile.last_name = "Name"
        user.profile.avatar = None
        user.profile.save(update_fields=["first_name", "last_name", "avatar"])

        populate_profile_from_social(
            details={"first_name": "Jan"},
            response={"picture": "https://example.com/photo.jpg"},
            user=user,
            is_new=False,
        )

        user.profile.refresh_from_db()
        assert user.profile.avatar is None
