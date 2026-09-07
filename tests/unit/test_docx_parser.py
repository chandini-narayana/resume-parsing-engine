from resume_engine.parsing.base import DocxParsingError
from resume_engine.parsing.docx_parser import DocxResumeParser
from resume_engine.representation.document import BlockKind
from tests.fixtures_path import FIXTURES_DIR


def test_parses_normal_resume_text_and_headings():
    doc = DocxResumeParser().parse(FIXTURES_DIR / "normal_resume.docx")
    assert doc.parser_warnings == []
    texts = [b.text for b in doc.blocks]
    assert "Experience" in texts
    assert "Education" in texts
    assert "Skills" in texts
    heading_blocks = [b for b in doc.blocks if b.kind == BlockKind.HEADING]
    assert any(b.text == "Experience" for b in heading_blocks)


def test_docx_blocks_have_no_page_number_by_design():
    doc = DocxResumeParser().parse(FIXTURES_DIR / "normal_resume.docx")
    assert all(b.page_number is None for b in doc.blocks)


def test_blocks_get_stable_sequential_block_ids():
    doc = DocxResumeParser().parse(FIXTURES_DIR / "normal_resume.docx")
    ids = [b.block_id for b in doc.blocks]
    assert ids == [f"b{i:04d}" for i in range(len(doc.blocks))]


def test_table_content_extracted_in_true_document_order():
    doc = DocxResumeParser().parse(FIXTURES_DIR / "table_resume.docx")
    texts = [b.text for b in doc.blocks]
    # "Skills" heading appears before the table cells, and "Education"
    # heading appears after them -- proving paragraphs+tables are walked
    # in real document order, not "all paragraphs then all tables".
    assert texts.index("Skills") < texts.index("Skill")
    assert texts.index("Skill") < texts.index("Education")


def test_table_cells_have_row_and_col_info():
    doc = DocxResumeParser().parse(FIXTURES_DIR / "table_resume.docx")
    table_cells = [b for b in doc.blocks if b.kind == BlockKind.TABLE_CELL]
    assert len(table_cells) == 8  # header row + 3 data rows, 2 cols each
    assert all(c.table_id == table_cells[0].table_id for c in table_cells)
    header_row = [c for c in table_cells if c.row_index == 0]
    assert {c.text for c in header_row} == {"Skill", "Level"}


def test_empty_docx_returns_no_blocks_with_warning():
    doc = DocxResumeParser().parse(FIXTURES_DIR / "empty_resume.docx")
    assert doc.blocks == []
    assert len(doc.parser_warnings) == 1
    assert "no extractable" in doc.parser_warnings[0].lower()


def test_corrupt_docx_raises_parsing_error_not_silent_failure():
    try:
        DocxResumeParser().parse(FIXTURES_DIR / "corrupt.docx")
        raised = False
    except DocxParsingError:
        raised = True
    assert raised
