from unittest.mock import Mock, call

import pytest
from storages.backends.s3boto3 import S3Boto3Storage

from common.storages import delete_storage_file, delete_storage_prefix


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
