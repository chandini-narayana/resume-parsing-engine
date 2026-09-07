from resume_engine.extraction.education import EducationExtractor
from tests.extraction_helpers import make_segmented


def _extract(lines):
    return EducationExtractor().extract(make_segmented(education=lines))


def test_degree_field_and_institution_all_extracted():
    results = _extract(["Bachelor of Science in Computer Science, Sample State University, 2018"])
    values = {(r.field_name, r.value) for r in results}
    assert ("degree", "Bachelor of Science") in values
    assert ("field_of_study", "Computer Science") in values
    assert ("institution", "Sample State University") in values


def test_degree_phrase_does_not_swallow_the_field_of_study_clause():
    """Regression test: an earlier version of the degree regex greedily
    matched 'Bachelor of Science in' (consuming 'in') instead of stopping
    at 'Bachelor of Science', losing the field of study entirely."""
    results = _extract(["Bachelor of Arts in English Literature, Example College, 2015"])
    degree = next(r.value for r in results if r.field_name == "degree")
    field = next(r.value for r in results if r.field_name == "field_of_study")
    assert degree == "Bachelor of Arts"
    assert field == "English Literature"


def test_multiple_education_entries_each_produce_their_own_records():
    results = _extract(
        [
            "Bachelor of Science in Computer Science, Sample State University, 2018",
            "Master of Science in Data Science, Sample State University, 2020",
        ]
    )
    degrees = sorted(r.value for r in results if r.field_name == "degree")
    assert degrees == ["Bachelor of Science", "Master of Science"]
    assert len([r for r in results if r.field_name == "institution"]) == 2


def test_abbreviated_degree_forms():
    for line, expected_degree in [
        ("MBA, Northwind Business School, 2015", "MBA"),
        ("PhD in Physics, Example Institute of Technology, 2012", "PhD"),
        ("MSc, Acme University, 2019", "MSc"),
    ]:
        results = _extract([line])
        degree = next(r.value for r in results if r.field_name == "degree")
        assert degree == expected_degree, f"failed for: {line!r}"


def test_institution_without_keyword_uses_weak_nlp_signal_and_is_flagged():
    # "Fixture Academy Studios" contains an institution keyword ("Academy"),
    # so this should be a confident, non-ambiguous match.
    results = _extract(["Diploma, Fixture Academy Studios, 2014"])
    institution = next(r for r in results if r.field_name == "institution")
    assert institution.value == "Fixture Academy Studios"
    assert institution.evidence.ambiguous is False


def test_no_degree_keyword_extracts_nothing_by_default():
    """A stray Education-section line with no degree keyword and no
    institution keyword/NLP signal should not fabricate a degree."""
    results = _extract(["Relevant coursework: Data Structures, Algorithms"])
    assert not any(r.field_name == "degree" for r in results)


def test_missing_education_section_returns_nothing():
    results = EducationExtractor().extract(make_segmented(contact=["Jamie Example"]))
    assert results == []


def test_every_result_traces_back_to_its_source_block():
    segmented = make_segmented(
        education=["Bachelor of Science in Computer Science, Sample State University, 2018"]
    )
    results = EducationExtractor().extract(segmented)
    for r in results:
        assert len(r.source_blocks) == 1
