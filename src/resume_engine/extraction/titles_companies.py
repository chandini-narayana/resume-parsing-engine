"""Job title and company extraction from the Experience section.

Layered heuristic approach, in priority order:

1. Strip any date range/date from the line (extraction.dates), since
   dates otherwise interfere with comma-splitting.
2. Split the remainder on commas (the dominant resume convention --
   "Title, Company") and on " at " (a second common convention --
   "Title at Company").
3. Classify each resulting segment using, in order of reliability:
   a. A curated job-title keyword list (Engineer, Manager, Director, ...).
   b. A curated company-suffix keyword list (Inc, LLC, Corp, ...).
   c. spaCy ORG detection on the isolated segment, as a weaker supporting
      signal only -- NOT the primary signal. Ad-hoc testing (see
      extraction/nlp_model.py's docstring) showed en_core_web_sm is
      unreliable on short resume fragments by itself: it missed
      "Acme Widgets LLC" and "Northwind Traders" entirely, and it
      false-positived "Data Scientist" as an ORG. Keyword heuristics are
      the primary signal precisely because they're deterministic and
      testable in a way the model's fragment-level behavior isn't.
4. If exactly one segment is confidently classified and the other isn't,
   assign the other by elimination (flagged ambiguous=True, since it
   wasn't independently confirmed).
5. If nothing is confidently classified, fall back to position
   (first segment = title, second = company), flagged ambiguous=True
   with method="positional_fallback" -- lower-confidence but still
   traceable, per "preserve uncertain candidates where appropriate".
6. If a line yields no confident title or company at all (e.g. a single
   unsplittable segment matching neither list), nothing is extracted for
   it -- extraction does not fabricate a value it has no signal for.
"""

from __future__ import annotations

import re

from resume_engine.extraction.base import ExtractionEvidence, FieldExtractor, RawExtraction
from resume_engine.extraction.dates import strip_date_text
from resume_engine.extraction.nlp_model import find_org_entities
from resume_engine.representation.document import TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument

_TITLE_KEYWORDS = (
    "engineer",
    "developer",
    "manager",
    "director",
    "analyst",
    "specialist",
    "consultant",
    "designer",
    "scientist",
    "architect",
    "lead",
    "intern",
    "coordinator",
    "president",
    "officer",
    "executive",
    "administrator",
    "technician",
    "vp",
    "vice president",
    "head",
    "associate",
    "assistant",
    "representative",
    "supervisor",
    "founder",
    "owner",
    "ceo",
    "cto",
    "cfo",
    "coo",
    "recruiter",
    "accountant",
    "strategist",
    "producer",
    "editor",
    "researcher",
)

_COMPANY_SUFFIXES = (
    "inc",
    "inc.",
    "llc",
    "llp",
    "ltd",
    "ltd.",
    "limited",
    "corp",
    "corp.",
    "corporation",
    "co.",
    "company",
    "group",
    "technologies",
    "solutions",
    "systems",
    "partners",
    "associates",
    "industries",
    "enterprises",
    "holdings",
)

_SPLIT_RE = re.compile(r",| at ", re.IGNORECASE)


def _has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", lowered) for kw in keywords)


class TitlesCompaniesExtractor(FieldExtractor):
    def extract(self, segmented: SegmentedDocument) -> list[RawExtraction]:
        results: list[RawExtraction] = []
        for block in segmented.sections.get(ResumeSection.EXPERIENCE, []):
            results.extend(self._extract_from_block(block))
        return results

    def _extract_from_block(self, block: TextBlock) -> list[RawExtraction]:
        residual = strip_date_text(block.text)
        if not residual:
            return []

        segments = [s.strip() for s in _SPLIT_RE.split(residual) if s.strip()]
        if not segments:
            return []

        if len(segments) == 1:
            return self._extract_single_segment(segments[0], block)
        if len(segments) == 2:
            return self._extract_two_segments(segments[0], segments[1], block)
        return self._extract_many_segments(segments, block)

    def _extract_single_segment(self, segment: str, block: TextBlock) -> list[RawExtraction]:
        if _has_keyword(segment, _TITLE_KEYWORDS):
            return [
                self._make(
                    field_name="job_title", value=segment, block=block, method="section_heuristic"
                )
            ]
        if _has_keyword(segment, _COMPANY_SUFFIXES) or find_org_entities(segment):
            return [
                self._make(
                    field_name="company",
                    value=segment,
                    block=block,
                    method="section_heuristic"
                    if _has_keyword(segment, _COMPANY_SUFFIXES)
                    else "nlp_ner",
                    matching_strength="weak"
                    if not _has_keyword(segment, _COMPANY_SUFFIXES)
                    else "exact",
                )
            ]
        return []  # no confident signal either way -- don't fabricate

    def _extract_two_segments(
        self, first: str, second: str, block: TextBlock
    ) -> list[RawExtraction]:
        first_is_title = _has_keyword(first, _TITLE_KEYWORDS)
        second_is_title = _has_keyword(second, _TITLE_KEYWORDS)
        first_is_company = _has_keyword(first, _COMPANY_SUFFIXES) or bool(find_org_entities(first))
        second_is_company = _has_keyword(second, _COMPANY_SUFFIXES) or bool(
            find_org_entities(second)
        )

        results: list[RawExtraction] = []

        if first_is_title and not second_is_title:
            results.append(self._make("job_title", first, block, "section_heuristic"))
            results.append(
                self._make(
                    "company",
                    second,
                    block,
                    "section_heuristic" if second_is_company else "elimination",
                    ambiguous=not second_is_company,
                    ambiguity_reason=None
                    if second_is_company
                    else "assigned by elimination, not independently confirmed",
                )
            )
        elif second_is_title and not first_is_title:
            results.append(self._make("job_title", second, block, "section_heuristic"))
            results.append(
                self._make(
                    "company",
                    first,
                    block,
                    "section_heuristic" if first_is_company else "elimination",
                    ambiguous=not first_is_company,
                    ambiguity_reason=None
                    if first_is_company
                    else "assigned by elimination, not independently confirmed",
                )
            )
        elif first_is_company and not second_is_company:
            results.append(self._make("company", first, block, "section_heuristic"))
            results.append(
                self._make(
                    "job_title",
                    second,
                    block,
                    "elimination",
                    ambiguous=True,
                    ambiguity_reason="assigned by elimination, not independently confirmed",
                )
            )
        elif second_is_company and not first_is_company:
            results.append(self._make("company", second, block, "section_heuristic"))
            results.append(
                self._make(
                    "job_title",
                    first,
                    block,
                    "elimination",
                    ambiguous=True,
                    ambiguity_reason="assigned by elimination, not independently confirmed",
                )
            )
        else:
            # Neither segment gave a confident, non-conflicting signal --
            # fall back to the dominant resume convention (title first),
            # explicitly flagged as low-confidence.
            results.append(
                self._make(
                    "job_title",
                    first,
                    block,
                    "positional_fallback",
                    matching_strength="weak",
                    signals_agree=False,
                    ambiguous=True,
                    ambiguity_reason="no keyword/NLP signal; assumed first-segment-is-title",
                )
            )
            results.append(
                self._make(
                    "company",
                    second,
                    block,
                    "positional_fallback",
                    matching_strength="weak",
                    signals_agree=False,
                    ambiguous=True,
                    ambiguity_reason="no keyword/NLP signal; assumed second-segment-is-company",
                )
            )
        return results

    def _extract_many_segments(self, segments: list[str], block: TextBlock) -> list[RawExtraction]:
        results: list[RawExtraction] = []
        title_segment = next((s for s in segments if _has_keyword(s, _TITLE_KEYWORDS)), None)
        if title_segment is not None:
            results.append(self._make("job_title", title_segment, block, "section_heuristic"))

        company_segment = next(
            (s for s in segments if s != title_segment and _has_keyword(s, _COMPANY_SUFFIXES)),
            None,
        )
        if company_segment is None:
            company_segment = next(
                (s for s in segments if s != title_segment and find_org_entities(s)),
                None,
            )
            if company_segment is not None:
                results.append(
                    self._make(
                        "company",
                        company_segment,
                        block,
                        "nlp_ner",
                        matching_strength="weak",
                        ambiguous=True,
                        ambiguity_reason="more than 2 segments; only weak NLP signal available",
                    )
                )
        else:
            results.append(self._make("company", company_segment, block, "section_heuristic"))

        return results

    @staticmethod
    def _make(
        field_name: str,
        value: str,
        block: TextBlock,
        method: str,
        matching_strength: str = "exact",
        signals_agree: bool = True,
        ambiguous: bool = False,
        ambiguity_reason: str | None = None,
    ) -> RawExtraction:
        return RawExtraction(
            field_name=field_name,
            value=value,
            source_blocks=[block],
            evidence=ExtractionEvidence(
                method=method,
                section=ResumeSection.EXPERIENCE,
                matching_strength=matching_strength,
                signals_agree=signals_agree,
                ambiguous=ambiguous,
                ambiguity_reason=ambiguity_reason,
            ),
        )
