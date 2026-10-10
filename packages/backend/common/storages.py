import os
import re
import secrets
from tempfile import SpooledTemporaryFile

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible
from storages.backends.s3boto3 import S3Boto3Storage
from storages.utils import clean_name


@deconstructible
class UniqueFilePathGenerator:
    def __init__(self, path_prefix):
        self.path_prefix = path_prefix

    def __call__(self, _, filename, *args, **kwargs):
        return f"{self.path_prefix}/{secrets.token_hex(8)}/{filename}"


def organization_document_prefix(organization_id):
    organization_id = str(organization_id)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', organization_id):
        raise ValueError('Invalid organization storage identifier')
    return f'documents/organizations/{organization_id}/'


@deconstructible
class OrganizationDocumentPathGenerator:
    def __call__(self, instance, filename):
        if instance.tenant_id is None:
            # Unassigned legacy documents have no organization to clean up.
            return UniqueFilePathGenerator('documents')(instance, filename)
        # Normalize raw integer FK assignments to the same hashid used by deletion.
        organization_id = instance._meta.get_field('tenant').target_field.to_python(instance.tenant_id)
        return f'{organization_document_prefix(organization_id)}{secrets.token_hex(8)}/{filename}'


@deconstructible
class UserAvatarPathGenerator:
    def __init__(self, kind):
        self.kind = kind

    def __call__(self, instance, filename):
        if not instance.account_id:
            return UniqueFilePathGenerator(f'avatars/{self.kind}')(instance, filename)
        if not re.fullmatch(r'[A-Za-z0-9_-]+', instance.account_id):
            raise ValueError('Invalid avatar owner')
        return f'avatars/users/{instance.account_id}/{self.kind}/{secrets.token_hex(8)}/{filename}'


def delete_storage_file(storage, path):
    """Permanently remove a recorded file, including historical S3 versions."""
    if isinstance(storage, S3Boto3Storage) and _has_storage_versions(storage):
        # Match Django's normal key normalization for existing recorded paths.
        key = storage._normalize_name(clean_name(path))
        _delete_storage_versions(storage, key, exact=True)
    else:
        storage.delete(path)


def _has_storage_versions(storage):
    response = storage.connection.meta.client.get_bucket_versioning(Bucket=storage.bucket_name)
    # Suspended buckets can still contain versions from when versioning was enabled.
    return response.get('Status') in ('Enabled', 'Suspended')


def _delete_storage_versions(storage, prefix, *, exact=False, progress=None):
    client = storage.connection.meta.client
    pages = client.get_paginator('list_object_versions').paginate(
        Bucket=storage.bucket_name, Prefix=prefix, PaginationConfig={'PageSize': 1000}
    )
    for page in pages:
        if progress is not None:
            progress()
        for collection in ('Versions', 'DeleteMarkers'):
            for index, item in enumerate(page.get(collection, [])):
                key = item['Key']
                if not key.startswith(prefix):
                    raise ValueError('Storage listing returned a version outside the cleanup prefix')
                if exact and key != prefix:
                    continue
                if progress is not None and index % 100 == 0:
                    progress()
                client.delete_object(Bucket=storage.bucket_name, Key=key, VersionId=item['VersionId'])


def delete_storage_prefix(storage, prefix, *, progress=None):
    """Delete objects and versions under an exact directory prefix, including unrecorded files.

    S3-compatible storage is streamed through ListObjectsV2 pagination. The caller
    may renew its durable cleanup lease while a large scan is in progress.
    """
    if (
        not prefix
        or not prefix.endswith('/')
        or prefix.startswith('/')
        or any(part in ('', '.', '..') for part in prefix[:-1].split('/'))
    ):
        raise ValueError('Cleanup requires an exact, nonempty directory prefix')

    def heartbeat():
        if progress is not None:
            progress()

    if isinstance(storage, S3Boto3Storage):
        location = storage.location.strip('/')
        full_prefix = f'{location}/{prefix}' if location else prefix
        if _has_storage_versions(storage):
            _delete_storage_versions(storage, full_prefix, progress=progress)
            return
        client = storage.connection.meta.client
        pages = client.get_paginator('list_objects_v2').paginate(
            Bucket=storage.bucket_name, Prefix=full_prefix, PaginationConfig={'PageSize': 1000}
        )
        for page in pages:
            heartbeat()
            for index, item in enumerate(page.get('Contents', [])):
                key = item['Key']
                if not key.startswith(full_prefix):
                    raise ValueError('Storage listing returned an object outside the cleanup prefix')
                if index % 100 == 0:
                    heartbeat()
                # Use the exact listed key. Django's path normalization could change
                # unusual object names containing ../ and delete a different object.
                client.delete_object(Bucket=storage.bucket_name, Key=key)
        return

    if isinstance(storage, FileSystemStorage):
        root = storage.path(prefix)
        ancestor = root
        while ancestor != storage.location:
            if os.path.islink(ancestor):
                raise ValueError('Cleanup cannot follow a symlinked organization directory')
            ancestor = os.path.dirname(ancestor)
            if ancestor == os.path.dirname(ancestor):
                raise ValueError('Cleanup directory escaped the storage root')

        def raise_listing_error(error):
            if not isinstance(error, FileNotFoundError):
                raise error

        count = 0
        for directory, _, filenames in os.walk(root, followlinks=False, onerror=raise_listing_error):
            heartbeat()
            for filename in filenames:
                if count % 100 == 0:
                    heartbeat()
                relative_path = os.path.relpath(os.path.join(directory, filename), root).replace(os.sep, '/')
                storage.delete(f'{prefix}{relative_path}')
                count += 1
        return

    raise NotImplementedError('Prefix cleanup is unsupported by this storage backend')


class CustomS3Boto3Storage(S3Boto3Storage):
    """AWS S3 storage backend (default behavior)"""

    # Overwritten to avoid "I/O operation on closed file" error when creating thumbnails
    # https://github.com/matthewwithanm/django-imagekit/issues/391#issuecomment-592877289
    def _save(self, name, content):
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


class PublicS3Boto3StorageWithCDN(CustomS3Boto3Storage):
    querystring_auth = False
    location = "public"


@deconstructible
class PublicCloudflareR2Storage(S3Boto3Storage):
    """
    Public Cloudflare R2 storage backend for user-facing assets like avatars.
    Uses querystring_auth=False for public URLs.
    Enforces SigV4 signature which is required by Cloudflare R2.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("endpoint_url", getattr(settings, "R2_ENDPOINT_URL", None))
        kwargs.setdefault("access_key", getattr(settings, "R2_ACCESS_KEY_ID", None))
        kwargs.setdefault("secret_key", getattr(settings, "R2_SECRET_ACCESS_KEY", None))
        kwargs.setdefault("bucket_name", getattr(settings, "R2_BUCKET_NAME", None))
        kwargs.setdefault("default_acl", None)
        kwargs.setdefault("querystring_auth", False)  # Public access
        kwargs.setdefault("location", "public")
        # R2 requires SigV4 - SigV2 is not supported
        kwargs.setdefault("signature_version", "s3v4")

        custom_domain = getattr(settings, "R2_CUSTOM_DOMAIN", None)
        if custom_domain:
            kwargs.setdefault("custom_domain", custom_domain)

        super().__init__(**kwargs)

    def _save(self, name, content):
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


@deconstructible
class CloudflareR2Storage(S3Boto3Storage):
    """
    Cloudflare R2 storage backend - S3-compatible object storage.
    Used for private files that require signed URLs.
    Enforces SigV4 signature which is required by Cloudflare R2.

    Configure with environment variables:
    - R2_ENDPOINT_URL: https://<account-id>.r2.cloudflarestorage.com
    - R2_ACCESS_KEY_ID: Your R2 access key
    - R2_SECRET_ACCESS_KEY: Your R2 secret key
    - R2_BUCKET_NAME: Your bucket name
    - R2_CUSTOM_DOMAIN: (optional) Custom domain for public access
    """

    def __init__(self, **kwargs):
        # R2 uses S3-compatible API but needs explicit endpoint
        kwargs.setdefault("endpoint_url", getattr(settings, "R2_ENDPOINT_URL", None))
        kwargs.setdefault("access_key", getattr(settings, "R2_ACCESS_KEY_ID", None))
        kwargs.setdefault("secret_key", getattr(settings, "R2_SECRET_ACCESS_KEY", None))
        kwargs.setdefault("bucket_name", getattr(settings, "R2_BUCKET_NAME", None))

        # R2 doesn't support some S3 features
        kwargs.setdefault("default_acl", None)
        kwargs.setdefault("querystring_auth", True)
        # R2 requires SigV4 - SigV2 is not supported
        kwargs.setdefault("signature_version", "s3v4")

        # Use custom domain if provided (for public bucket access)
        custom_domain = getattr(settings, "R2_CUSTOM_DOMAIN", None)
        if custom_domain:
            kwargs.setdefault("custom_domain", custom_domain)

        super().__init__(**kwargs)

    def _save(self, name, content):
        # Same fix as CustomS3Boto3Storage for thumbnail issues
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


@deconstructible
class BackblazeB2Storage(S3Boto3Storage):
    """
    Backblaze B2 storage backend - S3-compatible object storage.

    Configure with environment variables:
    - B2_ENDPOINT_URL: https://s3.<region>.backblazeb2.com
    - B2_ACCESS_KEY_ID: Your B2 application key ID
    - B2_SECRET_ACCESS_KEY: Your B2 application key
    - B2_BUCKET_NAME: Your bucket name
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("endpoint_url", getattr(settings, "B2_ENDPOINT_URL", None))
        kwargs.setdefault("access_key", getattr(settings, "B2_ACCESS_KEY_ID", None))
        kwargs.setdefault("secret_key", getattr(settings, "B2_SECRET_ACCESS_KEY", None))
        kwargs.setdefault("bucket_name", getattr(settings, "B2_BUCKET_NAME", None))
        kwargs.setdefault("default_acl", None)

        super().__init__(**kwargs)

    def _save(self, name, content):
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


@deconstructible
class MinIOStorage(S3Boto3Storage):
    """
    MinIO storage backend - self-hosted S3-compatible object storage.

    Configure with environment variables:
    - MINIO_ENDPOINT_URL: http://minio:9000 (or your MinIO endpoint)
    - MINIO_ACCESS_KEY_ID: Your MinIO access key
    - MINIO_SECRET_ACCESS_KEY: Your MinIO secret key
    - MINIO_BUCKET_NAME: Your bucket name
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("endpoint_url", getattr(settings, "MINIO_ENDPOINT_URL", None))
        kwargs.setdefault("access_key", getattr(settings, "MINIO_ACCESS_KEY_ID", None))
        kwargs.setdefault("secret_key", getattr(settings, "MINIO_SECRET_ACCESS_KEY", None))
        kwargs.setdefault("bucket_name", getattr(settings, "MINIO_BUCKET_NAME", None))
        kwargs.setdefault("default_acl", None)

        super().__init__(**kwargs)

    def _save(self, name, content):
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


@deconstructible
class LocalMediaStorage(FileSystemStorage):
    """
    Local filesystem storage for development and VPS deployments.

    Configure with environment variables:
    - MEDIA_ROOT: /path/to/media (default: BASE_DIR/media)
    - MEDIA_URL: /media/ (default)
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("location", getattr(settings, "MEDIA_ROOT", None))
        kwargs.setdefault("base_url", getattr(settings, "MEDIA_URL", "/media/"))
        super().__init__(**kwargs)


@deconstructible
class PublicBackblazeB2Storage(S3Boto3Storage):
    """Public Backblaze B2 storage for user-facing assets."""

    def __init__(self, **kwargs):
        kwargs.setdefault("endpoint_url", getattr(settings, "B2_ENDPOINT_URL", None))
        kwargs.setdefault("access_key", getattr(settings, "B2_ACCESS_KEY_ID", None))
        kwargs.setdefault("secret_key", getattr(settings, "B2_SECRET_ACCESS_KEY", None))
        kwargs.setdefault("bucket_name", getattr(settings, "B2_BUCKET_NAME", None))
        kwargs.setdefault("default_acl", None)
        kwargs.setdefault("querystring_auth", False)
        kwargs.setdefault("location", "public")
        super().__init__(**kwargs)

    def _save(self, name, content):
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


@deconstructible
class PublicMinIOStorage(S3Boto3Storage):
    """Public MinIO storage for user-facing assets."""

    def __init__(self, **kwargs):
        kwargs.setdefault("endpoint_url", getattr(settings, "MINIO_ENDPOINT_URL", None))
        kwargs.setdefault("access_key", getattr(settings, "MINIO_ACCESS_KEY_ID", None))
        kwargs.setdefault("secret_key", getattr(settings, "MINIO_SECRET_ACCESS_KEY", None))
        kwargs.setdefault("bucket_name", getattr(settings, "MINIO_BUCKET_NAME", None))
        kwargs.setdefault("default_acl", None)
        kwargs.setdefault("querystring_auth", False)
        kwargs.setdefault("location", "public")
        super().__init__(**kwargs)

    def _save(self, name, content):
        content.seek(0, os.SEEK_SET)
        with SpooledTemporaryFile() as content_autoclose:
            content_autoclose.write(content.read())
            return super()._save(name, content_autoclose)


# Storage backend registry
STORAGE_BACKENDS = {
    "s3": "common.storages.CustomS3Boto3Storage",
    "r2": "common.storages.CloudflareR2Storage",
    "b2": "common.storages.BackblazeB2Storage",
    "minio": "common.storages.MinIOStorage",
    "local": "common.storages.LocalMediaStorage",
}


def get_default_storage_backend():
    """
    Factory function to get storage backend class path based on STORAGE_BACKEND env var.

    Supported backends:
    - s3: AWS S3 (default)
    - r2: Cloudflare R2
    - b2: Backblaze B2
    - minio: Self-hosted MinIO
    - local: Local filesystem

    Usage in settings.py:
        STORAGES = {
            "default": {"BACKEND": get_default_storage_backend()},
            ...
        }
    """
    backend = os.environ.get("STORAGE_BACKEND", "s3")
    return STORAGE_BACKENDS.get(backend, STORAGE_BACKENDS["s3"])


# Public storage backend registry (for user-facing assets like avatars)
PUBLIC_STORAGE_BACKENDS = {
    "s3": PublicS3Boto3StorageWithCDN,
    "r2": PublicCloudflareR2Storage,
    "b2": PublicBackblazeB2Storage,
    "minio": PublicMinIOStorage,
    "local": LocalMediaStorage,
}


def get_public_storage():
    """
    Get the public storage backend instance based on STORAGE_BACKEND env var.

    Used for user-facing assets like avatars that need public URLs.

    Usage in models:
        avatar = models.ImageField(storage=get_public_storage, ...)

    Note: Pass the function itself (not called) to ImageField for lazy evaluation.
    """
    backend = os.environ.get("STORAGE_BACKEND", "s3")
    storage_class = PUBLIC_STORAGE_BACKENDS.get(backend, PUBLIC_STORAGE_BACKENDS["s3"])
    return storage_class()


def get_translations_storage():
    """
    Get the storage backend instance for translations.

    Uses the same backend as public storage but with 'translations' location prefix.
    This ensures translations are stored in the same bucket as other public assets.

    Supported backends (based on STORAGE_BACKEND env var):
    - s3: AWS S3
    - r2: Cloudflare R2
    - b2: Backblaze B2
    - minio: Self-hosted MinIO
    - local: Local filesystem

    Returns:
        Storage instance configured for translations
    """
    backend = os.environ.get("STORAGE_BACKEND", "s3")

    if backend == "local":
        return LocalMediaStorage(location=os.path.join(getattr(settings, "MEDIA_ROOT", ""), "translations"))

    # For cloud backends, use the public storage class with translations location
    storage_classes = {
        "s3": PublicS3Boto3StorageWithCDN,
        "r2": PublicCloudflareR2Storage,
        "b2": PublicBackblazeB2Storage,
        "minio": PublicMinIOStorage,
    }

    storage_class = storage_classes.get(backend, PublicS3Boto3StorageWithCDN)
    return storage_class(location="translations")


# Private storage backend registry (for files requiring signed URLs like exports)
PRIVATE_STORAGE_BACKENDS = {
    "s3": CustomS3Boto3Storage,
    "r2": CloudflareR2Storage,
    "b2": BackblazeB2Storage,
    "minio": MinIOStorage,
    "local": LocalMediaStorage,
}


def get_exports_storage():
    """
    Get the storage backend instance for private exports (action logs, reports, etc.).

    Uses signed URLs for secure downloads. For R2, this enforces SigV4.

    Supported backends (based on STORAGE_BACKEND env var):
    - s3: AWS S3
    - r2: Cloudflare R2 (uses SigV4)
    - b2: Backblaze B2
    - minio: Self-hosted MinIO
    - local: Local filesystem

    Returns:
        Storage instance configured for exports with 'exports' location prefix
    """
    backend = os.environ.get("STORAGE_BACKEND", "s3")

    if backend == "local":
        return LocalMediaStorage(location=os.path.join(getattr(settings, "MEDIA_ROOT", ""), "exports"))

    # For cloud backends, use the private storage class with exports location
    storage_class = PRIVATE_STORAGE_BACKENDS.get(backend, CustomS3Boto3Storage)
    return storage_class(location="exports")


def get_user_exports_storage():
    """Personal exports historically use a separate bucket on the AWS storage path."""
    if os.environ.get('STORAGE_BACKEND', 's3') == 's3':
        return CustomS3Boto3Storage(
            bucket_name=settings.AWS_EXPORTS_STORAGE_BUCKET_NAME,
            location='',
            custom_domain=None,
            querystring_auth=True,
            default_acl=None,
            querystring_expire=settings.USER_DATA_EXPORT_EXPIRY_SECONDS,
        )
    return get_exports_storage()


def delete_user_exports(account_id, *, legacy=False):
    account_id = str(account_id)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', account_id):
        raise ValueError('Invalid account identifier')
    storage = get_user_exports_storage()
    if not legacy:
        delete_storage_prefix(storage, f'users/{account_id}/')
        return
    # The underscore delimiter is part of the old filename format. Never scan by ID alone.
    prefix = f'exports/{account_id}_'
    if isinstance(storage, S3Boto3Storage):
        key_prefix = storage._normalize_name(prefix)
        if _has_storage_versions(storage):
            _delete_storage_versions(storage, key_prefix)
        else:
            client = storage.connection.meta.client
            for page in client.get_paginator('list_objects_v2').paginate(Bucket=storage.bucket_name, Prefix=key_prefix):
                for item in page.get('Contents', []):
                    if not item['Key'].startswith(key_prefix):
                        raise ValueError('Export listing escaped account prefix')
                    client.delete_object(Bucket=storage.bucket_name, Key=item['Key'])
    elif storage.exists('exports'):
        _, files = storage.listdir('exports')
        for name in files:
            if name.startswith(f'{account_id}_'):
                delete_storage_file(storage, f'exports/{name}')
