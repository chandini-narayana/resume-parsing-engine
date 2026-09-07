import pytest

from resume_engine.security.filenames import generate_stored_filename, sanitize_for_display

ALLOWED = (".pdf", ".docx")


def test_generate_stored_filename_uses_uuid_and_correct_extension():
    stored = generate_stored_filename("my resume.pdf", ALLOWED)
    assert stored.endswith(".pdf")
    assert "my resume" not in stored


def test_generate_stored_filename_rejects_disallowed_extension():
    with pytest.raises(ValueError):
        generate_stored_filename("resume.exe", ALLOWED)


def test_generate_stored_filename_ignores_path_traversal_in_original_name():
    stored = generate_stored_filename("../../etc/passwd.pdf", ALLOWED)
    assert "/" not in stored
    assert ".." not in stored


def test_sanitize_for_display_strips_path_separators():
    assert sanitize_for_display("../../secret/resume.pdf") == "resume.pdf"


def test_sanitize_for_display_handles_empty_name():
    assert sanitize_for_display("") == "unnamed"
