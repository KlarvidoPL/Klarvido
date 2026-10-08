import hashid_field
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group
from django.contrib.auth.models import BaseUserManager
from django.db import models
from django.utils import timezone

from common.acl.helpers import CommonGroups
from common.models import ImageWithThumbnailMixin
from common.storages import UniqueFilePathGenerator, get_public_storage
from apps.multitenancy.models import TenantMembership


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, language=None):
        if not email:
            raise ValueError("Users must have an email address")

        normalized_email = self.normalize_email(email)
        user = self.model(
            email=normalized_email,
        )
        user.set_password(password)
        user_group = Group.objects.get(name=CommonGroups.User)
        user.save(using=self._db)

        user.groups.add(user_group)

        UserProfile.objects.create(user=user, language=language or LanguageChoices.ENGLISH)

        TenantMembership.objects.associate_invitations_with_user(normalized_email, user)

        return user

    def create_superuser(self, email, password):
        user = self.create_user(
            email,
            password=password,
        )
        user.is_superuser = True
        user.save(using=self._db)

        return user

    def filter_admins(self):
        return self.filter(groups__name=CommonGroups.Admin)


class User(AbstractBaseUser, PermissionsMixin):
    id = hashid_field.HashidAutoField(primary_key=True)
    created = models.DateTimeField(editable=False, auto_now_add=True)
    email = models.EmailField(
        db_collation="case_insensitive",
        verbose_name="email address",
        max_length=255,
        unique=True,
    )
    is_confirmed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)

    otp_enabled = models.BooleanField(default=False)
    otp_verified = models.BooleanField(default=False)
    otp_base32 = models.CharField(max_length=255, blank=True, default="")
    otp_auth_url = models.CharField(max_length=255, blank=True, default="")
    # Holds a newly generated secret during setup/replacement, kept out of otp_base32
    # (the active secret used for login) until the user proves they can produce a code
    # from it - a failed or abandoned setup must never affect the currently active factor.
    otp_pending_base32 = models.CharField(max_length=255, blank=True, default="")
    otp_pending_auth_url = models.CharField(max_length=255, blank=True, default="")
    otp_failed_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    otp_locked_until = models.DateTimeField(null=True, blank=True, editable=False)
    # Hash of the most recently accepted login TOTP code. Submitting that exact code
    # again (e.g. a captured request/cookie replayed) is rejected even though it is
    # still within its validity window - each valid code is only ever usable once.
    otp_last_used_code_hash = models.CharField(max_length=64, blank=True, default="", editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"

    def __str__(self) -> str:
        return self.email

    @property
    def is_staff(self):
        return self.is_superuser

    def has_group(self, name):
        return self.groups.filter(name=name).exists()


class PendingSocialAccountLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    provider = models.CharField(max_length=64)
    uid = models.CharField(max_length=255)
    credential_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.provider} linking confirmation ({self.pk})'


class PendingOTPLogin(models.Model):
    """Server-side, one-use proof of "password/SSO succeeded, now enter your 2FA code".

    Replaces a self-contained signed JWT (which any holder of a valid access/refresh
    token could otherwise have satisfied) with a DB row that only begin_otp_login()
    can create, that only matches the account/credentials active when it was issued,
    and that is marked used atomically with session issuance so it cannot be replayed.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64, unique=True)
    auth_method = models.CharField(max_length=20)
    credential_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Pending OTP login ({self.pk})'


class SocialAccountUnlinkChallenge(models.Model):
    association = models.ForeignKey('social_django.UserSocialAuth', on_delete=models.CASCADE)
    challenge = models.OneToOneField('sso.WebAuthnChallenge', on_delete=models.CASCADE)
    credential_version = models.CharField(max_length=64)

    def __str__(self):
        return f'Social unlink challenge ({self.pk})'


class UserAvatar(ImageWithThumbnailMixin, models.Model):
    original = models.ImageField(storage=get_public_storage(), upload_to=UniqueFilePathGenerator("avatars"), null=True)
    thumbnail = models.ImageField(
        storage=get_public_storage(), upload_to=UniqueFilePathGenerator("avatars/thumbnails"), null=True
    )

    THUMBNAIL_SIZE = (128, 128)
    ERROR_FIELD_NAME = "avatar"

    def __str__(self) -> str:
        return str(self.id)


class LanguageChoices(models.TextChoices):
    ENGLISH = "en", "English"
    POLISH = "pl", "Polish"
    GERMAN = "de", "German"
    FRENCH = "fr", "French"
    SPANISH = "es", "Spanish"
    CHINESE = "zh", "Chinese"
    HINDI = "hi", "Hindi"
    ARABIC = "ar", "Arabic"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    first_name = models.CharField(max_length=40, blank=True, default="")
    last_name = models.CharField(max_length=40, blank=True, default="")
    language = models.CharField(
        max_length=5,
        choices=LanguageChoices.choices,
        default=LanguageChoices.ENGLISH,
        help_text="User's preferred language for emails and notifications",
    )
    avatar = models.OneToOneField(
        UserAvatar, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_profile"
    )
    has_seen_welcome_modal = models.BooleanField(default=False)
    default_organization = models.ForeignKey(
        'multitenancy.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='default_for_profiles'
    )

    def __str__(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.user.email


class SecurityEmailOutbox(models.Model):
    """No credential values: activation tokens are generated only when delivering."""

    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    event_id = models.CharField(max_length=64, unique=True)
    recipient = models.EmailField()
    kind = models.CharField(max_length=40)
    language = models.CharField(max_length=8, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=40, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['next_attempt_at'],
                name='users_security_email_due_idx',
                condition=models.Q(sent_at__isnull=True, failed_at__isnull=True, cancelled_at__isnull=True),
            )
        ]


class SignupEmailCooldown(models.Model):
    recipient_hash = models.CharField(max_length=64, primary_key=True)
    last_sent_at = models.DateTimeField(null=True)
    day_started_at = models.DateTimeField(default=timezone.now)
    daily_count = models.PositiveSmallIntegerField(default=0)
