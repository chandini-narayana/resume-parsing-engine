from resume_engine.extraction.titles_companies import TitlesCompaniesExtractor
from tests.extraction_helpers import make_segmented


def _extract(lines):
    return TitlesCompaniesExtractor().extract(make_segmented(experience=lines))


def test_comma_separated_title_and_company():
    results = _extract(["Senior Software Engineer, Fixture Industries Inc., 2021 - Present"])
    values = {(r.field_name, r.value) for r in results}
    assert ("job_title", "Senior Software Engineer") in values
    assert ("company", "Fixture Industries Inc.") in values


def test_title_at_company_phrasing():
    results = _extract(["VP of Engineering at Northwind Traders, 2015 - 2017"])
    values = {(r.field_name, r.value) for r in results}
    assert ("job_title", "VP of Engineering") in values
    assert ("company", "Northwind Traders") in values


def test_different_job_title_wordings_all_recognized():
    """Diverse title vocabulary, not just 'Engineer'."""
    cases = [
        ("Product Manager, Acme Widgets LLC", "Product Manager"),
        ("Data Scientist, IBM", "Data Scientist"),
        ("UX Designer, Studio Nine", "UX Designer"),
        ("Chief Technology Officer, Fixture Industries Inc.", "Chief Technology Officer"),
        ("Marketing Coordinator, Brightline Co.", "Marketing Coordinator"),
    ]
    for line, expected_title in cases:
        results = _extract([line])
        titles = [r.value for r in results if r.field_name == "job_title"]
        assert titles == [expected_title], f"failed for: {line!r}"


def test_multiple_employers_each_produce_their_own_entry():
    results = _extract(
        [
            "Senior Software Engineer, Fixture Industries Inc., 2021 - Present",
            "Software Engineer, Example Corp, 2018 - 2021",
            "Junior Developer, Northwind Traders, 2016 - 2018",
        ]
    )
    companies = sorted(r.value for r in results if r.field_name == "company")
    assert companies == ["Example Corp", "Fixture Industries Inc.", "Northwind Traders"]
    titles = sorted(r.value for r in results if r.field_name == "job_title")
    assert titles == ["Junior Developer", "Senior Software Engineer", "Software Engineer"]


def test_data_scientist_ibm_does_not_double_tag_title_as_company():
    """Regression-style check: raw spaCy tags BOTH 'Data Scientist' and
    'IBM' as ORG on this input (see nlp_model.py docstring) -- the
    title-keyword heuristic must take priority so the title isn't also
    emitted as a company."""
    results = _extract(["Data Scientist, IBM"])
    assert [r.value for r in results if r.field_name == "job_title"] == ["Data Scientist"]
    assert [r.value for r in results if r.field_name == "company"] == ["IBM"]


def test_ambiguous_org_like_phrase_falls_back_positionally_and_is_flagged():
    """Neither segment matches a title keyword or a company suffix, and
    spaCy finds no ORG in either -- positional fallback applies, and the
    result must be flagged ambiguous so a confidence stage can discount it."""
    results = _extract(["Riverside Team, Blue Horizon"])
    assert len(results) == 2
    assert all(r.evidence.ambiguous for r in results)
    assert all(r.evidence.method == "positional_fallback" for r in results)


def test_missing_company_when_line_has_only_a_title():
    results = _extract(["Senior Software Engineer"])
    assert [r.field_name for r in results] == ["job_title"]


def test_single_segment_with_no_signal_extracts_nothing():
    """No comma, no title keyword, no company suffix, no ORG match --
    must not fabricate either field."""
    results = _extract(["Worked closely with cross-functional teams"])
    assert results == []


def test_pure_description_line_extracts_nothing():
    results = _extract(["Built internal tooling for synthetic test data generation."])
    assert results == []


def test_missing_experience_section_returns_nothing():
    results = TitlesCompaniesExtractor().extract(make_segmented(contact=["Jamie Example"]))
    assert results == []


def test_every_result_traces_back_to_its_source_block():
    segmented = make_segmented(
        experience=["Senior Software Engineer, Fixture Industries Inc., 2021 - Present"]
    )
    results = TitlesCompaniesExtractor().extract(segmented)
    for r in results:
        assert len(r.source_blocks) == 1
        assert (
            r.source_blocks[0].text
            == "Senior Software Engineer, Fixture Industries Inc., 2021 - Present"
        )
