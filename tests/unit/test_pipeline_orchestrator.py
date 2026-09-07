import pytest

from resume_engine.extraction.base import ExtractionEvidence, FieldExtractor, RawExtraction
from resume_engine.pipeline.orchestrator import ProcessingResult, ResumeProcessingPipeline
from resume_engine.segmentation.segmenter import ResumeSection
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture(scope="module")
def pipeline():
    return ResumeProcessingPipeline()


def test_successful_pdf_processing_returns_completed_with_profile(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    assert isinstance(result, ProcessingResult)
    assert result.status == "completed"
    assert result.profile is not None
    assert result.error_message is None
    assert result.profile.contact.email.value == "jordan.testcase@example.com"


def test_successful_docx_processing_returns_completed_with_profile(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.docx")
    assert result.status == "completed"
    assert result.profile is not None
    assert result.profile.contact.email.value == "jordan.testcase@example.com"


def test_corrupt_pdf_returns_failed_not_an_exception(pipeline):
    result = pipeline.process(FIXTURES_DIR / "corrupt.pdf")
    assert result.status == "failed"
    assert result.profile is None
    assert result.error_message is not None


def test_corrupt_docx_returns_failed_not_an_exception(pipeline):
    result = pipeline.process(FIXTURES_DIR / "corrupt.docx")
    assert result.status == "failed"
    assert result.profile is None


def test_failure_error_message_never_leaks_local_paths(pipeline):
    result = pipeline.process(FIXTURES_DIR / "corrupt.pdf")
    assert str(FIXTURES_DIR) not in result.error_message


def test_missing_file_returns_failed(pipeline, tmp_path):
    result = pipeline.process(tmp_path / "does_not_exist.pdf")
    assert result.status == "failed"
    assert result.profile is None


def test_empty_resume_still_completes_with_an_empty_profile(pipeline):
    result = pipeline.process(FIXTURES_DIR / "empty_resume.pdf")
    assert result.status == "completed"
    assert result.profile is not None
    assert result.profile.skills == []
    assert result.profile.experience == []


class _ExplodingExtractor(FieldExtractor):
    """Simulates an extraction-stage failure to verify the orchestrator
    degrades to a safe 'failed' result instead of propagating the
    exception to the caller."""

    def extract(self, segmented) -> list[RawExtraction]:  # noqa: ANN001
        raise RuntimeError("simulated extraction failure with a fake /local/path/leak")


def test_extraction_failure_is_caught_and_returns_safe_failed_result():
    pipeline = ResumeProcessingPipeline(extractors=[_ExplodingExtractor()])
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    assert result.status == "failed"
    assert result.profile is None
    assert result.error_message is not None
    assert "/local/path/leak" not in result.error_message
    assert "RuntimeError" not in result.error_message


def test_custom_extractors_are_used_instead_of_defaults():
    """Dependency injection point: a custom extractor list replaces the
    default set entirely."""

    class _OnlyEmailExtractor(FieldExtractor):
        def extract(self, segmented) -> list[RawExtraction]:  # noqa: ANN001
            blocks = segmented.sections.get(ResumeSection.CONTACT, [])
            if not blocks:
                return []
            return [
                RawExtraction(
                    field_name="email",
                    value="stubbed@example.com",
                    source_blocks=[blocks[0]],
                    evidence=ExtractionEvidence(method="test_stub", section=ResumeSection.CONTACT),
                )
            ]

    pipeline = ResumeProcessingPipeline(extractors=[_OnlyEmailExtractor()])
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    assert result.status == "completed"
    assert result.profile.contact.email.value == "stubbed@example.com"
    # the default extractors would have found job titles/skills too -- a
    # custom extractor list fully replaces them, so those are absent here
    assert result.profile.experience == []
    assert result.profile.skills == []


def test_default_pipeline_uses_full_default_extractor_set(pipeline):
    result = pipeline.process(FIXTURES_DIR / "normal_resume.pdf")
    assert result.profile.experience  # the default set finds job titles too, unlike the stub above
