import pytest

from resume_engine.confidence.scorer import ConfidenceScorer
from resume_engine.extraction.base import ExtractionEvidence, RawExtraction
from resume_engine.normalization.normalizer import SkillNormalizer
from resume_engine.normalization.taxonomy import load_taxonomy
from resume_engine.pipeline.assembly import assemble_profile
from resume_engine.representation.document import BlockKind, ParsedDocument, TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument


def _block(text, block_id, page_number=1, kind=BlockKind.PARAGRAPH):
    return TextBlock(text=text, kind=kind, block_id=block_id, page_number=page_number)


def _extraction(field_name, value, section, block, method="regex", **evidence_kwargs):
    return RawExtraction(
        field_name=field_name,
        value=value,
        source_blocks=[block],
        evidence=ExtractionEvidence(method=method, section=section, **evidence_kwargs),
    )


def _normalizer():
    return SkillNormalizer(load_taxonomy())


def _document(blocks, source_format="pdf"):
    return ParsedDocument(source_filename="test.pdf", source_format=source_format, blocks=blocks)


def _empty_segmented():
    return SegmentedDocument(source_filename="test.pdf", sections={s: [] for s in ResumeSection})


# --- contact ---


def test_contact_takes_first_occurrence_of_singular_fields():
    b1 = _block("jordan.testcase@example.com", "b0")
    b2 = _block("jordan.alt@example.com", "b1")
    extractions = [
        _extraction("email", "jordan.testcase@example.com", ResumeSection.CONTACT, b1),
        _extraction("email", "jordan.alt@example.com", ResumeSection.CONTACT, b2),
    ]
    profile = assemble_profile(_document([b1, b2]), _empty_segmented(), extractions, _normalizer())
    assert profile.contact.email.value == "jordan.testcase@example.com"


def test_contact_links_deduplicated_by_value_kept_plural():
    b = _block("linkedin.com/in/x", "b0")
    extractions = [
        _extraction("url", "linkedin.com/in/x", ResumeSection.CONTACT, b),
        _extraction("url", "linkedin.com/in/x", ResumeSection.CONTACT, b),  # exact duplicate
        _extraction("url", "github.com/x", ResumeSection.CONTACT, b),  # distinct
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    values = {link.value for link in profile.contact.links}
    assert values == {"linkedin.com/in/x", "github.com/x"}
    assert len(profile.contact.links) == 2


# --- experience ---


def test_experience_groups_fields_from_same_block_into_one_entry():
    b = _block("Senior Software Engineer, Fixture Industries Inc., 2021 - Present", "b0")
    extractions = [
        _extraction("job_title", "Senior Software Engineer", ResumeSection.EXPERIENCE, b),
        _extraction("company", "Fixture Industries Inc.", ResumeSection.EXPERIENCE, b),
        _extraction("date_range", "2021 - Present", ResumeSection.EXPERIENCE, b),
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    assert len(profile.experience) == 1
    entry = profile.experience[0]
    assert entry.job_title.value == "Senior Software Engineer"
    assert entry.company.value == "Fixture Industries Inc."
    assert entry.start_date.value == "2021"
    assert entry.end_date is None
    assert entry.is_current is True


def test_two_roles_at_same_company_produce_two_entries_not_merged():
    """Repeated employer mentions must not automatically collapse into one
    experience record -- two different blocks are two different roles."""
    b1 = _block("Senior Engineer, Acme Corp, 2021 - Present", "b0")
    b2 = _block("Junior Engineer, Acme Corp, 2018 - 2021", "b1")
    extractions = [
        _extraction("job_title", "Senior Engineer", ResumeSection.EXPERIENCE, b1),
        _extraction("company", "Acme Corp", ResumeSection.EXPERIENCE, b1),
        _extraction("date_range", "2021 - Present", ResumeSection.EXPERIENCE, b1),
        _extraction("job_title", "Junior Engineer", ResumeSection.EXPERIENCE, b2),
        _extraction("company", "Acme Corp", ResumeSection.EXPERIENCE, b2),
        _extraction("date_range", "2018 - 2021", ResumeSection.EXPERIENCE, b2),
    ]
    profile = assemble_profile(_document([b1, b2]), _empty_segmented(), extractions, _normalizer())
    assert len(profile.experience) == 2
    titles = {e.job_title.value for e in profile.experience}
    assert titles == {"Senior Engineer", "Junior Engineer"}


def test_closed_date_range_sets_end_date_and_not_current():
    b = _block("Software Engineer, Example Corp, 2018 - 2021", "b0")
    extractions = [_extraction("date_range", "2018 - 2021", ResumeSection.EXPERIENCE, b)]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    entry = profile.experience[0]
    assert entry.start_date.value == "2018"
    assert entry.end_date.value == "2021"
    assert entry.is_current is False


def test_experience_with_only_title_has_no_fabricated_company_or_dates():
    b = _block("Senior Software Engineer", "b0")
    extractions = [
        _extraction("job_title", "Senior Software Engineer", ResumeSection.EXPERIENCE, b)
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    entry = profile.experience[0]
    assert entry.job_title.value == "Senior Software Engineer"
    assert entry.company is None
    assert entry.start_date is None
    assert entry.end_date is None


# --- education ---


def test_education_groups_fields_from_same_block():
    b = _block("Bachelor of Science in Computer Science, Sample University, 2018", "b0")
    extractions = [
        _extraction("degree", "Bachelor of Science", ResumeSection.EDUCATION, b),
        _extraction("field_of_study", "Computer Science", ResumeSection.EDUCATION, b),
        _extraction("institution", "Sample University", ResumeSection.EDUCATION, b),
        _extraction("date", "2018", ResumeSection.EDUCATION, b),
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    assert len(profile.education) == 1
    entry = profile.education[0]
    assert entry.degree.value == "Bachelor of Science"
    assert entry.field_of_study.value == "Computer Science"
    assert entry.institution.value == "Sample University"
    assert entry.graduation_date.value == "2018"


def test_two_degrees_produce_two_education_entries():
    b1 = _block("Bachelor of Science, Sample University, 2018", "b0")
    b2 = _block("Master of Science, Sample University, 2020", "b1")
    extractions = [
        _extraction("degree", "Bachelor of Science", ResumeSection.EDUCATION, b1),
        _extraction("degree", "Master of Science", ResumeSection.EDUCATION, b2),
    ]
    profile = assemble_profile(_document([b1, b2]), _empty_segmented(), extractions, _normalizer())
    assert len(profile.education) == 2


# --- skills ---


def test_skills_with_same_canonical_name_merge_into_one_entry():
    """'ML' and 'Machine Learning' are different raw phrases that
    normalize to the same canonical skill -- must not produce two
    entries."""
    b1 = _block("Skills: Machine Learning", "b0")
    b2 = _block("Used ML extensively.", "b1")
    extractions = [
        _extraction(
            "skill", "Machine Learning", ResumeSection.SKILLS, b1, method="section_heuristic"
        ),
        _extraction(
            "skill", "ML", ResumeSection.EXPERIENCE, b2, method="seed_list_match", ambiguous=True
        ),
    ]
    profile = assemble_profile(_document([b1, b2]), _empty_segmented(), extractions, _normalizer())
    matching = [s for s in profile.skills if s.canonical_name == "Machine Learning"]
    assert len(matching) == 1
    assert len(matching[0].mentions) == 2
    raw_texts = {m.raw_text for m in matching[0].mentions}
    assert raw_texts == {"Machine Learning", "ML"}


def test_distinct_unmatched_skills_stay_separate():
    b = _block("Skills: Acme InternalToolkit, SomeOtherProprietaryThing", "b0")
    extractions = [
        _extraction(
            "skill", "Acme InternalToolkit", ResumeSection.SKILLS, b, method="section_heuristic"
        ),
        _extraction(
            "skill",
            "SomeOtherProprietaryThing",
            ResumeSection.SKILLS,
            b,
            method="section_heuristic",
        ),
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    unmatched = [s for s in profile.skills if s.canonical_name is None]
    assert len(unmatched) == 2
    raw_texts = {s.mentions[0].raw_text for s in unmatched}
    assert raw_texts == {"Acme InternalToolkit", "SomeOtherProprietaryThing"}


def test_unresolved_skill_is_preserved_with_none_canonical_name():
    b = _block("Skills: Acme InternalToolkit", "b0")
    extractions = [
        _extraction(
            "skill", "Acme InternalToolkit", ResumeSection.SKILLS, b, method="section_heuristic"
        )
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    assert len(profile.skills) == 1
    assert profile.skills[0].canonical_name is None
    assert profile.skills[0].mentions[0].raw_text == "Acme InternalToolkit"
    assert profile.skills[0].normalization_evidence.method == "unmatched"


def test_repeated_exact_same_unmatched_text_merges():
    b1 = _block("Uses WidgetForge.", "b0")
    b2 = _block("Expert in WidgetForge.", "b1")
    extractions = [
        _extraction("skill", "WidgetForge", ResumeSection.SKILLS, b1, method="section_heuristic"),
        _extraction("skill", "WidgetForge", ResumeSection.SKILLS, b2, method="section_heuristic"),
    ]
    profile = assemble_profile(_document([b1, b2]), _empty_segmented(), extractions, _normalizer())
    assert len(profile.skills) == 1
    assert len(profile.skills[0].mentions) == 2


# --- unclassified content ---


def test_unclassified_content_preserved_in_profile():
    b = _block("An unrecognized objective statement about career goals.", "b0")
    segmented = SegmentedDocument(
        source_filename="test.pdf",
        sections={s: [] for s in ResumeSection} | {ResumeSection.UNCLASSIFIED: [b]},
    )
    profile = assemble_profile(_document([b]), segmented, [], _normalizer())
    assert profile.unclassified_text == ["An unrecognized objective statement about career goals."]


def test_empty_unclassified_blocks_are_skipped_not_fabricated():
    b = _block("   ", "b0")
    segmented = SegmentedDocument(
        source_filename="test.pdf",
        sections={s: [] for s in ResumeSection} | {ResumeSection.UNCLASSIFIED: [b]},
    )
    profile = assemble_profile(_document([b]), segmented, [], _normalizer())
    assert profile.unclassified_text == []


# --- provenance ---


def test_provenance_includes_block_id_page_and_original_text():
    b = _block("jordan.testcase@example.com", "b0", page_number=2)
    extractions = [_extraction("email", "jordan.testcase@example.com", ResumeSection.CONTACT, b)]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    prov = profile.contact.email.provenance
    assert prov.block_ids == ["b0"]
    assert prov.page_numbers == [2]
    assert prov.original_text == ["jordan.testcase@example.com"]
    assert prov.section == "contact"


def test_docx_provenance_page_number_is_none_not_fabricated():
    b = _block("jordan.testcase@example.com", "b0", page_number=None)
    extractions = [_extraction("email", "jordan.testcase@example.com", ResumeSection.CONTACT, b)]
    profile = assemble_profile(
        _document([b], source_format="docx"), _empty_segmented(), extractions, _normalizer()
    )
    assert profile.contact.email.provenance.page_numbers == [None]


def test_confidence_and_needs_review_are_populated_by_the_scorer():
    b = _block("jordan.testcase@example.com", "b0")
    extractions = [_extraction("email", "jordan.testcase@example.com", ResumeSection.CONTACT, b)]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    # regex  exact  no red flags -> high confidence, per HeuristicConfidenceScorer's defaults
    assert profile.contact.email.confidence == pytest.approx(0.95)
    assert profile.contact.email.needs_review is False


def test_low_confidence_evidence_produces_low_score_and_needs_review():
    b = _block("Riverside Team", "b0")
    extractions = [
        _extraction(
            "job_title",
            "Riverside Team",
            ResumeSection.EXPERIENCE,
            b,
            method="positional_fallback",
            matching_strength="weak",
            ambiguous=True,
            signals_agree=False,
        )
    ]
    profile = assemble_profile(_document([b]), _empty_segmented(), extractions, _normalizer())
    entry = profile.experience[0]
    assert entry.job_title.confidence is not None
    assert entry.job_title.confidence < 0.6
    assert entry.job_title.needs_review is True


def test_confidence_scorer_is_injectable():
    """A custom ConfidenceScorer can be supplied instead of the default
    HeuristicConfidenceScorer -- dependency injection, not a hard-coded
    concrete class."""

    class _AlwaysZeroScorer(ConfidenceScorer):
        def score(self, extraction):  # noqa: ANN001, ANN201
            return 0.0

        def score_normalization(self, result):  # noqa: ANN001, ANN201
            return 0.0

    b = _block("jordan.testcase@example.com", "b0")
    extractions = [_extraction("email", "jordan.testcase@example.com", ResumeSection.CONTACT, b)]
    profile = assemble_profile(
        _document([b]), _empty_segmented(), extractions, _normalizer(), _AlwaysZeroScorer()
    )
    assert profile.contact.email.confidence == 0.0
    assert profile.contact.email.needs_review is True


# --- parser_warnings passthrough ---


def test_parser_warnings_are_carried_through():
    document = ParsedDocument(
        source_filename="test.pdf",
        source_format="pdf",
        blocks=[],
        parser_warnings=["No extractable text found."],
    )
    profile = assemble_profile(document, _empty_segmented(), [], _normalizer())
    assert profile.parser_warnings == ["No extractable text found."]
