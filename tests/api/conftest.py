import pytest
from fastapi.testclient import TestClient

from resume_engine.api.dependencies import (
    provide_file_storage,
    provide_repository,
    provide_settings,
)
from resume_engine.api.main import app
from resume_engine.config import Settings
from resume_engine.persistence.sqlite_repository import SqliteCandidateRepository
from resume_engine.storage.file_storage import LocalFileStorage


@pytest.fixture
def client(tmp_path):
    test_settings = Settings(
        sqlite_db_path=tmp_path / "test.sqlite3",
        upload_storage_dir=tmp_path / "uploads",
        max_upload_size_mb=1,
    )

    def _repository():
        return SqliteCandidateRepository(test_settings.sqlite_db_path)

    def _file_storage():
        return LocalFileStorage(test_settings.upload_storage_dir)

    app.dependency_overrides[provide_settings] = lambda: test_settings
    app.dependency_overrides[provide_repository] = _repository
    app.dependency_overrides[provide_file_storage] = _file_storage

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
