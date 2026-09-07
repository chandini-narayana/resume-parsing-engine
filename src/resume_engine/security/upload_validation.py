"""Strict upload validation for resume files.

Applies three independent checks -- extension allowlist, file size limit,
and magic-byte signature -- before a file is ever written to disk or
handed to a parser. All three must pass; relying on the extension alone is
not sufficient (a renamed file would pass an extension-only check).
"""

from __future__ import annotations

from dataclasses import dataclass

# Signature bytes for the formats this MVP accepts.
_PDF_MAGIC = b"%PDF-"
_DOCX_MAGIC = b"PK\x03\x04"  # DOCX is a zip container


class UploadValidationError(ValueError):
    """Raised when an uploaded file fails validation. Safe to show to the
    client -- the message never includes file content or internal paths."""


@dataclass(frozen=True)
class UploadLimits:
    allowed_extensions: tuple[str, ...]
    max_size_bytes: int


def validate_upload(filename: str, content: bytes, limits: UploadLimits) -> str:
    """Validate an uploaded resume. Returns the validated lowercase extension.

    Raises UploadValidationError on any failure. Does not raise for
    ambiguous/ok content -- unrecognized-but-within-limits content still
    goes through parsing, where parse failures are surfaced explicitly
    rather than here.
    """
    if not content:
        raise UploadValidationError("Uploaded file is empty.")

    if len(content) > limits.max_size_bytes:
        raise UploadValidationError(
            f"File exceeds the maximum allowed size of {limits.max_size_bytes // (1024 * 1024)} MB."
        )

    ext = _extract_extension(filename)
    if ext not in {e.lower() for e in limits.allowed_extensions}:
        raise UploadValidationError(
            f"Unsupported file type '{ext or 'unknown'}'. Allowed types: "
            f"{', '.join(limits.allowed_extensions)}."
        )

    if ext == ".pdf" and not content.startswith(_PDF_MAGIC):
        raise UploadValidationError("File does not look like a valid PDF.")
    if ext == ".docx" and not content.startswith(_DOCX_MAGIC):
        raise UploadValidationError("File does not look like a valid DOCX.")

    return ext


def _extract_extension(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()
