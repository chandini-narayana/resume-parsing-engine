"""Safe filename / path handling.

Never trust a client-supplied filename for building a filesystem path
(directory traversal, null bytes, collisions, overlong names). Storage
filenames are always generated server-side; the original filename is kept
only as display metadata, and even then it is sanitized before being
shown or logged.
"""

from __future__ import annotations

import re
import uuid

_DISPLAY_SANITIZE_RE = re.compile(r"[^A-Za-z0-9 ._\-]")


def generate_stored_filename(original_filename: str, allowed_extensions: tuple[str, ...]) -> str:
    """Return a safe, collision-free filename to use on disk.

    The returned name is `<uuid4>.<ext>` -- it never incorporates any part
    of the client-supplied name, which eliminates path traversal and
    collision risk by construction rather than by trying to blocklist bad
    characters.
    """
    ext = _extract_extension(original_filename)
    if ext not in {e.lower() for e in allowed_extensions}:
        raise ValueError(f"Extension '{ext}' is not permitted")
    return f"{uuid.uuid4().hex}{ext}"


def sanitize_for_display(original_filename: str, max_length: int = 255) -> str:
    """Strip path separators/control characters for safe display or logging.

    This is metadata only -- it must never be used to construct a
    filesystem path.
    """
    name = original_filename.replace("\\", "/").split("/")[-1]
    name = _DISPLAY_SANITIZE_RE.sub("_", name).strip()
    return name[:max_length] or "unnamed"


def _extract_extension(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()
