"""Education extraction: degree, field of study, and institution.

Layered heuristic approach, similar in spirit to titles_companies but
using degree-phrase patterns instead of a keyword list, because degrees
follow much more rigid phrasing than job titles do:

1. Strip date range/date text.
2. Match a degree phrase against an ordered list of patterns (most
   specific first, e.g. "Bachelor of Science" before bare "BS").
3. If a degree matched and is followed by "in <Field>", capture the field
   of study.
4. Whatever remains after removing the degree (+ field-of-study) phrase is
   treated as institution candidate text, split on commas. A segment
   containing an institution keyword (University, College, Institute,
   School, Academy, Polytechnic) is a confident institution match;
   otherwise spaCy ORG detection on the isolated segment is used as a
   weaker supporting signal (same caveat as titles_companies: the model
   is not reliable by itself on short fragments, so it never solely
   decides).
5. If no degree phrase is found at all, the block is not assumed to be
   about a degree -- only an institution is extracted, and only if a
   segment matches the institution-keyword/NLP signal. Nothing is
   fabricated when neither degree nor institution can be confidently
   identified.
"""

from __future__ import annotations

import re

from resume_engine.extraction.base import ExtractionEvidence, FieldExtractor, RawExtraction
from resume_engine.extraction.dates import strip_date_text
from resume_engine.extraction.nlp_model import find_org_entities
from resume_engine.representation.document import TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument

# Ordered most-specific-first so e.g. "Bachelor of Science" is preferred
# over a bare "bachelor" match within the same text. The "(?!in\b)"
# lookahead stops "Bachelor of Science in Computer Science" from greedily
# swallowing "in" as part of the degree phrase -- found via testing.
_DEGREE_PATTERNS = [
    re.compile(r"\bBachelor'?s?\s+of\s+[A-Za-z]+(?:\s+(?!in\b)[A-Za-z]+)*\b", re.IGNORECASE),
    re.compile(r"\bMaster'?s?\s+of\s+[A-Za-z]+(?:\s+(?!in\b)[A-Za-z]+)*\b", re.IGNORECASE),
    re.compile(r"\bAssociate'?s?\s+(?:degree|of\s+[A-Za-z]+)\b", re.IGNORECASE),
    re.compile(r"\bDoctor\s+of\s+[A-Za-z]+(?:\s+(?!in\b)[A-Za-z]+)*\b", re.IGNORECASE),
    re.compile(r"\bPh\.?\s?D\.?\b", re.IGNORECASE),
    re.compile(r"\bDoctorate\b", re.IGNORECASE),
    re.compile(r"\bMBA\b", re.IGNORECASE),
    re.compile(r"\bB\.?S\.?c?\.?\b(?!\w)", re.IGNORECASE),
    re.compile(r"\bM\.?S\.?c?\.?\b(?!\w)", re.IGNORECASE),
    re.compile(r"\bB\.?A\.?\b(?!\w)", re.IGNORECASE),
    re.compile(r"\bM\.?A\.?\b(?!\w)", re.IGNORECASE),
    re.compile(r"\bDiploma\b", re.IGNORECASE),
]

_FIELD_OF_STUDY_RE = re.compile(r"\bin\s+([A-Z][A-Za-z&\- ]*?)(?=,|$)")

_INSTITUTION_KEYWORDS = ("university", "college", "institute", "school", "academy", "polytechnic")


class EducationExtractor(FieldExtractor):
    def extract(self, segmented: SegmentedDocument) -> list[RawExtraction]:
        results: list[RawExtraction] = []
        for block in segmented.sections.get(ResumeSection.EDUCATION, []):
            results.extend(self._extract_from_block(block))
        return results

    def _extract_from_block(self, block: TextBlock) -> list[RawExtraction]:
        residual = strip_date_text(block.text)
        if not residual:
            return []

        results: list[RawExtraction] = []
        degree_match = self._find_degree(residual)
        remainder = residual

        if degree_match is not None:
            degree_text, span = degree_match
            results.append(self._make("degree", degree_text, block, "regex"))

            after_degree = residual[span[1] :]
            field_match = _FIELD_OF_STUDY_RE.search(after_degree)
            if field_match:
                field_text = field_match.group(1).strip()
                if field_text:
                    results.append(self._make("field_of_study", field_text, block, "regex"))
                remainder = residual[: span[0]] + after_degree[field_match.end() :]
            else:
                remainder = residual[: span[0]] + after_degree

        institution = self._find_institution(remainder)
        if institution is not None:
            text, method, matching_strength, ambiguous = institution
            results.append(
                self._make(
                    "institution",
                    text,
                    block,
                    method,
                    matching_strength=matching_strength,
                    ambiguous=ambiguous,
                    ambiguity_reason="only a weak NLP signal available" if ambiguous else None,
                )
            )

        return results

    @staticmethod
    def _find_degree(text: str) -> tuple[str, tuple[int, int]] | None:
        for pattern in _DEGREE_PATTERNS:
            m = pattern.search(text)
            if m:
                return m.group().strip(), m.span()
        return None

    @staticmethod
    def _find_institution(text: str) -> tuple[str, str, str, bool] | None:
        segments = [s.strip() for s in text.split(",") if s.strip()]
        for segment in segments:
            if any(kw in segment.lower() for kw in _INSTITUTION_KEYWORDS):
                return segment, "section_heuristic", "exact", False
        for segment in segments:
            if find_org_entities(segment):
                return segment, "nlp_ner", "weak", True
        return None

    @staticmethod
    def _make(
        field_name: str,
        value: str,
        block: TextBlock,
        method: str,
        matching_strength: str = "exact",
        ambiguous: bool = False,
        ambiguity_reason: str | None = None,
    ) -> RawExtraction:
        return RawExtraction(
            field_name=field_name,
            value=value,
            source_blocks=[block],
            evidence=ExtractionEvidence(
                method=method,
                section=ResumeSection.EDUCATION,
                matching_strength=matching_strength,
                signals_agree=not ambiguous,
                ambiguous=ambiguous,
                ambiguity_reason=ambiguity_reason,
            ),
        )
