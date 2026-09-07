from tests.fixtures_path import FIXTURES_DIR

# Passes upload validation (correct magic bytes) but isn't real PDF
# structure, so the pipeline completes as "failed" with no persisted
# profile -- used for the "no profile to correct" scenarios.
FAKE_PDF_BYTES = b"%PDF-1.4 minimal fake pdf content"

# A real, parseable fixture is required for correction tests now that
# corrections are applied against an actual stored CandidateProfile, not
# just recorded as a bare audit log entry.
REAL_PDF_BYTES = (FIXTURES_DIR / "normal_resume.pdf").read_bytes()


def _upload_real_resume(client) -> str:
    response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", REAL_PDF_BYTES, "application/pdf")},
    )
    assert response.json()["status"] == "completed"
    return response.json()["candidate_id"]


def _get_profile(client, candidate_id: str) -> dict:
    return client.get(f"/resumes/{candidate_id}").json()["profile"]


def test_upload_and_process_workflow_unaffected_by_correction_changes(client):
    """Regression guard: correction persistence work must not touch the
    upload/process/GET pipeline (see test_resumes_upload.py for the full
    suite -- this is a local sanity check for this feature's own tests)."""
    response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", REAL_PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"

    get_response = client.get(f"/resumes/{body['candidate_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["profile"] is not None


def test_correct_contact_field_updates_profile_and_clears_needs_review(client):
    candidate_id = _upload_real_resume(client)
    before = _get_profile(client, candidate_id)
    full_name_before = before["contact"]["full_name"]
    assert full_name_before["needs_review"] is True  # weak heuristic match on this fixture

    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={
            "field_path": "contact.full_name.value",
            "corrected_value": "Jordan T. Testcase",
            "corrected_by": "recruiter@example.com",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["original_value"] == full_name_before["value"]
    corrected_field = body["profile"]["contact"]["full_name"]
    assert corrected_field["value"] == "Jordan T. Testcase"
    assert corrected_field["needs_review"] is False
    # Confidence is preserved as a historical record of the original
    # machine read, never fabricated for a human correction.
    assert corrected_field["confidence"] == full_name_before["confidence"]

    after = _get_profile(client, candidate_id)
    assert after["contact"]["full_name"]["value"] == "Jordan T. Testcase"
    assert after["contact"]["full_name"]["needs_review"] is False


def test_correct_experience_field_updates_profile(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "experience[0].company.value", "corrected_value": "Renamed Corp"},
    )
    assert response.status_code == 201
    company = response.json()["profile"]["experience"][0]["company"]
    assert company["value"] == "Renamed Corp"
    assert company["needs_review"] is False

    after = _get_profile(client, candidate_id)
    assert after["experience"][0]["company"]["value"] == "Renamed Corp"


def test_correct_education_field_updates_profile(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "education[0].degree.value", "corrected_value": "Master of Science"},
    )
    assert response.status_code == 201
    assert response.json()["profile"]["education"][0]["degree"]["value"] == "Master of Science"

    after = _get_profile(client, candidate_id)
    assert after["education"][0]["degree"]["value"] == "Master of Science"


def test_correct_skill_canonical_name_updates_profile(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={
            "field_path": "skills[0].canonical_name",
            "corrected_value": "React",
            "corrected_by": "recruiter@example.com",
        },
    )
    assert response.status_code == 201
    skill = response.json()["profile"]["skills"][0]
    assert skill["canonical_name"] == "React"
    assert skill["needs_review"] is False

    after = _get_profile(client, candidate_id)
    assert after["skills"][0]["canonical_name"] == "React"


def test_correct_accepts_valid_boundary_list_index(client):
    candidate_id = _upload_real_resume(client)
    before = _get_profile(client, candidate_id)
    last_index = len(before["skills"]) - 1

    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": f"skills[{last_index}].canonical_name", "corrected_value": "GitOps"},
    )
    assert response.status_code == 201
    assert response.json()["profile"]["skills"][last_index]["canonical_name"] == "GitOps"


def test_correct_rejects_invalid_list_index(client):
    candidate_id = _upload_real_resume(client)
    before = _get_profile(client, candidate_id)
    out_of_range = len(before["skills"])

    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": f"skills[{out_of_range}].canonical_name", "corrected_value": "React"},
    )
    assert response.status_code == 400

    after = _get_profile(client, candidate_id)
    assert after["skills"] == before["skills"]  # rejected correction leaves the profile untouched


def test_correct_rejects_unknown_field(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "contact.middle_name.value", "corrected_value": "Q"},
    )
    assert response.status_code == 400


def test_correct_rejects_protected_metadata_field(client):
    """confidence is machine metadata, not a recruiter-editable field --
    the whitelist has no template for it regardless of field_path shape."""
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "contact.email.confidence", "corrected_value": "0.99"},
    )
    assert response.status_code == 400


def test_correct_rejects_malformed_field_path(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "; DROP TABLE candidates; --", "corrected_value": "React"},
    )
    assert response.status_code == 400


def test_correct_rejects_empty_field_path(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "", "corrected_value": "React"},
    )
    assert response.status_code == 422  # Pydantic min_length validation


def test_correct_rejects_blank_corrected_value(client):
    candidate_id = _upload_real_resume(client)
    response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "contact.email.value", "corrected_value": "   "},
    )
    assert response.status_code == 400


def test_correct_for_unknown_candidate_returns_404(client):
    response = client.post(
        "/resumes/does-not-exist/corrections",
        json={"field_path": "skills[0].canonical_name", "corrected_value": "React"},
    )
    assert response.status_code == 404


def test_correct_rejects_candidate_with_no_persisted_profile(client):
    upload_response = client.post(
        "/resumes",
        files={"file": ("resume.pdf", FAKE_PDF_BYTES, "application/pdf")},
    )
    assert upload_response.json()["status"] == "failed"
    candidate_id = upload_response.json()["candidate_id"]

    correction_response = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "skills[0].canonical_name", "corrected_value": "React"},
    )
    assert correction_response.status_code == 400


def test_correction_audit_trail_reflects_each_prior_value(client):
    """Each correction's `original_value` should be whatever the previous
    correction left behind, proving the audit trail stays coherent across
    repeated corrections to the same field (see
    tests/unit/test_sqlite_repository.py for repository-level audit-log
    storage coverage)."""
    candidate_id = _upload_real_resume(client)

    first = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "contact.phone.value", "corrected_value": "(555) 000-0000"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/resumes/{candidate_id}/corrections",
        json={"field_path": "contact.phone.value", "corrected_value": "(555) 111-1111"},
    )
    assert second.status_code == 201
    assert second.json()["original_value"] == "(555) 000-0000"
