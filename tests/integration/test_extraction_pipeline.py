"""End-to-end tests: ingestion -> parsing -> segmentation -> extraction,
against real fixture files (not hand-built SegmentedDocuments)."""

import pytest

from resume_engine.extraction.extract import extract_candidate
from resume_engine.ingestion.loader import build_default_parser_registry, load_resume
from resume_engine.segmentation.segmenter import segment
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture
def registry():
    return build_default_parser_registry()


def _run_pipeline(registry, filename):
    document = load_resume(FIXTURES_DIR / filename, registry)
    segmented = segment(document)
    return extract_candidate(segmented)


@pytest.mark.parametrize(
    "filename",
    [
        "normal_resume.pdf",
        "normal_resume.docx",
        "table_resume.pdf",
        "table_resume.docx",
        "two_column_resume.pdf",
        "unusual_order_resume.pdf",
        "headingless_resume.pdf",
    ],
)
def test_extraction_runs_without_crashing_on_every_fixture(registry, filename):
    results = _run_pipeline(registry, filename)
    assert isinstance(results, list)  # doesn't crash; may legitimately be empty for some fixtures


def test_normal_resume_pdf_full_extraction(registry):
    results = _run_pipeline(registry, "normal_resume.pdf")
    field_values = {(r.field_name, r.value) for r in results}
    assert ("email", "jordan.testcase@example.com") in field_values
    assert ("phone", "(555) 123-4567") in field_values
    assert any(f == "job_title" and "Engineer" in v for f, v in field_values)
    assert any(f == "company" for f, v in field_values)
    assert any(f == "degree" for f, v in field_values)
    assert any(f == "skill" and v == "Python" for f, v in field_values)


def test_table_resume_docx_skills_extracted_from_table(registry):
    results = _run_pipeline(registry, "table_resume.docx")
    skills = {r.value for r in results if r.field_name == "skill"}
    assert {"Python", "SQL", "Docker"}.issubset(skills)


def test_two_column_resume_extracts_from_both_columns(registry):
    results = _run_pipeline(registry, "two_column_resume.pdf")
    field_values = {(r.field_name, r.value) for r in results}
    assert any(f == "company" and "Example Corp" in v for f, v in field_values)
    assert any(f == "skill" and v == "Kubernetes" for f, v in field_values)


def test_unusual_order_resume_extracts_despite_heading_variants(registry):
    results = _run_pipeline(registry, "unusual_order_resume.pdf")
    field_values = {(r.field_name, r.value) for r in results}
    assert any(f == "job_title" and "Platform Engineer" in v for f, v in field_values)
    assert any(f == "skill" and v == "Python" for f, v in field_values)
    assert any(f == "degree" for f, v in field_values)


def test_headingless_resume_extracts_via_fallback_sections(registry):
    results = _run_pipeline(registry, "headingless_resume.pdf")
    field_values = {(r.field_name, r.value) for r in results}
    assert ("email", "riley.headingless@example.com") in field_values
    assert ("job_title", "Backend Engineer") in field_values
    assert ("company", "Example Corp") in field_values
    assert ("degree", "Bachelor of Science") in field_values
    assert any(f == "skill" and v == "Terraform" for f, v in field_values)


def test_empty_resume_pdf_extracts_nothing_without_crashing(registry):
    results = _run_pipeline(registry, "empty_resume.pdf")
    assert results == []


def test_empty_resume_docx_extracts_nothing_without_crashing(registry):
    results = _run_pipeline(registry, "empty_resume.docx")
    assert results == []


def test_scanned_image_pdf_extracts_nothing_without_crashing(registry):
    results = _run_pipeline(registry, "scanned_image.pdf")
    assert results == []


def test_every_extraction_traces_back_to_a_real_source_block(registry):
    results = _run_pipeline(registry, "normal_resume.pdf")
    for r in results:
        assert len(r.source_blocks) >= 1
        for block in r.source_blocks:
            assert block.block_id is not None
