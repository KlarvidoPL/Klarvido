from unittest.mock import Mock, call

import pytest
import boto3
from moto import mock_s3
from storages.backends.s3boto3 import S3Boto3Storage

from common.storages import delete_storage_file, delete_storage_prefix

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('suspended', [False, True])
def test_versioned_bucket_cleanup_removes_real_versions_and_preserves_neighbors(suspended):
    with mock_s3():
        client = boto3.client('s3', region_name='us-east-1')
        bucket = 'organization-version-cleanup'
        client.create_bucket(Bucket=bucket)
        client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={'Status': 'Enabled'})
        target = 'exports/tenant_backups/abc/backup.xml'
        neighbor = 'exports/tenant_backups/abcd/keep.xml'
        for content in (b'old', b'new'):
            client.put_object(Bucket=bucket, Key=target, Body=content)
        client.delete_object(Bucket=bucket, Key=target)
        client.put_object(Bucket=bucket, Key=neighbor, Body=b'keep')
        if suspended:
            client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={'Status': 'Suspended'})
            client.put_object(Bucket=bucket, Key=target, Body=b'null version')
        storage = S3Boto3Storage(bucket_name=bucket, location='exports', region_name='us-east-1')
        delete_storage_prefix(storage, 'tenant_backups/abc/')
        delete_storage_prefix(storage, 'tenant_backups/abc/')  # A repeated cleanup is harmless.
        remaining = client.list_object_versions(Bucket=bucket, Prefix='exports/tenant_backups/abc/')
        assert not remaining.get('Versions')
        assert not remaining.get('DeleteMarkers')
        assert client.get_object(Bucket=bucket, Key=neighbor)['Body'].read() == b'keep'


@pytest.fixture
def storage():
    result = Mock(spec=S3Boto3Storage)
    result.location = 'exports'
    result.bucket_name = 'private-files'
    result.connection.meta.client.get_bucket_versioning.return_value = {'Status': 'Enabled'}
    return result


@pytest.mark.parametrize('status', ['Enabled', 'Suspended'])
def test_prefix_removes_paginated_versions_and_delete_markers(storage, status):
    client = storage.connection.meta.client
    client.get_bucket_versioning.return_value = {'Status': status}
    key = 'exports/tenant_backups/abc/backup.xml'
    client.get_paginator.return_value.paginate.return_value = [
        {'Versions': [{'Key': key, 'VersionId': 'old'}, {'Key': key, 'VersionId': 'current'}]},
        {'Versions': [{'Key': key, 'VersionId': 'null'}], 'DeleteMarkers': [{'Key': key, 'VersionId': 'marker'}]},
    ]
    progress = Mock()
    delete_storage_prefix(storage, 'tenant_backups/abc/', progress=progress)
    client.get_paginator.assert_called_once_with('list_object_versions')
    client.get_paginator.return_value.paginate.assert_called_once_with(
        Bucket='private-files', Prefix='exports/tenant_backups/abc/', PaginationConfig={'PageSize': 1000}
    )
    assert client.delete_object.call_args_list == [
        call(Bucket='private-files', Key=key, VersionId=version) for version in ['old', 'current', 'null', 'marker']
    ]
    assert progress.call_count >= 2
    storage.delete.assert_not_called()


def test_legacy_document_cleanup_matches_exact_key_only(storage):
    key = 'documents/random/report.pdf'
    storage._normalize_name.return_value = key
    client = storage.connection.meta.client
    client.get_paginator.return_value.paginate.return_value = [
        {
            'Versions': [{'Key': key, 'VersionId': 'old'}, {'Key': key + '-other', 'VersionId': 'keep'}],
            'DeleteMarkers': [{'Key': key, 'VersionId': 'marker'}],
        }
    ]
    delete_storage_file(storage, key)
    assert client.delete_object.call_args_list == [
        call(Bucket='private-files', Key=key, VersionId='old'),
        call(Bucket='private-files', Key=key, VersionId='marker'),
    ]


def test_unversioned_file_keeps_normal_storage_delete(storage):
    storage.connection.meta.client.get_bucket_versioning.return_value = {}
    delete_storage_file(storage, 'report.pdf')
    storage.delete.assert_called_once_with('report.pdf')
    storage.connection.meta.client.get_paginator.assert_not_called()


def test_cannot_confirm_versioning_does_not_report_success(storage):
    storage.connection.meta.client.get_bucket_versioning.side_effect = PermissionError('denied')
    with pytest.raises(PermissionError):
        delete_storage_file(storage, 'report.pdf')
    storage.delete.assert_not_called()


def test_delete_version_failure_propagates_for_durable_retry(storage):
    client = storage.connection.meta.client
    client.get_paginator.return_value.paginate.return_value = [
        {'Versions': [{'Key': 'exports/tenant_backups/abc/backup.xml', 'VersionId': 'old'}]}
    ]
    client.delete_object.side_effect = PermissionError('retention or denied')
    with pytest.raises(PermissionError):
        delete_storage_prefix(storage, 'tenant_backups/abc/')


def test_version_scan_rejects_another_organization(storage):
    client = storage.connection.meta.client
    client.get_paginator.return_value.paginate.return_value = [
        {'DeleteMarkers': [{'Key': 'exports/tenant_backups/abcd/backup.xml', 'VersionId': 'marker'}]}
    ]
    with pytest.raises(ValueError):
        delete_storage_prefix(storage, 'tenant_backups/abc/')
    client.delete_object.assert_not_called()
