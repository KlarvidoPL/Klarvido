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
    """Regression coverage for a one-time-only fill: name/avatar should be copied
    from the social provider on the account's first signup, but never re-applied
    on a later login - even if the user has since cleared those fields."""

    def test_does_nothing_when_not_a_new_user(self, user):
        user.profile.first_name = ""
        user.profile.save(update_fields=["first_name"])

        populate_profile_from_social(
            details={"first_name": "Jan", "last_name": "Kowalski"}, response={}, user=user, is_new=False
        )

        user.profile.refresh_from_db()
        assert user.profile.first_name == ""

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

    def test_does_not_refill_after_user_clears_fields_on_a_later_login(self, user):
        """The core guarantee: is_new gates this, not "is the field currently
        blank" - otherwise deleting a synced name/avatar would just bring it back
        on the next Google/Facebook login."""
        user.profile.first_name = ""
        user.profile.avatar = None
        user.profile.save(update_fields=["first_name", "avatar"])

        populate_profile_from_social(
            details={"first_name": "Jan"},
            response={"picture": "https://example.com/photo.jpg"},
            user=user,
            is_new=False,
        )

        user.profile.refresh_from_db()
        assert user.profile.first_name == ""
        assert user.profile.avatar is None
