"""Full end-to-end pipeline tests: file -> ResumeProcessingPipeline ->
CandidateProfile, against real fixture files. Complements
tests/unit/test_pipeline_assembly.py (assembly logic in isolation) and
tests/unit/test_pipeline_orchestrator.py (orchestrator error handling)
with genuine parsing-through-normalization runs.
"""

import pytest

from resume_engine.pipeline.orchestrator import ResumeProcessingPipeline
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture(scope="module")
def pipeline():
    return ResumeProcessingPipeline()


def test_normal_resume_pdf_end_to_end(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    profile = result.profile

    assert profile.contact.full_name.value == "Jordan Testcase"
    assert profile.contact.email.value == "jordan.testcase@example.com"
    assert profile.contact.phone.value == "(555) 123-4567"

    assert len(profile.experience) == 2
    titles = {e.job_title.value for e in profile.experience if e.job_title}
    assert titles == {"Senior Software Engineer", "Software Engineer"}

    assert len(profile.education) == 1
    assert profile.education[0].degree.value == "Bachelor of Science"

    skill_names = {s.canonical_name for s in profile.skills}
    assert {"Python", "FastAPI", "SQL", "Docker", "Git"}.issubset(skill_names)


def test_normal_resume_docx_end_to_end(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.docx")
    profile = result.profile
    assert profile.contact.email.value == "jordan.testcase@example.com"
    assert profile.experience
    assert profile.education
    assert profile.skills


def test_table_resume_docx_end_to_end(pipeline):
    result = pipeline.process(FIXTURES_DIR / "table_resume.docx")
    profile = result.profile
    skill_names = {s.canonical_name for s in profile.skills}
    assert {"Python", "SQL", "Docker"}.issubset(skill_names)
    # header/rating cells extracted alongside real skills correctly stay unmatched
    unmatched = {s.mentions[0].raw_text for s in profile.skills if s.canonical_name is None}
    assert "Level" in unmatched or "Expert" in unmatched


def test_two_column_resume_end_to_end(pipeline):
    result = pipeline.process(FIXTURES_DIR / "two_column_resume.pdf")
    profile = result.profile
    assert any(e.company and "Example Corp" in e.company.value for e in profile.experience)
    assert any(s.canonical_name == "Kubernetes" for s in profile.skills)


def test_headingless_resume_end_to_end(pipeline):
    result = pipeline.process(FIXTURES_DIR / "headingless_resume.pdf")
    profile = result.profile
    assert profile.contact.email.value == "riley.headingless@example.com"
    assert profile.experience[0].company.value == "Example Corp"
    assert profile.education[0].degree.value == "Bachelor of Science"
    skill_names = {s.canonical_name for s in profile.skills}
    assert {"Python", "SQL", "Docker", "Kubernetes", "Terraform"}.issubset(skill_names)


def test_every_experience_entry_has_provenance(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    for entry in result.profile.experience:
        assert entry.provenance.block_ids
        assert entry.provenance.original_text


def test_every_skill_mention_traces_back_to_a_real_block(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    for skill in result.profile.skills:
        for mention in skill.mentions:
            assert mention.provenance.block_ids
            assert mention.provenance.original_text


def test_scanned_image_pdf_completes_with_empty_profile_not_failure(pipeline):
    result = pipeline.process(FIXTURES_DIR / "scanned_image.pdf")
    assert result.status == "completed"
    assert result.profile.skills == []
    assert result.profile.parser_warnings  # the emptiness is still surfaced


def test_source_filename_is_preserved(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    assert result.profile.source_filename == "normal_resume.pdf"
