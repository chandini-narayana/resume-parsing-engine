from resume_engine.extraction.contact import ContactExtractor
from tests.extraction_helpers import make_segmented


def test_extracts_email_phone_and_name():
    segmented = make_segmented(
        contact=["Jordan Testcase", "jordan.testcase@example.com | (555) 123-4567"]
    )
    results = ContactExtractor().extract(segmented)
    values = {(r.field_name, r.value) for r in results}
    assert ("full_name", "Jordan Testcase") in values
    assert ("email", "jordan.testcase@example.com") in values
    assert ("phone", "(555) 123-4567") in values


def test_extracts_bare_domain_url():
    segmented = make_segmented(contact=["linkedin.com/in/jordantestcase"])
    results = ContactExtractor().extract(segmented)
    assert any(
        r.field_name == "url" and r.value == "linkedin.com/in/jordantestcase" for r in results
    )


def test_url_does_not_duplicate_as_emails_domain():
    segmented = make_segmented(contact=["jordan.testcase@example.com"])
    results = ContactExtractor().extract(segmented)
    urls = [r for r in results if r.field_name == "url"]
    assert urls == []  # the email's own domain must not also become a "url" extraction


def test_only_first_name_like_block_is_taken_as_name():
    segmented = make_segmented(contact=["Jordan Testcase", "Also Looks Name Like"])
    results = ContactExtractor().extract(segmented)
    names = [r for r in results if r.field_name == "full_name"]
    assert len(names) == 1
    assert names[0].value == "Jordan Testcase"


def test_name_extraction_is_flagged_ambiguous():
    segmented = make_segmented(contact=["Jordan Testcase"])
    results = ContactExtractor().extract(segmented)
    name_result = next(r for r in results if r.field_name == "full_name")
    assert name_result.evidence.ambiguous is True
    assert name_result.evidence.matching_strength == "weak"


def test_email_extraction_is_not_ambiguous():
    segmented = make_segmented(contact=["jordan.testcase@example.com"])
    results = ContactExtractor().extract(segmented)
    email_result = next(r for r in results if r.field_name == "email")
    assert email_result.evidence.ambiguous is False
    assert email_result.evidence.method == "regex"


def test_missing_contact_section_returns_nothing():
    segmented = make_segmented(experience=["Engineer, Acme Corp"])
    assert ContactExtractor().extract(segmented) == []


def test_no_email_or_phone_present_does_not_fabricate():
    segmented = make_segmented(contact=["Address available upon request"])
    results = ContactExtractor().extract(segmented)
    assert not any(r.field_name in ("email", "phone") for r in results)
