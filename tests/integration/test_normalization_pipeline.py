"""End-to-end: ingestion -> parsing -> segmentation -> extraction ->
skill normalization, against real fixture files."""

import pytest

from resume_engine.extraction.extract import extract_candidate
from resume_engine.ingestion.loader import build_default_parser_registry, load_resume
from resume_engine.normalization.normalizer import SkillNormalizer
from resume_engine.normalization.taxonomy import load_taxonomy
from resume_engine.segmentation.segmenter import segment
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture
def registry():
    return build_default_parser_registry()


@pytest.fixture(scope="module")
def normalizer():
    return SkillNormalizer(load_taxonomy())


def _extracted_skills(registry, filename):
    document = load_resume(FIXTURES_DIR / filename, registry)
    segmented = segment(document)
    results = extract_candidate(segmented)
    return [r.value for r in results if r.field_name == "skill"]


def test_normal_resume_skills_all_resolve_to_canonical_entries(registry, normalizer):
    skills = _extracted_skills(registry, "normal_resume.pdf")
    assert skills  # sanity: fixture actually produced skill extractions
    for raw_skill in skills:
        result = normalizer.normalize(raw_skill)
        assert result.matched_entry is not None, f"expected a taxonomy match for {raw_skill!r}"


def test_table_resume_skills_normalize_correctly(registry, normalizer):
    skills = _extracted_skills(registry, "table_resume.docx")

    # The genuine technology terms must normalize to their canonical entries.
    genuine = {"Python", "SQL", "Docker"}
    for raw_skill in genuine:
        assert raw_skill in skills
        result = normalizer.normalize(raw_skill)
        assert result.matched_entry is not None, f"expected a taxonomy match for {raw_skill!r}"

    # This fixture's Skills-section table also has header/rating-level
    # cells ("Skill", "Level", "Expert", "Advanced", "Intermediate") --
    # SkillsExtractor trusts Skills-section content at face value (by
    # design, see its module docstring), so these get extracted as skill
    # *candidates* too. Normalization correctly leaves them unmatched
    # rather than forcing a false match -- it doesn't paper over an
    # extraction-stage gap, it surfaces it honestly as "unmatched".
    for non_skill in ("Skill", "Level", "Expert", "Advanced", "Intermediate"):
        assert non_skill in skills
        assert normalizer.normalize(non_skill).matched_entry is None


def test_headingless_resume_skills_normalize_correctly(registry, normalizer):
    skills = _extracted_skills(registry, "headingless_resume.pdf")
    canonical_names = {normalizer.normalize(s).matched_entry.canonical_name for s in skills}
    assert {"Python", "SQL", "Docker", "Kubernetes", "Terraform"}.issubset(canonical_names)


def test_normalization_never_crashes_on_extraction_output_across_all_fixtures(registry, normalizer):
    fixtures = [
        "normal_resume.pdf",
        "normal_resume.docx",
        "table_resume.pdf",
        "table_resume.docx",
        "two_column_resume.pdf",
        "unusual_order_resume.pdf",
        "headingless_resume.pdf",
        "empty_resume.pdf",
        "empty_resume.docx",
    ]
    for filename in fixtures:
        for raw_skill in _extracted_skills(registry, filename):
            normalizer.normalize(raw_skill)  # must not raise
