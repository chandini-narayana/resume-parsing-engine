import pytest

from resume_engine.corrections.applier import CorrectionError, apply_correction


def _scored(value, needs_review=True, confidence=0.5):
    return {
        "value": value,
        "confidence": confidence,
        "needs_review": needs_review,
        "provenance": {"section": None, "block_ids": [], "page_numbers": [], "original_text": []},
        "extraction_evidence": None,
    }


def _profile_data():
    return {
        "source_filename": "resume.pdf",
        "contact": {
            "full_name": _scored("Jordan Testcase"),
            "email": _scored("jordan@example.com", needs_review=False, confidence=0.95),
            "phone": None,
            "location": None,
            "links": [_scored("https://example.com/jordan")],
        },
        "skills": [
            {
                "canonical_name": None,
                "mentions": [
                    {
                        "raw_text": "Pythom",
                        "confidence": 0.4,
                        "needs_review": True,
                        "provenance": {
                            "section": None,
                            "block_ids": [],
                            "page_numbers": [],
                            "original_text": [],
                        },
                        "extraction_evidence": None,
                    }
                ],
                "normalization_evidence": {"method": "unmatched", "match_score": 0.0},
                "normalization_confidence": 0.0,
                "needs_review": True,
            }
        ],
        "experience": [
            {
                "job_title": _scored("Engineer"),
                "company": _scored("Acme"),
                "start_date": _scored("2020"),
                "end_date": None,
                "is_current": False,
                "provenance": {
                    "section": None,
                    "block_ids": [],
                    "page_numbers": [],
                    "original_text": [],
                },
            }
        ],
        "education": [
            {
                "institution": _scored("State University"),
                "degree": _scored("BS"),
                "field_of_study": None,
                "graduation_date": None,
                "provenance": {
                    "section": None,
                    "block_ids": [],
                    "page_numbers": [],
                    "original_text": [],
                },
            }
        ],
        "parser_warnings": [],
        "unclassified_text": [],
    }


def test_applies_contact_scalar_correction_and_clears_needs_review():
    data = _profile_data()
    applied = apply_correction(data, "contact.full_name.value", "Jordan T. Testcase")
    assert applied.original_value == "Jordan Testcase"
    assert data["contact"]["full_name"]["value"] == "Jordan T. Testcase"
    assert data["contact"]["full_name"]["needs_review"] is False
    assert data["contact"]["full_name"]["confidence"] == 0.5  # preserved, not fabricated


def test_applies_contact_link_correction():
    data = _profile_data()
    apply_correction(data, "contact.links[0].value", "https://example.com/new")
    assert data["contact"]["links"][0]["value"] == "https://example.com/new"


def test_applies_skill_canonical_name_correction():
    data = _profile_data()
    applied = apply_correction(data, "skills[0].canonical_name", "Python")
    assert applied.original_value is None  # was unmatched
    assert data["skills"][0]["canonical_name"] == "Python"
    assert data["skills"][0]["needs_review"] is False
    assert data["skills"][0]["normalization_confidence"] == 0.0  # preserved, not fabricated


def test_applies_skill_mention_raw_text_correction():
    data = _profile_data()
    apply_correction(data, "skills[0].mentions[0].raw_text", "Python")
    assert data["skills"][0]["mentions"][0]["raw_text"] == "Python"
    assert data["skills"][0]["mentions"][0]["needs_review"] is False
    # correcting one mention does not cascade into the entry-level flag
    assert data["skills"][0]["needs_review"] is True


def test_applies_experience_field_correction():
    data = _profile_data()
    apply_correction(data, "experience[0].company.value", "New Co")
    assert data["experience"][0]["company"]["value"] == "New Co"


def test_applies_education_field_correction():
    data = _profile_data()
    apply_correction(data, "education[0].degree.value", "MS")
    assert data["education"][0]["degree"]["value"] == "MS"


def test_rejects_correction_through_a_field_never_extracted():
    data = _profile_data()
    with pytest.raises(CorrectionError, match="never extracted"):
        apply_correction(data, "contact.phone.value", "555-0100")


def test_rejects_out_of_range_list_index():
    data = _profile_data()
    with pytest.raises(CorrectionError, match="index 5"):
        apply_correction(data, "skills[5].canonical_name", "React")


def test_rejects_unknown_field():
    data = _profile_data()
    with pytest.raises(CorrectionError):
        apply_correction(data, "contact.middle_name.value", "Q")


def test_rejects_protected_metadata_path():
    data = _profile_data()
    with pytest.raises(CorrectionError):
        apply_correction(data, "contact.email.confidence", "0.99")


def test_rejects_blank_corrected_value():
    data = _profile_data()
    with pytest.raises(CorrectionError, match="blank"):
        apply_correction(data, "contact.email.value", "   ")


def test_does_not_mutate_on_rejection():
    data = _profile_data()
    original = _profile_data()
    with pytest.raises(CorrectionError):
        apply_correction(data, "skills[5].canonical_name", "React")
    assert data == original
