from resume_engine.extraction.skills import SkillsExtractor
from tests.extraction_helpers import make_segmented


def test_skills_section_comma_list_taken_at_face_value():
    segmented = make_segmented(skills=["Python, FastAPI, SQL, Docker, Git"])
    results = SkillsExtractor().extract(segmented)
    values = sorted(r.value for r in results)
    assert values == ["Docker", "FastAPI", "Git", "Python", "SQL"]
    assert all(r.evidence.method == "section_heuristic" for r in results)
    assert all(not r.evidence.ambiguous for r in results)


def test_skills_section_bullet_list():
    segmented = make_segmented(skills=["- Python\n- SQL\n- Docker"])
    results = SkillsExtractor().extract(segmented)
    values = sorted(r.value for r in results)
    assert values == ["Docker", "Python", "SQL"]


def test_multi_word_skill_preserved_as_one_candidate():
    segmented = make_segmented(skills=["Machine Learning, Deep Learning, Node.js"])
    results = SkillsExtractor().extract(segmented)
    values = sorted(r.value for r in results)
    assert values == ["Deep Learning", "Machine Learning", "Node.js"]


def test_skills_section_accepts_a_term_not_in_the_seed_list():
    """The Skills section is trusted at face value -- an internal tool
    name or niche skill not in any generic seed list still belongs here,
    since the recruiter explicitly listed it as a skill."""
    segmented = make_segmented(skills=["Acme InternalToolkit, Python"])
    results = SkillsExtractor().extract(segmented)
    values = {r.value for r in results}
    assert "Acme InternalToolkit" in values


def test_skill_mentioned_in_both_skills_and_experience_is_not_duplicated():
    segmented = make_segmented(
        skills=["Python, Docker"],
        experience=["Built backend services using Python for internal tooling."],
    )
    results = SkillsExtractor().extract(segmented)
    python_results = [r for r in results if r.value == "Python"]
    assert len(python_results) == 1
    assert python_results[0].evidence.method == "section_heuristic"  # Skills section wins


def test_skill_found_only_in_experience_is_extracted_as_ambiguous():
    segmented = make_segmented(
        skills=["Python"],
        experience=["Deployed services on Kubernetes using Terraform."],
    )
    results = SkillsExtractor().extract(segmented)
    kubernetes = next(r for r in results if r.value == "Kubernetes")
    assert kubernetes.evidence.method == "seed_list_match"
    assert kubernetes.evidence.ambiguous is True


def test_abbreviations_are_matched_case_sensitively():
    segmented = make_segmented(experience=["Built REST APIs and used SQL extensively with AWS."])
    results = SkillsExtractor().extract(segmented)
    values = {r.value for r in results}
    assert {"REST", "SQL", "AWS"}.issubset(values)


def test_lowercase_abbreviation_does_not_false_positive_in_free_text():
    """'sql' lowercase in ordinary prose should not match the
    case-sensitive abbreviation pattern used for free-text scanning."""
    segmented = make_segmented(experience=["we discussed sql briefly during the interview"])
    results = SkillsExtractor().extract(segmented)
    assert results == []


def test_ordinary_english_words_are_not_extracted_as_skills():
    """Negative case: free-text scanning must not turn ordinary
    vocabulary into skill candidates."""
    segmented = make_segmented(
        experience=[
            "Led a team and improved communication across departments while managing budgets."
        ]
    )
    assert SkillsExtractor().extract(segmented) == []


def test_no_skill_inferred_merely_from_job_title():
    """A 'Data Scientist' job title must not cause skills like 'Python'
    or 'Machine Learning' to be invented if they never appear in the text."""
    segmented = make_segmented(experience=["Data Scientist, IBM, 2019 - 2021"])
    assert SkillsExtractor().extract(segmented) == []


def test_missing_skills_and_experience_sections_returns_nothing():
    segmented = make_segmented(contact=["Jamie Example"])
    assert SkillsExtractor().extract(segmented) == []


def test_unclassified_section_is_also_scanned_for_seed_terms():
    segmented = make_segmented(
        unclassified=["Side project using Docker and Kubernetes for deployment."]
    )
    results = SkillsExtractor().extract(segmented)
    values = {r.value for r in results}
    assert {"Docker", "Kubernetes"}.issubset(values)
    assert all(r.evidence.ambiguous for r in results)


def test_evidence_section_reflects_the_actual_source_section():
    """Regression test: evidence.section for a free-text skill match was
    previously hardcoded to EXPERIENCE regardless of which section the
    block actually came from, corrupting provenance for skills found in
    UNCLASSIFIED. Found while wiring CandidateProfile assembly."""
    from resume_engine.segmentation.segmenter import ResumeSection

    segmented = make_segmented(unclassified=["Side project using Docker for deployment."])
    results = SkillsExtractor().extract(segmented)
    docker_result = next(r for r in results if r.value == "Docker")
    assert docker_result.evidence.section == ResumeSection.UNCLASSIFIED
