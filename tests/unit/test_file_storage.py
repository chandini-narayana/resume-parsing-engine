import pytest

from resume_engine.storage.file_storage import LocalFileStorage


def test_save_and_read_roundtrip(tmp_path):
    storage = LocalFileStorage(tmp_path / "uploads")
    ref = storage.save("abc123.pdf", b"hello world")
    assert storage.read(ref) == b"hello world"


def test_delete_removes_file(tmp_path):
    storage = LocalFileStorage(tmp_path / "uploads")
    ref = storage.save("abc123.pdf", b"hello world")
    storage.delete(ref)
    with pytest.raises(FileNotFoundError):
        storage.read(ref)


def test_rejects_path_traversal_filename(tmp_path):
    storage = LocalFileStorage(tmp_path / "uploads")
    with pytest.raises(ValueError):
        storage.save("../escape.pdf", b"data")
