"""Deterministic date and date-range extraction.

Regex-based, not NLP -- resume date formats are structured enough that
rules are more reliable and far easier to test exhaustively than a model
here (per the project brief's preference for deterministic extraction on
fields with a strong structural signal).

The module exposes two things:
1. `find_date_mentions` / `find_date_ranges` / `find_standalone_dates`:
   reusable parsing utilities that other extractors (titles_companies,
   education) use internally to locate and strip date text before
   parsing the remainder of a line.
2. `DatesExtractor`: the FieldExtractor that turns those findings into
   RawExtractions for the Experience and Education sections.

Contextual-evidence note: this only runs against blocks the segmenter has
already placed in Experience or Education. That section membership *is*
the contextual evidence the project brief asks for when it says to avoid
treating ordinary years in arbitrary body text as employment dates --
a bare year is only extracted here because it's inside a section already
identified as Experience/Education, not because any 4-digit number
anywhere looks like a date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from resume_engine.extraction.base import ExtractionEvidence, FieldExtractor, RawExtraction
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument

_MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)

# Ordered by specificity (most specific alternative first) via named groups;
# `m.lastgroup` tells us which alternative actually matched.
_DATE_MENTION_RE = re.compile(
    rf"""
    (?P<month_year>\b(?:{_MONTH_NAMES})\.?\s+\d{{4}}\b) |
    (?P<numeric_month_year>\b(?:0[1-9]|1[0-2])/\d{{4}}\b) |
    (?P<present>\b(?:present|current)\b) |
    (?P<year_only>\b(?:19|20)\d{{2}}\b)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_RANGE_CONNECTOR_RE = re.compile(r"^\s*(-|–|—|to)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DateMention:
    text: str
    span: tuple[int, int]
    precision: str  # "month_year" | "numeric_month_year" | "year_only" | "present"


@dataclass(frozen=True)
class DateRangeMention:
    text: str
    start: DateMention
    end: DateMention
    span: tuple[int, int]


def find_date_mentions(text: str) -> list[DateMention]:
    """All individual date-like mentions in `text`, in reading order."""
    mentions = []
    for m in _DATE_MENTION_RE.finditer(text):
        mentions.append(DateMention(text=m.group(), span=m.span(), precision=m.lastgroup))
    return mentions


def find_date_ranges(text: str) -> list[DateRangeMention]:
    """Pairs of adjacent date mentions connected by a range connector
    (hyphen/en-dash/em-dash/"to"), e.g. "2019 - 2022" or "Jan 2020 to Present"."""
    mentions = find_date_mentions(text)
    ranges: list[DateRangeMention] = []
    used = set()
    for i in range(len(mentions) - 1):
        if i in used:
            continue
        a, b = mentions[i], mentions[i + 1]
        gap = text[a.span[1] : b.span[0]]
        if _RANGE_CONNECTOR_RE.match(gap):
            ranges.append(
                DateRangeMention(
                    text=text[a.span[0] : b.span[1]],
                    start=a,
                    end=b,
                    span=(a.span[0], b.span[1]),
                )
            )
            used.add(i)
            used.add(i + 1)
    return ranges


def find_standalone_dates(text: str) -> list[DateMention]:
    """Date mentions not already consumed by a range, e.g. a lone
    graduation year with no accompanying start date."""
    ranges = find_date_ranges(text)
    consumed_spans = {r.start.span for r in ranges} | {r.end.span for r in ranges}
    return [m for m in find_date_mentions(text) if m.span not in consumed_spans]


def strip_date_text(text: str) -> str:
    """Remove every date range / standalone date mention from `text`,
    collapsing extra whitespace/punctuation left behind. Used by other
    extractors to isolate the non-date portion of an Experience/Education
    line (e.g. the title/company part) before parsing it further."""
    spans_to_remove: list[tuple[int, int]] = [r.span for r in find_date_ranges(text)]
    spans_to_remove += [m.span for m in find_standalone_dates(text)]
    spans_to_remove.sort(key=lambda s: s[0], reverse=True)

    result = text
    for start, end in spans_to_remove:
        result = result[:start] + result[end:]

    result = re.sub(r"[,\s]*[-–—][,\s]*", " ", result)  # leftover bare connectors
    result = re.sub(r"\s*,\s*,\s*", ", ", result)  # doubled-up commas from removal
    result = re.sub(r"\s+", " ", result).strip(" ,")
    return result


class DatesExtractor(FieldExtractor):
    def extract(self, segmented: SegmentedDocument) -> list[RawExtraction]:
        results: list[RawExtraction] = []
        for section in (ResumeSection.EXPERIENCE, ResumeSection.EDUCATION):
            for block in segmented.sections.get(section, []):
                text = block.text
                for r in find_date_ranges(text):
                    results.append(
                        RawExtraction(
                            field_name="date_range",
                            value=r.text,
                            source_blocks=[block],
                            evidence=ExtractionEvidence(
                                method="regex",
                                section=section,
                                matching_strength="exact",
                                signals_agree=True,
                            ),
                        )
                    )
                for m in find_standalone_dates(text):
                    if m.precision == "present":
                        continue  # a bare "present"/"current" with no start date isn't useful alone
                    is_year_only = m.precision == "year_only"
                    results.append(
                        RawExtraction(
                            field_name="date",
                            value=m.text,
                            source_blocks=[block],
                            evidence=ExtractionEvidence(
                                method="regex",
                                section=section,
                                matching_strength="weak" if is_year_only else "exact",
                                signals_agree=True,
                                ambiguous=is_year_only,
                                ambiguity_reason=(
                                    "bare year without month precision or range context"
                                    if is_year_only
                                    else None
                                ),
                            ),
                        )
                    )
        return results
