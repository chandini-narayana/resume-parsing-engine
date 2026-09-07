"""The 12 diverse extraction scenarios required by the task brief, each
run through the full extract_candidate() pipeline (SegmentedDocument ->
RawExtractions) with exact expected-value assertions.
"""

from resume_engine.extraction.extract import extract_candidate
from resume_engine.representation.document import BlockKind, TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument
from tests.extraction_helpers import make_segmented, table_block


def _values(results, field_name):
    return sorted(r.value for r in results if r.field_name == field_name)


# 1. Standard professional resume -------------------------------------------
def test_scenario_1_standard_professional_resume():
    segmented = make_segmented(
        contact=["Jordan Testcase", "jordan.testcase@example.com | (555) 123-4567"],
        experience=["Senior Software Engineer, Fixture Industries Inc., 2021 - Present"],
        education=["Bachelor of Science in Computer Science, Sample State University, 2018"],
        skills=["Python, FastAPI, SQL, Docker, Git"],
    )
    results = extract_candidate(segmented)
    assert _values(results, "email") == ["jordan.testcase@example.com"]
    assert _values(results, "phone") == ["(555) 123-4567"]
    assert _values(results, "job_title") == ["Senior Software Engineer"]
    assert _values(results, "company") == ["Fixture Industries Inc."]
    assert _values(results, "date_range") == ["2021 - Present"]
    assert _values(results, "degree") == ["Bachelor of Science"]
    assert _values(results, "institution") == ["Sample State University"]
    assert _values(results, "skill") == ["Docker", "FastAPI", "Git", "Python", "SQL"]


# 2. Different job title wording ---------------------------------------------
def test_scenario_2_different_job_title_wording():
    segmented = make_segmented(
        experience=[
            "Head of Product, Acme Widgets LLC, 2020 - Present",
            "Marketing Coordinator, Brightline Co., 2018 - 2020",
        ]
    )
    results = extract_candidate(segmented)
    assert _values(results, "job_title") == ["Head of Product", "Marketing Coordinator"]


# 3. Multiple employers -------------------------------------------------------
def test_scenario_3_multiple_employers():
    segmented = make_segmented(
        experience=[
            "Senior Software Engineer, Fixture Industries Inc., 2021 - Present",
            "Software Engineer, Example Corp, 2018 - 2021",
            "Junior Developer, Northwind Traders, 2016 - 2018",
        ]
    )
    results = extract_candidate(segmented)
    assert _values(results, "company") == [
        "Example Corp",
        "Fixture Industries Inc.",
        "Northwind Traders",
    ]
    assert len(_values(results, "date_range")) == 3


# 4. Multiple employment date formats -----------------------------------------
def test_scenario_4_multiple_date_formats():
    segmented = make_segmented(
        experience=[
            "Engineer A, Company A, 2019 - 2022",
            "Engineer B, Company B, 03/2018 - 01/2019",
            "Engineer C, Company C, March 2015 - January 2018",
            "Engineer D, Company D, Jan 2022 to Present",
        ]
    )
    results = extract_candidate(segmented)
    ranges = _values(results, "date_range")
    assert ranges == [
        "03/2018 - 01/2019",
        "2019 - 2022",
        "Jan 2022 to Present",
        "March 2015 - January 2018",
    ]


# 5. Multiple education entries -----------------------------------------------
def test_scenario_5_multiple_education_entries():
    segmented = make_segmented(
        education=[
            "Bachelor of Science in Computer Science, Sample State University, 2018",
            "Master of Science in Data Science, Sample State University, 2020",
        ]
    )
    results = extract_candidate(segmented)
    assert _values(results, "degree") == ["Bachelor of Science", "Master of Science"]
    assert _values(results, "field_of_study") == ["Computer Science", "Data Science"]


# 6. Skills appearing both in Skills and Experience --------------------------
def test_scenario_6_skills_in_both_sections_not_duplicated():
    segmented = make_segmented(
        skills=["Python, Docker"],
        experience=["Built backend services using Python and deployed with Kubernetes."],
    )
    results = extract_candidate(segmented)
    skill_results = [r for r in results if r.field_name == "skill"]
    assert sorted(r.value for r in skill_results) == ["Docker", "Kubernetes", "Python"]
    python_results = [r for r in skill_results if r.value == "Python"]
    assert len(python_results) == 1  # not duplicated across sections


# 7. Abbreviations -------------------------------------------------------------
def test_scenario_7_abbreviations():
    segmented = make_segmented(skills=["SQL, AWS, GCP, REST, ML, AI"])
    results = extract_candidate(segmented)
    assert _values(results, "skill") == ["AI", "AWS", "GCP", "ML", "REST", "SQL"]


# 8. Multi-word skills -----------------------------------------------------
def test_scenario_8_multi_word_skills():
    segmented = make_segmented(skills=["Machine Learning, Node.js, Power BI"])
    results = extract_candidate(segmented)
    assert _values(results, "skill") == ["Machine Learning", "Node.js", "Power BI"]


# 9. Ambiguous organization-like phrases --------------------------------------
def test_scenario_9_ambiguous_org_like_phrase_flagged():
    segmented = make_segmented(experience=["Riverside Team, Blue Horizon"])
    results = extract_candidate(segmented)
    title_or_company = [r for r in results if r.field_name in ("job_title", "company")]
    assert len(title_or_company) == 2
    assert all(r.evidence.ambiguous for r in title_or_company)


# 10. Missing fields -----------------------------------------------------------
def test_scenario_10_missing_fields_not_fabricated():
    segmented = make_segmented(
        contact=["jordan.testcase@example.com"],  # no phone, no name
        experience=["Senior Software Engineer"],  # no company, no dates
    )
    results = extract_candidate(segmented)
    assert _values(results, "phone") == []
    assert _values(results, "company") == []
    assert _values(results, "date_range") == []
    assert _values(results, "job_title") == ["Senior Software Engineer"]
    assert _values(results, "email") == ["jordan.testcase@example.com"]


# 11. Headingless sections where the segmenter uses fallbacks -----------------
def test_scenario_11_headingless_sections():
    """Uses segmentation directly (not make_segmented, which pre-assigns
    sections) to confirm the fallback-classified sections still extract
    correctly downstream."""
    from resume_engine.representation.document import ParsedDocument
    from resume_engine.segmentation.segmenter import segment

    blocks = [
        TextBlock(text="Riley Headingless", kind=BlockKind.PARAGRAPH),
        TextBlock(text="riley.headingless@example.com", kind=BlockKind.PARAGRAPH),
        TextBlock(text="Backend Engineer, Example Corp, 2020 - Present", kind=BlockKind.PARAGRAPH),
        TextBlock(
            text="Bachelor of Science in Computer Science, Sample State University, 2016",
            kind=BlockKind.PARAGRAPH,
        ),
        TextBlock(text="Python, SQL, Docker, Kubernetes, Terraform", kind=BlockKind.PARAGRAPH),
    ]
    document = ParsedDocument(source_filename="headingless.pdf", source_format="pdf", blocks=blocks)
    segmented = segment(document)
    results = extract_candidate(segmented)

    assert _values(results, "email") == ["riley.headingless@example.com"]
    assert _values(results, "job_title") == ["Backend Engineer"]
    assert _values(results, "company") == ["Example Corp"]
    assert _values(results, "degree") == ["Bachelor of Science"]
    assert _values(results, "skill") == ["Docker", "Kubernetes", "Python", "SQL", "Terraform"]


# 12. Table-derived content -----------------------------------------------------
def test_scenario_12_table_derived_skills_content():
    sections = {s: [] for s in ResumeSection}
    sections[ResumeSection.SKILLS] = [
        table_block("Python", "t0", 0, 0),
        table_block("Expert", "t0", 0, 1),
        table_block("SQL", "t0", 1, 0),
        table_block("Advanced", "t0", 1, 1),
    ]
    segmented = SegmentedDocument(source_filename="table.docx", sections=sections)
    results = extract_candidate(segmented)
    assert _values(results, "skill") == ["Advanced", "Expert", "Python", "SQL"]


def test_scenario_12_table_derived_experience_content():
    sections = {s: [] for s in ResumeSection}
    sections[ResumeSection.EXPERIENCE] = [
        table_block(
            "Senior Software Engineer, Fixture Industries Inc., 2021 - Present", "t0", 0, 0
        ),
    ]
    segmented = SegmentedDocument(source_filename="table.docx", sections=sections)
    results = extract_candidate(segmented)
    assert _values(results, "job_title") == ["Senior Software Engineer"]
    assert _values(results, "company") == ["Fixture Industries Inc."]
    assert _values(results, "date_range") == ["2021 - Present"]
