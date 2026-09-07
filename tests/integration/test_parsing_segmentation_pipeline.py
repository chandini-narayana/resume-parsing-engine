"""End-to-end fixture-driven tests: ingestion -> parsing -> segmentation.

These exercise the full "upload -> document parsing -> structural
representation -> section segmentation -> output ready for NLP
extraction" flow described in the task brief, against the representative
fixtures in tests/fixtures/. Task 5 (layout/reading-order validation)
lives here alongside the general pipeline checks, since layout behavior
is only meaningful once parsing and segmentation are combined.
"""

import pytest

from resume_engine.ingestion.loader import (
    IngestionError,
    build_default_parser_registry,
    load_resume,
)
from resume_engine.parsing.base import ParsingError
from resume_engine.segmentation.segmenter import ResumeSection, segment
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture
def registry():
    return build_default_parser_registry()


@pytest.mark.parametrize(
    "filename",
    [
        "normal_resume.pdf",
        "normal_resume.docx",
        "table_resume.pdf",
        "table_resume.docx",
        "two_column_resume.pdf",
        "unusual_order_resume.pdf",
    ],
)
def test_pipeline_runs_end_to_end_without_dropping_any_block(registry, filename):
    document = load_resume(FIXTURES_DIR / filename, registry)
    segmented = segment(document)

    total_in = len([b for b in document.blocks if b.text.strip()])
    # Content blocks land in `sections`; heading blocks that triggered a
    # section switch are recorded separately in `section_headings` (they're
    # labels, not section content) -- both together must account for every
    # non-empty input block, or something was silently dropped.
    total_out = sum(len(blocks) for blocks in segmented.sections.values())
    total_out += sum(len(blocks) for blocks in segmented.section_headings.values())
    assert total_out == total_in, "every non-empty block must be filed somewhere (never dropped)"


def test_normal_resume_pdf_has_no_unclassified_content(registry):
    document = load_resume(FIXTURES_DIR / "normal_resume.pdf", registry)
    segmented = segment(document)
    assert segmented.sections[ResumeSection.UNCLASSIFIED] == []


def test_table_resume_docx_table_content_lands_in_correct_section(registry):
    document = load_resume(FIXTURES_DIR / "table_resume.docx", registry)
    segmented = segment(document)
    skills_text = {b.text for b in segmented.sections[ResumeSection.SKILLS]}
    assert {"Skill", "Level", "Python", "SQL", "Docker"}.issubset(skills_text)
    education_text = [b.text for b in segmented.sections[ResumeSection.EDUCATION]]
    assert any("Master of Science" in t for t in education_text)


def test_table_resume_pdf_table_content_lands_in_correct_section(registry):
    document = load_resume(FIXTURES_DIR / "table_resume.pdf", registry)
    segmented = segment(document)
    # table_resume.pdf has no section headings at all (it's a bare table);
    # skill cells should still land somewhere, not vanish.
    total_in = len(document.blocks)
    total_out = sum(len(blocks) for blocks in segmented.sections.values())
    assert total_out == total_in


def test_two_column_resume_both_columns_reach_segmentation(registry):
    """Layout validation: content from both the left (Experience) and
    right (Skills) columns must both survive parsing AND land in their
    respective sections after segmentation -- not just be present
    somewhere in the raw block list."""
    document = load_resume(FIXTURES_DIR / "two_column_resume.pdf", registry)
    segmented = segment(document)

    experience_text = " ".join(b.text for b in segmented.sections[ResumeSection.EXPERIENCE])
    skills_text = " ".join(b.text for b in segmented.sections[ResumeSection.SKILLS])

    assert "Example Corp" in experience_text
    assert "Kubernetes" in skills_text
    # cross-contamination check: skills content should not leak into
    # experience and vice versa for this fixture
    assert "Kubernetes" not in experience_text
    assert "Example Corp" not in skills_text


def test_unusual_order_resume_heading_variants_all_recognized(registry):
    document = load_resume(FIXTURES_DIR / "unusual_order_resume.pdf", registry)
    segmented = segment(document)
    assert any("Python" in b.text for b in segmented.sections[ResumeSection.SKILLS])
    assert any("Platform Engineer" in b.text for b in segmented.sections[ResumeSection.EXPERIENCE])
    assert any("Master of Science" in b.text for b in segmented.sections[ResumeSection.EDUCATION])
    assert segmented.sections[ResumeSection.UNCLASSIFIED] == []


def test_empty_pdf_pipeline_completes_without_error(registry):
    document = load_resume(FIXTURES_DIR / "empty_resume.pdf", registry)
    segmented = segment(document)
    assert all(blocks == [] for blocks in segmented.sections.values())
    assert document.parser_warnings  # the emptiness is surfaced, not silent


def test_empty_docx_pipeline_completes_without_error(registry):
    document = load_resume(FIXTURES_DIR / "empty_resume.docx", registry)
    segmented = segment(document)
    assert all(blocks == [] for blocks in segmented.sections.values())
    assert document.parser_warnings


def test_scanned_image_pdf_pipeline_completes_without_error(registry):
    document = load_resume(FIXTURES_DIR / "scanned_image.pdf", registry)
    segmented = segment(document)
    assert all(blocks == [] for blocks in segmented.sections.values())
    assert any("image" in w.lower() for w in document.parser_warnings)


def test_corrupt_pdf_fails_loudly_not_silently(registry):
    with pytest.raises((IngestionError, ParsingError)):
        load_resume(FIXTURES_DIR / "corrupt.pdf", registry)


def test_corrupt_docx_fails_loudly_not_silently(registry):
    with pytest.raises((IngestionError, ParsingError)):
        load_resume(FIXTURES_DIR / "corrupt.docx", registry)
