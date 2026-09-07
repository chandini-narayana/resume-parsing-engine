from resume_engine.persistence.models import CandidateRecord, Correction, ReviewState
from resume_engine.persistence.sqlite_repository import SqliteCandidateRepository


def _make_repo(tmp_path):
    return SqliteCandidateRepository(tmp_path / "test.sqlite3")


def _sample_record(candidate_id="c1"):
    return CandidateRecord(
        id=candidate_id,
        original_filename="resume.pdf",
        stored_filename="abc123.pdf",
        file_format="pdf",
        file_size_bytes=1234,
        status="uploaded",
        uploaded_at="2026-08-28T00:00:00+00:00",
    )


def test_create_and_get_candidate(tmp_path):
    repo = _make_repo(tmp_path)
    repo.create_candidate(_sample_record())
    fetched = repo.get_candidate("c1")
    assert fetched is not None
    assert fetched.original_filename == "resume.pdf"
    assert fetched.status == "uploaded"


def test_get_missing_candidate_returns_none(tmp_path):
    repo = _make_repo(tmp_path)
    assert repo.get_candidate("does-not-exist") is None


def test_update_candidate_status(tmp_path):
    repo = _make_repo(tmp_path)
    repo.create_candidate(_sample_record())
    repo.update_candidate_status("c1", "processing")
    assert repo.get_candidate("c1").status == "processing"


def test_save_and_get_profile_json(tmp_path):
    repo = _make_repo(tmp_path)
    repo.create_candidate(_sample_record())
    repo.save_profile_json("c1", '{"skills": []}')
    assert repo.get_profile_json("c1") == '{"skills": []}'
    # upsert on second save
    repo.save_profile_json("c1", '{"skills": ["Python"]}')
    assert repo.get_profile_json("c1") == '{"skills": ["Python"]}'


def test_add_and_list_corrections(tmp_path):
    repo = _make_repo(tmp_path)
    repo.create_candidate(_sample_record())
    repo.add_correction(
        Correction(
            id=0,
            candidate_id="c1",
            field_path="skills[0].canonical_name",
            original_value="Reactjs",
            corrected_value="React",
            corrected_by="recruiter@example.com",
            corrected_at="2026-08-28T00:00:00+00:00",
        )
    )
    corrections = repo.list_corrections("c1")
    assert len(corrections) == 1
    assert corrections[0].corrected_value == "React"


def test_set_and_get_review_state(tmp_path):
    repo = _make_repo(tmp_path)
    repo.create_candidate(_sample_record())
    repo.set_review_state(
        ReviewState(
            candidate_id="c1",
            status="pending_review",
            reviewed_by=None,
            reviewed_at=None,
            notes=None,
        )
    )
    state = repo.get_review_state("c1")
    assert state.status == "pending_review"
    # upsert
    repo.set_review_state(
        ReviewState(
            candidate_id="c1",
            status="approved",
            reviewed_by="r1",
            reviewed_at="now",
            notes="looks good",
        )
    )
    state = repo.get_review_state("c1")
    assert state.status == "approved"
    assert state.reviewed_by == "r1"
