"""Local file storage for uploaded resumes (behind a replaceable interface).

MVP requirement is controlled local storage, not cloud storage -- but
callers depend only on the FileStorage interface, so a future
S3/GCS-backed implementation is a drop-in replacement, not a rewrite.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class FileStorage(ABC):
    @abstractmethod
    def save(self, stored_filename: str, content: bytes) -> str:
        """Persist `content` under `stored_filename`. Returns a storage
        reference (implementation-defined) to pass to `read`/`delete`."""
        raise NotImplementedError

    @abstractmethod
    def read(self, storage_ref: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_ref: str) -> None:
        raise NotImplementedError

    def path_for(self, storage_ref: str) -> Path | None:
        """A real filesystem Path for `storage_ref`, if this storage is
        local-file-backed -- parsers need an actual Path, not bytes.
        Returns None for a backend with no local path (e.g. a future
        cloud-backed implementation), which callers must handle explicitly
        (e.g. by writing `read()`'s bytes to a temp file first) rather
        than assuming one always exists."""
        return None


class LocalFileStorage(FileStorage):
    """Stores files under a single controlled root directory.

    `stored_filename` must already be a server-generated safe name (see
    security/filenames.py) -- this class does not sanitize input, by
    design, so that path-safety stays owned in one place.
    """

    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def save(self, stored_filename: str, content: bytes) -> str:
        target = self._resolve(stored_filename)
        target.write_bytes(content)
        return stored_filename

    def read(self, storage_ref: str) -> bytes:
        return self._resolve(storage_ref).read_bytes()

    def delete(self, storage_ref: str) -> None:
        self._resolve(storage_ref).unlink(missing_ok=True)

    def path_for(self, storage_ref: str) -> Path | None:
        return self._resolve(storage_ref)

    def _resolve(self, stored_filename: str) -> Path:
        # Reject anything that isn't a bare filename -- defence in depth
        # against path traversal even though filenames are server-generated.
        if "/" in stored_filename or "\\" in stored_filename or stored_filename in {".", ".."}:
            raise ValueError("Invalid stored filename.")
        resolved = (self._root_dir / stored_filename).resolve()
        root = self._root_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError("Resolved path escapes storage root.")
        return resolved
