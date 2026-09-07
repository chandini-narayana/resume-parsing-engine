"""DOCX parser.

Implementation notes:
- Paragraphs and tables are walked in true document order via the
  `_iter_block_items` recipe below (python-docx does not expose a single
  ordered stream of both itself), so reading order matches how the
  document was actually authored -- not "all paragraphs, then all
  tables."
- Headings are read from the paragraph's Word style ("Heading 1",
  "Heading 2", "Title", ...) rather than guessed from formatting, since
  DOCX carries that information directly and reliably.
- DOCX has no native page concept without rendering the document, so
  TextBlock.page_number is always None here -- a documented limitation,
  not a bug.
- Merged table cells are de-duplicated (python-docx repeats the same
  cell object across the cells it spans), so a merged cell's text is only
  emitted once.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from docx import Document
from docx.document import Document as _DocumentObject
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from resume_engine.parsing.base import DocxParsingError, ResumeParser
from resume_engine.representation.document import BlockKind, ParsedDocument, TextBlock


class DocxResumeParser(ResumeParser):
    supported_extensions = frozenset({".docx"})

    def parse(self, file_path: Path) -> ParsedDocument:
        try:
            document = Document(str(file_path))
        except Exception as exc:  # python-docx raises several exception types for a bad file
            raise DocxParsingError(f"Could not open DOCX '{file_path.name}': {exc}") from exc

        blocks: list[TextBlock] = []
        warnings: list[str] = []
        table_counter = 0

        try:
            block_items = list(_iter_block_items(document))
        except Exception as exc:
            raise DocxParsingError(f"Could not read DOCX body '{file_path.name}': {exc}") from exc

        for item in block_items:
            if isinstance(item, Paragraph):
                text = item.text.strip()
                if not text:
                    continue
                blocks.append(TextBlock(text=text, kind=_paragraph_block_kind(item)))
            else:
                table_id = f"t{table_counter}"
                table_counter += 1
                blocks.extend(_extract_table_blocks(item, table_id))

        if not blocks:
            warnings.append("DOCX contains no extractable text content.")

        for idx, block in enumerate(blocks):
            block.block_id = f"b{idx:04d}"

        return ParsedDocument(
            source_filename=file_path.name,
            source_format="docx",
            blocks=blocks,
            parser_warnings=warnings,
        )


def _paragraph_block_kind(paragraph: Paragraph) -> BlockKind:
    style_name = ((paragraph.style.name if paragraph.style else "") or "").lower()
    if style_name.startswith("heading") or style_name == "title":
        return BlockKind.HEADING
    if "list" in style_name:
        return BlockKind.LIST_ITEM
    return BlockKind.PARAGRAPH


def _extract_table_blocks(table: Table, table_id: str) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    # Holds references to already-seen `_tc` elements so identity checks
    # below are reliable. Using id(cell._tc) directly is unsafe: `_tc` can
    # return a fresh, uncached proxy object per access, and once the
    # previous proxy is garbage-collected Python can reuse its id() for an
    # unrelated cell -- which silently dropped genuinely distinct cells
    # here (found via testing; see test_docx_parser.py regression test).
    seen_tc_elements: list[object] = []
    for row_idx, row in enumerate(table.rows):
        for col_idx, cell in enumerate(row.cells):
            tc = cell._tc
            if any(tc is seen for seen in seen_tc_elements):
                continue  # a merged cell is repeated across the columns it spans
            seen_tc_elements.append(tc)
            text = cell.text.strip()
            if not text:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    kind=BlockKind.TABLE_CELL,
                    table_id=table_id,
                    row_index=row_idx,
                    col_index=col_idx,
                )
            )
    return blocks


def _iter_block_items(parent: _DocumentObject | _Cell) -> Iterator[Paragraph | Table]:
    """Yield each paragraph and table child of `parent` in document order.

    python-docx does not expose this directly; this is the standard
    recipe for it (walking the underlying XML body's children and
    wrapping each in the appropriate python-docx object).
    """
    if isinstance(parent, _DocumentObject):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise TypeError(f"Unsupported parent type for block iteration: {type(parent)!r}")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)
