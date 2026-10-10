import json
import os
import tempfile
import uuid
import zipfile
from typing import Union
from django.db import transaction
from django.core.files import File

from apps.demo.models import DocumentDemoItem
from common.storages import get_user_exports_storage
from ..protocols import UserDataExportable, UserFilesExportable
from ....models import User
from utils import hashid


class CrudDemoItemDataExport(UserDataExportable):
    export_key = "crud_demo_items"

    @classmethod
    def export(cls, user: User) -> list[str]:
        return [
            json.dumps(
                {
                    "id": hashid.encode(item.id),
                    "name": item.name,
                }
            )
            for item in user.cruddemoitem_set.all()
        ]


class DocumentDemoItemFileExport(UserFilesExportable):
    @classmethod
    def export(cls, user: User) -> list[str]:
        return [document.file.name for document in user.documents.all()]


class UserDataExport(UserDataExportable):
    export_key = "user"
    schema_class = User

    @classmethod
    def export(cls, user: User) -> Union[str, list[str]]:
        user_data = {
            "id": hashid.encode(user.id),
            "profile": {
                "id": user.profile.id,
                "first_name": user.profile.first_name,
                "last_name": user.profile.last_name,
            },
            "email": user.email,
            "is_superuser": user.is_superuser,
            "is_active": user.is_active,
            "is_confirmed": user.is_confirmed,
            "created": user.created.isoformat(),
        }

        return json.dumps(user_data)


class ExportUserArchive:
    _DATA_EXPORTS: list[UserDataExportable] = [UserDataExport, CrudDemoItemDataExport]
    _FILES_EXPORTS: list[UserFilesExportable] = [DocumentDemoItemFileExport]

    def __init__(self, user: User):
        self._user = user

    @property
    def _user_id(self) -> str:
        return hashid.encode(self._user.id)

    def run(self) -> str:
        with transaction.atomic():
            # Deletion takes this lock before collecting paths and deleting the account.
            self._user = User.objects.select_for_update().get(pk=self._user.pk)
            archive_filename = self._export_user_archive_to_zip(self._export_user_data(), self._export_user_files())
            try:
                return self._export_zip_archive_to_s3(archive_filename)
            finally:
                os.unlink(archive_filename)

    def _export_user_data(self) -> dict:
        export_data = {}

        for user_data_export in self._DATA_EXPORTS:
            export_data[user_data_export.export_key] = user_data_export.export(self._user)

        return export_data

    def _export_user_files(self) -> list:
        export_files_paths = []

        for user_file_export in self._FILES_EXPORTS:
            export_files_paths.extend(user_file_export.export(self._user))

        return export_files_paths

    def _export_user_archive_to_zip(self, user_data: dict, user_files: list[str]) -> str:
        descriptor, archive_filename = tempfile.mkstemp(suffix='.zip')
        os.close(descriptor)

        try:
            with zipfile.ZipFile(archive_filename, "w", zipfile.ZIP_DEFLATED) as zf:
                json_data_filename = f"{self._user_id}/{self._user_id}.json"
                zf.writestr(json_data_filename, json.dumps(user_data).encode("utf-8"))

                for file_path in user_files:
                    with DocumentDemoItem._meta.get_field('file').storage.open(file_path, 'rb') as source:
                        zf.writestr(f"{self._user_id}/{file_path}", source.read())
        except Exception:
            os.unlink(archive_filename)
            raise

        return archive_filename

    def _export_zip_archive_to_s3(self, user_archive_filename: str) -> str:
        storage = get_user_exports_storage()
        user_archive_obj_key = self._get_user_archive_obj_key()
        with open(user_archive_filename, 'rb') as source:
            path = storage.save(user_archive_obj_key, File(source))
        return storage.url(path)

    def _get_user_archive_obj_key(self) -> str:
        return f"users/{self._user_id}/{uuid.uuid4()}.zip"
