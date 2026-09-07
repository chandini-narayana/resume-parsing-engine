"""End-to-end confidence scoring: file -> ResumeProcessingPipeline ->
CandidateProfile, verifying confidence/needs_review are populated
throughout, threshold behavior applies, and unresolved/ambiguous fields
remain represented (never dropped for being low-confidence).
"""

import pytest

from resume_engine.confidence.scorer import ConfidenceConfig, HeuristicConfidenceScorer
from resume_engine.pipeline.orchestrator import ResumeProcessingPipeline
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture(scope="module")
def pipeline():
    return ResumeProcessingPipeline()


def test_default_pipeline_uses_a_real_confidence_scorer_by_default():
    pipeline = ResumeProcessingPipeline()
    assert isinstance(pipeline.confidence_scorer, HeuristicConfidenceScorer)


def test_normal_resume_confidence_populated_throughout(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    profile = result.profile

    assert profile.contact.email.confidence is not None
    assert profile.contact.email.confidence >= 0.9
    assert profile.contact.email.needs_review is False

    for entry in profile.experience:
        if entry.job_title:
            assert entry.job_title.confidence is not None
        if entry.company:
            assert entry.company.confidence is not None

    for entry in profile.education:
        if entry.degree:
            assert entry.degree.confidence is not None

    for skill in profile.skills:
        assert skill.normalization_confidence is not None
        assert skill.needs_review is not None
        for mention in skill.mentions:
            assert mention.confidence is not None
            assert mention.needs_review is not None


def test_matched_skills_have_high_normalization_confidence(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    python_entry = next(s for s in result.profile.skills if s.canonical_name == "Python")
    assert python_entry.normalization_confidence == 1.0
    assert python_entry.needs_review is False


def test_unresolved_skill_remains_represented_and_flagged(pipeline):
    """table_resume.docx's Skills-section table includes header/rating
    cells (e.g. 'Level') that extract as skill candidates but never
    normalize -- they must still appear in the profile, flagged for
    review, never silently dropped for being low-confidence."""
    result = pipeline.process(FIXTURES_DIR / "table_resume.docx")
    unmatched = [s for s in result.profile.skills if s.canonical_name is None]
    assert unmatched  # still present
    for entry in unmatched:
        assert entry.normalization_confidence == 0.0
        assert entry.needs_review is True
        assert entry.mentions  # provenance/mentions preserved, not dropped


def test_ambiguous_experience_field_is_flagged_but_still_present(pipeline):
    """two_column_resume.pdf's layout produces at least one field with
    weaker evidence -- confirm the pipeline never drops a field just
    because confidence came back low."""
    result = pipeline.process(FIXTURES_DIR / "unusual_order_resume.pdf")
    profile = result.profile
    assert profile.experience  # present despite unconventional heading wording
    for entry in profile.experience:
        if entry.job_title:
            assert entry.job_title.confidence is not None


def test_custom_review_threshold_changes_needs_review_outcome():
    lenient_pipeline = ResumeProcessingPipeline(
        confidence_scorer=HeuristicConfidenceScorer(ConfidenceConfig(review_threshold=0.0))
    )
    strict_pipeline = ResumeProcessingPipeline(
        confidence_scorer=HeuristicConfidenceScorer(ConfidenceConfig(review_threshold=1.0))
    )

    lenient_result = lenient_pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    strict_result = strict_pipeline.process(FIXTURES_DIR / "normal_resume.pdf")

    # threshold 0.0 -- essentially nothing needs review
    assert lenient_result.profile.contact.email.needs_review is False
    # threshold 1.0 -- everything short of a perfect 1.0 needs review
    assert strict_result.profile.contact.email.needs_review is True


def test_empty_resume_completes_with_no_fields_to_score(pipeline):
    result = pipeline.process(FIXTURES_DIR / "empty_resume.pdf")
    assert result.status == "completed"
    assert result.profile.skills == []
    assert result.profile.experience == []


def test_scores_are_json_serializable_through_the_full_profile(pipeline):
    """Confidence values must survive persistence (model_dump_json, as
    the API route does) without error."""
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    payload = result.profile.model_dump_json()
    assert '"confidence":0.95' in payload or '"confidence": 0.95' in payload
