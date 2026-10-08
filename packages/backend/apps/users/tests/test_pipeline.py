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


def _google_backend():
    backend = Mock()
    backend.name = "google-oauth2"
    return backend


class TestPopulateProfileFromSocial:
    """Name, avatar, and email-confirmation are backfilled whenever they're
    still blank on a new or already linked social account. These helper tests
    assume the provider identity was resolved by the preceding pipeline steps;
    email collisions are covered in test_social_account_linking.py."""

    def test_confirms_email_and_fills_blank_name_for_existing_account_on_later_login(self, user):
        """An existing provider association resolves this account; no new user
        is created, but blank profile fields should still be backfilled."""
        user.profile.first_name = ""
        user.profile.last_name = ""
        user.profile.save(update_fields=["first_name", "last_name"])
        user.is_confirmed = False
        user.save(update_fields=["is_confirmed"])

        populate_profile_from_social(
            details={"first_name": "Jan", "last_name": "Kowalski", "email": user.email},
            response={"email_verified": True},
            user=user,
            is_new=False,
            backend=_google_backend(),
        )

        user.profile.refresh_from_db()
        user.refresh_from_db()
        assert user.profile.first_name == "Jan"
        assert user.profile.last_name == "Kowalski"
        assert user.is_confirmed is True

    def test_does_not_confirm_email_without_a_verified_matching_provider_email(self, user):
        """Defense-in-depth: this step alone must not confirm an account just
        because it's reachable - create_social_user is expected to already have
        gated that, but this guard should hold even if it didn't."""
        user.is_confirmed = False
        user.save(update_fields=["is_confirmed"])

        populate_profile_from_social(
            details={"email": user.email},
            response={"email_verified": False},
            user=user,
            is_new=False,
            backend=_google_backend(),
        )
        user.refresh_from_db()
        assert user.is_confirmed is False

        populate_profile_from_social(
            details={"email": "someone-else@example.com"},
            response={"email_verified": True},
            user=user,
            is_new=False,
            backend=_google_backend(),
        )
        user.refresh_from_db()
        assert user.is_confirmed is False

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

        populate_profile_from_social(
            details={"email": user.email},
            response={"email_verified": True},
            user=user,
            is_new=True,
            backend=_google_backend(),
        )

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

    @patch("apps.users.pipeline.requests.get")
    def test_downloads_blank_avatar_for_existing_account_on_later_login(self, mock_get, user):
        """An already linked provider login should backfill a blank avatar,
        just as it backfills a blank name."""
        mock_get.return_value = Mock(status_code=200, content=_tiny_jpeg_bytes(), raise_for_status=Mock())
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
        assert user.profile.avatar is not None

    @patch("apps.users.pipeline.requests.get")
    def test_does_not_overwrite_an_existing_avatar_on_later_login(self, mock_get, user_factory):
        mock_get.return_value = Mock(status_code=200, content=_tiny_jpeg_bytes(), raise_for_status=Mock())
        user = user_factory(has_avatar=True)
        existing_avatar = user.profile.avatar

        populate_profile_from_social(
            details={},
            response={"picture": "https://example.com/photo.jpg"},
            user=user,
            is_new=False,
        )

        user.profile.refresh_from_db()
        assert user.profile.avatar_id == existing_avatar.id
        mock_get.assert_not_called()
