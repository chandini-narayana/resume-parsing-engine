"""Shared helper for constructing SegmentedDocument fixtures in extraction
tests without needing a real parsed file."""

from __future__ import annotations

from resume_engine.representation.document import BlockKind, TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument


def make_segmented(**section_texts: list[str]) -> SegmentedDocument:
    """make_segmented(contact=["Jamie Example"], experience=["Engineer, Acme, 2020 - Present"])

    Keys are ResumeSection names (lowercase); any section not passed
    defaults to an empty list, matching what segment() always produces.
    """
    sections: dict[ResumeSection, list[TextBlock]] = {s: [] for s in ResumeSection}
    counter = 0
    for key, texts in section_texts.items():
        section = ResumeSection(key)
        blocks = []
        for text in texts:
            blocks.append(
                TextBlock(text=text, kind=BlockKind.PARAGRAPH, block_id=f"b{counter:04d}")
            )
            counter += 1
        sections[section] = blocks
    return SegmentedDocument(source_filename="test.pdf", sections=sections)


def table_block(text: str, table_id: str, row: int, col: int) -> TextBlock:
    return TextBlock(
        text=text, kind=BlockKind.TABLE_CELL, table_id=table_id, row_index=row, col_index=col
    )
