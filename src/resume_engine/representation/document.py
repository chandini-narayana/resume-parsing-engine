"""Canonical in-memory representation of a parsed document.

Every format-specific parser (PDF, DOCX, future formats) converts its input
into this common representation. Downstream stages (segmentation,
extraction) work only against this representation, never against a raw
PDF/DOCX object directly. This is what lets a new parser be added later
without touching segmentation or extraction.

Layout information (page/column/table origin) is preserved rather than
collapsed into a flat string, so segmentation can reason about non-standard
layouts (multi-column, tables) instead of receiving text that has already
had structure silently discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BlockKind(StrEnum):
    """What kind of layout element a text block came from."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE_CELL = "table_cell"
    LIST_ITEM = "list_item"
    UNKNOWN = "unknown"


@dataclass
class TextBlock:
    """A single unit of extracted text plus where it came from.

    Keeping provenance (page, column, bounding box, table coordinates)
    attached to each block is what allows the parser to avoid silently
    dropping or reordering content from tables and multi-column layouts.
    """

    text: str
    kind: BlockKind = BlockKind.UNKNOWN
    page_number: int | None = None
    column_index: int | None = None
    table_id: str | None = None
    row_index: int | None = None
    col_index: int | None = None
    bbox: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1
    block_id: str | None = None  # stable identifier assigned by the parser, for traceability


@dataclass
class ParsedDocument:
    """Canonical representation produced by any parser implementation."""

    source_filename: str
    source_format: str  # "pdf" | "docx" | future formats
    blocks: list[TextBlock] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)

    def raw_text(self) -> str:
        """Flattened text view, for cases that don't need block structure."""
        return "\n".join(block.text for block in self.blocks)
