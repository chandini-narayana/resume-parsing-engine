import pytest

from resume_engine.security.upload_validation import (
    UploadLimits,
    UploadValidationError,
    validate_upload,
)

LIMITS = UploadLimits(allowed_extensions=(".pdf", ".docx"), max_size_bytes=1024)
PDF_BYTES = b"%PDF-1.4 rest of a fake pdf"
DOCX_BYTES = b"PK\x03\x04 rest of a fake docx"


def test_accepts_valid_pdf():
    ext = validate_upload("resume.pdf", PDF_BYTES, LIMITS)
    assert ext == ".pdf"


def test_accepts_valid_docx():
    ext = validate_upload("resume.docx", DOCX_BYTES, LIMITS)
    assert ext == ".docx"


def test_rejects_empty_file():
    with pytest.raises(UploadValidationError):
        validate_upload("resume.pdf", b"", LIMITS)


def test_rejects_oversized_file():
    with pytest.raises(UploadValidationError):
        validate_upload("resume.pdf", PDF_BYTES * 200, LIMITS)


def test_rejects_disallowed_extension():
    with pytest.raises(UploadValidationError):
        validate_upload("resume.exe", PDF_BYTES, LIMITS)


def test_rejects_mismatched_magic_bytes():
    # .pdf extension but content that isn't actually a PDF
    with pytest.raises(UploadValidationError):
        validate_upload("resume.pdf", b"not really a pdf", LIMITS)
