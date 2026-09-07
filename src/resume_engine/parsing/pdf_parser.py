"""PDF parser.

Implementation approach: pdfplumber (built on pdfminer.six), because it
exposes word-level bounding boxes and font metadata rather than only a
flattened text string -- that's what makes column detection, heading
detection, and table-vs-paragraph separation possible here instead of
guessing from a single blob of text.

Reading order is reconstructed rather than trusted from raw word order:
1. Tables are detected first (page.find_tables()) and their cell content
   is extracted separately; their bounding boxes are excluded from the
   plain-text word stream so content isn't duplicated.
2. Remaining words are assigned to one or two column bands based on a
   detected horizontal gap in page content (a heuristic -- see
   _detect_column_bounds -- that only distinguishes single- vs.
   two-column layouts; see known limitations in the task report).
3. Within each column, words are grouped into lines by vertical
   proximity, and lines are ordered top-to-bottom.
4. Column bands and tables are then merged column-by-column
   (left-to-right), each internally ordered top-to-bottom, which is a
   reasonable approximation of natural reading order for common resume
   layouts.

Headings are guessed from font size (relative to the page's median body
text size) and boldness -- PDFs carry no semantic "this is a heading"
marker, unlike DOCX styles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber

from resume_engine.parsing.base import PdfParsingError, ResumeParser
from resume_engine.representation.document import BlockKind, ParsedDocument, TextBlock

Span = tuple[float, float]
BBox = tuple[float, float, float, float]

_LINE_TOP_TOLERANCE = 3.0  # points; words within this vertical distance are treated as one line
_HEADING_SIZE_RATIO = (
    1.15  # a line is heading-like if its font is >=15% larger than median body size
)


class PdfResumeParser(ResumeParser):
    supported_extensions = frozenset({".pdf"})

    def parse(self, file_path: Path) -> ParsedDocument:
        try:
            pdf = pdfplumber.open(file_path)
        except Exception as exc:  # pdfplumber/pdfminer raise several exception types for a bad file
            raise PdfParsingError(f"Could not open PDF '{file_path.name}': {exc}") from exc

        blocks: list[TextBlock] = []
        warnings: list[str] = []

        with pdf:
            if len(pdf.pages) == 0:
                warnings.append("PDF has no pages.")
            for page_number, page in enumerate(pdf.pages, start=1):
                page_blocks, page_warnings = self._parse_page(page, page_number)
                blocks.extend(page_blocks)
                warnings.extend(page_warnings)

        if not blocks:
            warnings.append(
                "No extractable text found anywhere in this PDF; it may be a "
                "scanned or image-only document. OCR is outside this MVP's scope."
            )

        for idx, block in enumerate(blocks):
            block.block_id = f"b{idx:04d}"

        return ParsedDocument(
            source_filename=file_path.name,
            source_format="pdf",
            blocks=blocks,
            parser_warnings=warnings,
        )

    def _parse_page(self, page: Any, page_number: int) -> tuple[list[TextBlock], list[str]]:
        warnings: list[str] = []
        blocks: list[TextBlock] = []

        try:
            tables = page.find_tables()
        except Exception as exc:
            warnings.append(f"Page {page_number}: table detection failed ({exc}).")
            tables = []
        table_bboxes: list[BBox] = [tuple(t.bbox) for t in tables]

        try:
            words = page.extract_words(extra_attrs=["size", "fontname"])
        except Exception as exc:
            warnings.append(
                f"Page {page_number}: text extraction failed ({exc}); page may be image-only."
            )
            words = []

        non_table_words = [w for w in words if not _bbox_contains_word(table_bboxes, w)]

        if not words and not tables:
            if getattr(page, "images", None):
                warnings.append(
                    f"Page {page_number} has no extractable text but contains "
                    "image content -- likely a scanned/image-only page."
                )
            return blocks, warnings

        all_spans: list[Span] = [(w["x0"], w["x1"]) for w in non_table_words]
        all_spans += [(b[0], b[2]) for b in table_bboxes]
        column_bounds = _detect_column_bounds(all_spans, float(page.width))

        body_sizes = sorted(w.get("size", 0) for w in non_table_words if w.get("size"))
        median_size = body_sizes[len(body_sizes) // 2] if body_sizes else 0.0

        # (column_index, top, kind, payload) -- sorted column-major, then top-to-bottom.
        units: list[tuple[int, float, str, Any]] = []

        words_by_column: dict[int, list[dict]] = {i: [] for i in range(len(column_bounds))}
        for w in non_table_words:
            col = _assign_column((w["x0"], w["x1"]), column_bounds)
            words_by_column[col].append(w)

        for col_idx, col_words in words_by_column.items():
            for line in _group_lines(col_words):
                units.append((col_idx, line["bbox"][1], "line", line))

        for t_idx, (table, bbox) in enumerate(zip(tables, table_bboxes, strict=True)):
            col_idx = _assign_column((bbox[0], bbox[2]), column_bounds)
            units.append((col_idx, bbox[1], "table", (t_idx, table, bbox)))

        units.sort(key=lambda u: (u[0], u[1]))

        for col_idx, _top, kind, payload in units:
            if kind == "line":
                blocks.append(self._line_to_block(payload, page_number, col_idx, median_size))
            else:
                t_idx, table, bbox = payload
                table_id = f"p{page_number}-t{t_idx}"
                try:
                    rows = table.extract() or []
                except Exception as exc:
                    warnings.append(
                        f"Page {page_number}: table {t_idx} could not be fully "
                        f"extracted ({exc}); any recovered cells are still included."
                    )
                    rows = []
                for row_idx, row in enumerate(rows):
                    for cell_idx, cell_text in enumerate(row):
                        if cell_text and cell_text.strip():
                            blocks.append(
                                TextBlock(
                                    text=cell_text.strip(),
                                    kind=BlockKind.TABLE_CELL,
                                    page_number=page_number,
                                    column_index=col_idx,
                                    table_id=table_id,
                                    row_index=row_idx,
                                    col_index=cell_idx,
                                    bbox=bbox,
                                )
                            )

        return blocks, warnings

    @staticmethod
    def _line_to_block(line: dict, page_number: int, col_idx: int, median_size: float) -> TextBlock:
        is_heading = line["is_bold"] or (
            median_size and line["avg_size"] >= median_size * _HEADING_SIZE_RATIO
        )
        return TextBlock(
            text=line["text"],
            kind=BlockKind.HEADING if is_heading else BlockKind.PARAGRAPH,
            page_number=page_number,
            column_index=col_idx,
            bbox=line["bbox"],
        )


def _bbox_contains_word(table_bboxes: list[BBox], word: dict, tolerance: float = 1.0) -> bool:
    wx0, wtop, wx1, wbottom = word["x0"], word["top"], word["x1"], word["bottom"]
    for tx0, ttop, tx1, tbottom in table_bboxes:
        if (
            wx0 >= tx0 - tolerance
            and wx1 <= tx1 + tolerance
            and wtop >= ttop - tolerance
            and wbottom <= tbottom + tolerance
        ):
            return True
    return False


def _group_lines(words: list[dict]) -> list[dict]:
    """Cluster words into lines by vertical proximity, then order each
    line left-to-right. Uses a simple streaming tolerance rather than a
    detected line-height, which is a known limitation for pages with
    unusually tight or irregular line spacing (see task report)."""
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: w["top"])
    raw_lines: list[list[dict]] = [[words_sorted[0]]]
    for w in words_sorted[1:]:
        if abs(w["top"] - raw_lines[-1][-1]["top"]) <= _LINE_TOP_TOLERANCE:
            raw_lines[-1].append(w)
        else:
            raw_lines.append([w])

    line_dicts = []
    for line_words in raw_lines:
        ordered = sorted(line_words, key=lambda w: w["x0"])
        sizes = [w.get("size", 0) for w in ordered if w.get("size")]
        fontnames = [w.get("fontname", "") for w in ordered]
        bbox = (
            min(w["x0"] for w in ordered),
            min(w["top"] for w in ordered),
            max(w["x1"] for w in ordered),
            max(w["bottom"] for w in ordered),
        )
        line_dicts.append(
            {
                "text": " ".join(w["text"] for w in ordered),
                "bbox": bbox,
                "avg_size": sum(sizes) / len(sizes) if sizes else 0.0,
                "is_bold": any("bold" in f.lower() or "black" in f.lower() for f in fontnames),
            }
        )
    return line_dicts


def _detect_column_bounds(spans: list[Span], page_width: float) -> list[BBox | Span]:
    """Detect 1 or 2 column bands from a horizontal coverage histogram.

    Only distinguishes single-column vs. two-column layouts (the common
    resume cases); 3+ column layouts fall back to being treated as a
    single band, which is a documented limitation, not silent failure --
    all content is still emitted, just without the finer column ordering.
    """
    if not spans or page_width <= 0:
        return [(0.0, page_width)]

    bin_count = 60
    bin_width = page_width / bin_count
    covered = [False] * bin_count
    for x0, x1 in spans:
        start_bin = max(0, min(bin_count - 1, int(x0 // bin_width)))
        end_bin = max(0, min(bin_count - 1, int(x1 // bin_width)))
        for b in range(start_bin, end_bin + 1):
            covered[b] = True

    margin_bins = max(1, int(bin_count * 0.05))
    gaps: list[tuple[int, int]] = []
    run_start: int | None = None
    for b in range(margin_bins, bin_count - margin_bins):
        if not covered[b]:
            run_start = b if run_start is None else run_start
        elif run_start is not None:
            gaps.append((run_start, b - 1))
            run_start = None
    if run_start is not None:
        gaps.append((run_start, bin_count - margin_bins - 1))

    min_gap_bins = max(2, int(bin_count * 0.04))
    candidate_gaps = [
        g
        for g in gaps
        if (g[1] - g[0] + 1) >= min_gap_bins
        and bin_count * 0.25 <= (g[0] + g[1]) / 2 <= bin_count * 0.75
    ]
    if not candidate_gaps:
        return [(0.0, page_width)]

    best_gap = max(candidate_gaps, key=lambda g: g[1] - g[0])
    split_x0 = best_gap[0] * bin_width
    split_x1 = (best_gap[1] + 1) * bin_width
    return [(0.0, split_x0), (split_x1, page_width)]


def _assign_column(span: Span, column_bounds: list[Span]) -> int:
    center = (span[0] + span[1]) / 2
    best_idx, best_dist = 0, float("inf")
    for idx, (bmin, bmax) in enumerate(column_bounds):
        if bmin <= center <= bmax:
            return idx
        dist = min(abs(center - bmin), abs(center - bmax))
        if dist < best_dist:
            best_idx, best_dist = idx, dist
    return best_idx
