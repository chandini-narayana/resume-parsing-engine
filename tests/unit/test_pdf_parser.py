from resume_engine.parsing.base import PdfParsingError
from resume_engine.parsing.pdf_parser import PdfResumeParser
from resume_engine.representation.document import BlockKind
from tests.fixtures_path import FIXTURES_DIR


def test_parses_normal_resume_text_and_headings():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "normal_resume.pdf")
    assert doc.parser_warnings == []
    texts = [b.text for b in doc.blocks]
    assert "Experience" in texts
    assert "Education" in texts
    assert "Skills" in texts
    assert any("Jordan Testcase" in t for t in texts)
    heading_blocks = [b for b in doc.blocks if b.kind == BlockKind.HEADING]
    assert any(b.text == "Experience" for b in heading_blocks)


def test_blocks_carry_page_number_and_bbox():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "normal_resume.pdf")
    assert all(b.page_number == 1 for b in doc.blocks)
    assert all(b.bbox is not None for b in doc.blocks)


def test_blocks_get_stable_sequential_block_ids():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "normal_resume.pdf")
    ids = [b.block_id for b in doc.blocks]
    assert ids == [f"b{i:04d}" for i in range(len(doc.blocks))]


def test_table_cells_extracted_with_row_and_col_info():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "table_resume.pdf")
    table_cells = [b for b in doc.blocks if b.kind == BlockKind.TABLE_CELL]
    assert len(table_cells) == 8  # 4 rows x 2 cols
    header_cells = [c for c in table_cells if c.row_index == 0]
    assert {c.text for c in header_cells} == {"Skill", "Level"}
    assert all(c.table_id == table_cells[0].table_id for c in table_cells)


def test_empty_pdf_returns_no_blocks_with_warning():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "empty_resume.pdf")
    assert doc.blocks == []
    assert len(doc.parser_warnings) == 1
    assert (
        "scanned" in doc.parser_warnings[0].lower()
        or "no extractable text" in doc.parser_warnings[0].lower()
    )


def test_scanned_image_pdf_detected_and_warned():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "scanned_image.pdf")
    assert doc.blocks == []
    assert any("image" in w.lower() for w in doc.parser_warnings)


def test_corrupt_pdf_raises_parsing_error_not_silent_failure():
    try:
        PdfResumeParser().parse(FIXTURES_DIR / "corrupt.pdf")
        raised = False
    except PdfParsingError:
        raised = True
    assert raised


def test_two_column_layout_preserves_both_columns():
    doc = PdfResumeParser().parse(FIXTURES_DIR / "two_column_resume.pdf")
    texts = " ".join(b.text for b in doc.blocks)
    # both the left-column (experience) and right-column (skills) content
    # must survive -- neither column may be silently dropped.
    assert "Software Engineer, Example Corp" in texts
    assert "Kubernetes" in texts
    column_indices = {b.column_index for b in doc.blocks if b.column_index is not None}
    assert column_indices == {0, 1}, "expected two distinct columns to be detected"


def test_two_column_layout_groups_each_column_contiguously():
    """Task 5 layout validation: within our column-major ordering, all of
    one column's content should appear before the other column's, rather
    than interleaved line-by-line (which would scramble reading order)."""
    doc = PdfResumeParser().parse(FIXTURES_DIR / "two_column_resume.pdf")
    columns_seen_in_order = [b.column_index for b in doc.blocks if b.column_index is not None]
    # once we leave a column index we should never return to a lower one
    assert columns_seen_in_order == sorted(columns_seen_in_order)
