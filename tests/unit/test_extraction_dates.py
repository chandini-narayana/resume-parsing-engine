from resume_engine.extraction.dates import (
    DatesExtractor,
    find_date_mentions,
    find_date_ranges,
    find_standalone_dates,
    strip_date_text,
)
from tests.extraction_helpers import make_segmented

# --- format coverage: MM/YYYY, Month YYYY, YYYY, YYYY-YYYY, YYYY to Present, Present/current ---


def test_year_range_with_hyphen():
    ranges = find_date_ranges("2019 - 2022")
    assert [r.text for r in ranges] == ["2019 - 2022"]


def test_year_range_with_en_dash():
    ranges = find_date_ranges("2019–2022")
    assert [r.text for r in ranges] == ["2019–2022"]


def test_year_to_present():
    ranges = find_date_ranges("2019 to Present")
    assert [r.text for r in ranges] == ["2019 to Present"]
    assert ranges[0].end.precision == "present"


def test_month_year_range():
    ranges = find_date_ranges("March 2020 - January 2022")
    assert [r.text for r in ranges] == ["March 2020 - January 2022"]
    assert ranges[0].start.precision == "month_year"


def test_abbreviated_month_year_range():
    ranges = find_date_ranges("Jan 2019 – Dec 2021")
    assert [r.text for r in ranges] == ["Jan 2019 – Dec 2021"]


def test_numeric_month_year_range():
    ranges = find_date_ranges("03/2018 - 01/2021")
    assert [r.text for r in ranges] == ["03/2018 - 01/2021"]
    assert ranges[0].start.precision == "numeric_month_year"


def test_current_as_open_end():
    ranges = find_date_ranges("June 2021 - Current")
    assert [r.text for r in ranges] == ["June 2021 - Current"]


def test_standalone_year():
    mentions = find_standalone_dates("Graduated 2018")
    assert [m.text for m in mentions] == ["2018"]
    assert mentions[0].precision == "year_only"


def test_bare_present_alone_is_not_a_range():
    assert find_date_ranges("Present") == []


# --- avoiding false positives ---


def test_no_dates_in_plain_text():
    assert find_date_mentions("No dates in this line at all") == []


def test_phone_number_is_not_mistaken_for_a_date():
    # sanity check that phone-like text near a section doesn't confuse date parsing
    assert find_date_ranges("(555) 123-4567") == []


# --- strip_date_text ---


def test_strip_date_text_removes_range_and_cleans_punctuation():
    assert (
        strip_date_text("Senior Engineer, Acme Corp, 2021 - Present")
        == "Senior Engineer, Acme Corp"
    )


def test_strip_date_text_removes_standalone_year():
    assert (
        strip_date_text("Bachelor of Science, Acme University, 2018")
        == "Bachelor of Science, Acme University"
    )


def test_strip_date_text_no_dates_returns_text_unchanged():
    assert strip_date_text("No dates here") == "No dates here"


# --- DatesExtractor (FieldExtractor) ---


def test_dates_extractor_only_scans_experience_and_education():
    segmented = make_segmented(
        experience=["Engineer, Acme Corp, 2019 - 2022"],
        education=["BSc, Acme University, 2018"],
        skills=["Uses 2020 vintage tools"],  # a bare year in Skills must NOT be extracted
        contact=["Reachable through 2025 (not a real signal)"],
    )
    results = DatesExtractor().extract(segmented)
    values = {(r.field_name, r.value) for r in results}
    assert ("date_range", "2019 - 2022") in values
    assert ("date", "2018") in values
    assert not any(r.value == "2020" for r in results)
    assert not any(r.value == "2025" for r in results)


def test_dates_extractor_flags_bare_year_as_ambiguous_weak():
    segmented = make_segmented(education=["BSc, Acme University, 2018"])
    results = DatesExtractor().extract(segmented)
    date_result = next(r for r in results if r.field_name == "date")
    assert date_result.evidence.ambiguous is True
    assert date_result.evidence.matching_strength == "weak"


def test_dates_extractor_range_is_not_ambiguous():
    segmented = make_segmented(experience=["Engineer, Acme Corp, 2019 - 2022"])
    results = DatesExtractor().extract(segmented)
    range_result = next(r for r in results if r.field_name == "date_range")
    assert range_result.evidence.ambiguous is False
    assert range_result.evidence.matching_strength == "exact"


def test_dates_extractor_tolerates_missing_sections():
    segmented = make_segmented(contact=["Jamie Example"])
    assert DatesExtractor().extract(segmented) == []
