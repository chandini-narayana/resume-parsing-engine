from resume_engine.representation.document import BlockKind, ParsedDocument, TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, segment


def _block(text: str, kind: BlockKind = BlockKind.PARAGRAPH) -> TextBlock:
    return TextBlock(text=text, kind=kind)


def test_segments_document_with_conventional_headings():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Jamie Example", BlockKind.HEADING),
            _block("jamie@example.com"),
            _block("Experience", BlockKind.HEADING),
            _block("Engineer, Example Corp, 2020 - Present"),
            _block("Education", BlockKind.HEADING),
            _block("BSc Computer Science, Sample University"),
            _block("Skills", BlockKind.HEADING),
            _block("Python, SQL, Docker"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.CONTACT]] == [
        "Jamie Example",
        "jamie@example.com",
    ]
    assert [b.text for b in seg.sections[ResumeSection.EXPERIENCE]] == [
        "Engineer, Example Corp, 2020 - Present"
    ]
    assert [b.text for b in seg.sections[ResumeSection.EDUCATION]] == [
        "BSc Computer Science, Sample University"
    ]
    assert [b.text for b in seg.sections[ResumeSection.SKILLS]] == ["Python, SQL, Docker"]
    assert seg.sections[ResumeSection.UNCLASSIFIED] == []


def test_recognizes_heading_variants_not_exactly_named_in_brief():
    """'Skills & Technologies' isn't one of the enumerated phrases, but it
    is heading-like and contains the 'technologies' keyword stem."""
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Skills & Technologies", BlockKind.HEADING),
            _block("Python, SQL"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.SKILLS]] == ["Python, SQL"]


def test_case_and_punctuation_insensitive_heading_matching():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("WORK EXPERIENCE:", BlockKind.HEADING),
            _block("Engineer, Example Corp"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.EXPERIENCE]] == ["Engineer, Example Corp"]


def test_missing_section_is_simply_absent_not_an_error():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Experience", BlockKind.HEADING),
            _block("Engineer, Example Corp"),
        ],
    )
    seg = segment(doc)
    assert seg.sections[ResumeSection.SKILLS] == []
    assert seg.sections[ResumeSection.EDUCATION] == []


def test_contact_detected_by_content_without_a_heading():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[_block("Reach me at jamie@example.com or (555) 111-2222")],
    )
    seg = segment(doc)
    assert len(seg.sections[ResumeSection.CONTACT]) == 1


def test_date_range_without_heading_falls_back_to_experience():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[_block("Engineer, Example Corp, 2019 - 2022")],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.EXPERIENCE]] == [
        "Engineer, Example Corp, 2019 - 2022"
    ]


def test_degree_keyword_without_heading_falls_back_to_education():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[_block("Bachelor of Science, Sample State University")],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.EDUCATION]] == [
        "Bachelor of Science, Sample State University"
    ]


def test_comma_list_without_heading_falls_back_to_skills():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[_block("Python, SQL, Docker, Git, Terraform")],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.SKILLS]] == [
        "Python, SQL, Docker, Git, Terraform"
    ]


def test_unrecognizable_content_goes_to_unclassified_not_dropped():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("A brief objective statement about career goals and aspirations in general.")
        ],
    )
    seg = segment(doc)
    assert len(seg.sections[ResumeSection.UNCLASSIFIED]) == 1
    total_blocks_in = 1
    total_blocks_out = sum(len(v) for v in seg.sections.values())
    assert total_blocks_out == total_blocks_in


def test_reordered_sections_are_still_correctly_assigned():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Core Competencies", BlockKind.HEADING),
            _block("Python, Go"),
            _block("Employment History", BlockKind.HEADING),
            _block("Engineer, Example Corp"),
            _block("Academic History", BlockKind.HEADING),
            _block("BSc, Sample University"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.SKILLS]] == ["Python, Go"]
    assert [b.text for b in seg.sections[ResumeSection.EXPERIENCE]] == ["Engineer, Example Corp"]
    assert [b.text for b in seg.sections[ResumeSection.EDUCATION]] == ["BSc, Sample University"]


def test_table_cells_are_assigned_by_surrounding_heading():
    doc = ParsedDocument(
        source_filename="r.docx",
        source_format="docx",
        blocks=[
            _block("Skills", BlockKind.HEADING),
            TextBlock(
                text="Python", kind=BlockKind.TABLE_CELL, table_id="t0", row_index=0, col_index=0
            ),
            TextBlock(
                text="Expert", kind=BlockKind.TABLE_CELL, table_id="t0", row_index=0, col_index=1
            ),
        ],
    )
    seg = segment(doc)
    assert {b.text for b in seg.sections[ResumeSection.SKILLS]} == {"Python", "Expert"}


def test_section_headings_are_recorded_for_traceability():
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Experience", BlockKind.HEADING),
            _block("Engineer, Example Corp"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.section_headings[ResumeSection.EXPERIENCE]] == ["Experience"]


def test_empty_document_segments_without_error():
    doc = ParsedDocument(source_filename="empty.pdf", source_format="pdf", blocks=[])
    seg = segment(doc)
    assert all(blocks == [] for blocks in seg.sections.values())


def test_contact_detection_does_not_swallow_later_headingless_content():
    """Regression test: content-detected contact info (email/phone) must
    not permanently latch the segmenter's current section to CONTACT --
    otherwise, in a headingless document, every later block (which relies
    on its own fallback classification) gets incorrectly swept into
    CONTACT instead. Found via testing headingless_resume.pdf."""
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Riley Headingless"),
            _block("riley.headingless@example.com"),
            _block("Backend Engineer, Example Corp, 2020 - Present"),
            _block("Bachelor of Science in Computer Science, Sample State University, 2016"),
            _block("Python, SQL, Docker, Kubernetes, Terraform"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.CONTACT]] == [
        "Riley Headingless",
        "riley.headingless@example.com",
    ]
    assert seg.sections[ResumeSection.EXPERIENCE] != []
    assert seg.sections[ResumeSection.EDUCATION] != []
    assert seg.sections[ResumeSection.SKILLS] != []
    assert seg.sections[ResumeSection.UNCLASSIFIED] == []


def test_standalone_profile_link_line_classified_as_contact():
    """Regression test: a line containing only links (no email/phone on
    that line) must still be routed to CONTACT -- found via validation's
    varied_formats_resume.pdf, where this line was previously lost to
    UNCLASSIFIED entirely."""
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Alex Fixture"),
            _block("alex.fixture@example.com | (555) 987-6543"),
            _block("linkedin.com/in/alexfixture | github.com/alexfixture"),
            _block("Experience", BlockKind.HEADING),
            _block("Engineer, Example Corp, 2020 - Present"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.CONTACT]] == [
        "Alex Fixture",
        "alex.fixture@example.com | (555) 987-6543",
        "linkedin.com/in/alexfixture | github.com/alexfixture",
    ]
    assert seg.sections[ResumeSection.UNCLASSIFIED] == []


def test_standalone_https_url_classified_as_contact():
    """A full https:// URL (the extractor's other supported link form,
    not just a bare linkedin.com-style domain) is also routed to CONTACT."""
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Jamie Example"),
            _block("jamie@example.com"),
            _block("https://jamie-example.dev/portfolio"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.CONTACT]] == [
        "Jamie Example",
        "jamie@example.com",
        "https://jamie-example.dev/portfolio",
    ]


def test_contact_detection_handles_email_phone_and_link_without_latching_state():
    """Regression test: adding URL detection must not change the existing
    email/phone behavior, including the "don't latch current_section"
    contract that keeps a headingless document's later content flowing
    through its own fallback classification (see the sibling test above)."""
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Riley Headingless"),
            _block("riley.headingless@example.com"),
            _block("(555) 111-2222"),
            _block("linkedin.com/in/rileyheadingless"),
            _block("Backend Engineer, Example Corp, 2020 - Present"),
            _block("Python, SQL, Docker"),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.CONTACT]] == [
        "Riley Headingless",
        "riley.headingless@example.com",
        "(555) 111-2222",
        "linkedin.com/in/rileyheadingless",
    ]
    assert seg.sections[ResumeSection.EXPERIENCE] != []
    assert seg.sections[ResumeSection.SKILLS] != []
    assert seg.sections[ResumeSection.UNCLASSIFIED] == []


def test_domain_like_token_in_experience_prose_is_not_misrouted_to_contact():
    """False-positive guard: once an explicit heading has set
    current_section, a domain-like token in ordinary prose (here "acme.io"
    inside a sentence) must NOT be pulled into CONTACT -- the same guard
    that already protects email/phone detection covers URL detection too."""
    doc = ParsedDocument(
        source_filename="r.pdf",
        source_format="pdf",
        blocks=[
            _block("Experience", BlockKind.HEADING),
            _block("Engineer, Example Corp, 2020 - Present"),
            _block("Deployed services to acme.io for production traffic."),
        ],
    )
    seg = segment(doc)
    assert [b.text for b in seg.sections[ResumeSection.EXPERIENCE]] == [
        "Engineer, Example Corp, 2020 - Present",
        "Deployed services to acme.io for production traffic.",
    ]
    assert seg.sections[ResumeSection.CONTACT] == []
