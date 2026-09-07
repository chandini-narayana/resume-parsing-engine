from tests.fixtures_path import FIXTURES_DIR

# Used for upload-validation-layer tests (extension/size/magic-byte checks,
# which run before parsing) -- these never need to be a real parseable PDF.
FAKE_PDF_BYTES = b"%PDF-1.4 minimal fake pdf content"

# Used for tests that exercise the full pipeline -- must be real,
# parseable content, since the upload endpoint now runs parsing/
# segmentation/extraction/normalization synchronously.
REAL_PDF_BYTES = (FIXTURES_DIR / "normal_resume.pdf").read_bytes()


def test_upload_valid_pdf_processes_successfully(client):
    response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", REAL_PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["file_format"] == "pdf"
    assert body["original_filename"] == "resume.pdf"
    assert "candidate_id" in body


def test_upload_rejects_disallowed_extension(client):
    response = client.post(
        "/resumes",
        files={"file": ("resume.exe", b"MZ fake exe", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client):
    # test client fixture is configured with max_upload_size_mb=1
    oversized = FAKE_PDF_BYTES + b"0" * (2 * 1024 * 1024)
    response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_rejects_mismatched_magic_bytes(client):
    response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", b"not a real pdf", "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_of_unparseable_pdf_completes_as_failed_not_500(client):
    """Passes upload validation (correct magic bytes) but isn't real PDF
    structure -- the pipeline should fail gracefully, not 500."""
    response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", FAKE_PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"


def test_get_processed_resume_returns_profile(client):
    upload_response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", REAL_PDF_BYTES, "application/pdf")},
    )
    candidate_id = upload_response.json()["candidate_id"]

    get_response = client.get(f"/resumes/{candidate_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["candidate_id"] == candidate_id
    assert body["status"] == "completed"
    assert body["processing_error"] is None
    assert body["profile"] is not None
    assert body["profile"]["contact"]["email"]["value"] == "jordan.testcase@example.com"


def test_get_failed_resume_returns_safe_error_message(client):
    upload_response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", FAKE_PDF_BYTES, "application/pdf")},
    )
    candidate_id = upload_response.json()["candidate_id"]

    get_response = client.get(f"/resumes/{candidate_id}")
    body = get_response.json()
    assert body["status"] == "failed"
    assert body["processing_error"] is not None
    assert body["profile"] is None
    # never leak internal detail
    assert "Traceback" not in body["processing_error"]
    assert "/home/" not in body["processing_error"]
    assert "site-packages" not in body["processing_error"]


def test_get_unknown_resume_returns_404(client):
    response = client.get("/resumes/does-not-exist")
    assert response.status_code == 404
