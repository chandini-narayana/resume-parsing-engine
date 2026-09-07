"""CandidateProfile assembly: RawExtractions -> CandidateProfile.

Grouping and deduplication policy (documented here since the task brief
requires it to be explicit):

- Experience/Education entries are grouped by SOURCE BLOCK ID, not by
  company/institution name. Two different roles at the same employer
  (two different blocks) correctly produce two separate entries; if a
  single block ever yielded more than one extraction for the same field
  (not expected from the current extractors, but handled defensively),
  the first one found wins and the rest are not placed elsewhere -- this
  is a within-group tie-break, not a silently dropped extraction
  failure.
- Skills are deduplicated by CANONICAL NAME when normalization matched
  one, so "ML" and "Machine Learning" collapse into a single entry with
  both raw mentions preserved (not two entries for the same skill). An
  UNMATCHED skill is deduplicated only against other occurrences of the
  exact same raw text (case-insensitive) -- two different unmatched
  phrases never merge just because both are unmatched.
- Contact singular fields (name/email/phone) take the first occurrence in
  extraction order (which follows document reading order) if more than
  one is found. URLs are deduplicated by exact value and all kept
  (plural -- a candidate can have more than one relevant link).

Confidence scoring: every ScoredField's `confidence`/`needs_review` is
now populated by a `ConfidenceScorer` (see confidence/scorer.py) --
an explainable heuristic over the evidence extraction already captured,
NOT a calibrated model. `confidence_scorer` defaults to
`HeuristicConfidenceScorer()` if not supplied, so existing callers that
don't pass one still get real (not fabricated-then-hidden) scores.
Skill entries get their own `normalization_confidence`, kept
deliberately separate from mention-level extraction confidence -- see
confidence/scorer.py's module docstring for why the two are never
blended into one number.
"""

from __future__ import annotations

from resume_engine.confidence.scorer import ConfidenceScorer, HeuristicConfidenceScorer
from resume_engine.extraction.base import ExtractionEvidence, RawExtraction
from resume_engine.extraction.dates import find_date_mentions, find_date_ranges
from resume_engine.normalization.normalizer import SkillNormalizer
from resume_engine.representation.document import ParsedDocument, TextBlock
from resume_engine.schema.candidate_profile import (
    CandidateProfile,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    ExtractionEvidenceSummary,
    NormalizationEvidence,
    Provenance,
    ScoredField,
    SkillEntry,
    SkillMention,
)
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument

_EXPERIENCE_FIELDS = {"job_title", "company", "date_range", "date"}
_EDUCATION_FIELDS = {"degree", "field_of_study", "institution", "date_range", "date"}


def assemble_profile(
    document: ParsedDocument,
    segmented: SegmentedDocument,
    raw_extractions: list[RawExtraction],
    skill_normalizer: SkillNormalizer,
    confidence_scorer: ConfidenceScorer | None = None,
) -> CandidateProfile:
    scorer = confidence_scorer or HeuristicConfidenceScorer()
    unclassified_text = [
        block.text
        for block in segmented.sections.get(ResumeSection.UNCLASSIFIED, [])
        if block.text.strip()
    ]
    return CandidateProfile(
        source_filename=document.source_filename,
        contact=_assemble_contact(raw_extractions, scorer),
        skills=_assemble_skills(raw_extractions, skill_normalizer, scorer),
        experience=_assemble_experience(raw_extractions, scorer),
        education=_assemble_education(raw_extractions, scorer),
        parser_warnings=list(document.parser_warnings),
        unclassified_text=unclassified_text,
    )


# --- shared provenance/evidence helpers ---


def _provenance_from_blocks(section: ResumeSection | None, blocks: list[TextBlock]) -> Provenance:
    return Provenance(
        section=section.value if section is not None else None,
        block_ids=[b.block_id for b in blocks if b.block_id is not None],
        page_numbers=[b.page_number for b in blocks],
        original_text=[b.text for b in blocks],
    )


def _provenance_from_extraction(extraction: RawExtraction) -> Provenance:
    return _provenance_from_blocks(extraction.evidence.section, extraction.source_blocks)


def _evidence_summary(evidence: ExtractionEvidence) -> ExtractionEvidenceSummary:
    return ExtractionEvidenceSummary(
        method=evidence.method,
        section=evidence.section.value if evidence.section is not None else None,
        matching_strength=evidence.matching_strength,
        signals_agree=evidence.signals_agree,
        ambiguous=evidence.ambiguous,
        ambiguity_reason=evidence.ambiguity_reason,
        normalization_ready=evidence.normalization_ready,
        notes=evidence.notes,
    )


def _scored_field(
    extraction: RawExtraction, scorer: ConfidenceScorer, value: str | None = None
) -> ScoredField[str]:
    confidence = scorer.score(extraction)
    return ScoredField(
        value=value if value is not None else extraction.value,
        confidence=confidence,
        needs_review=scorer.needs_review(confidence),
        provenance=_provenance_from_extraction(extraction),
        extraction_evidence=_evidence_summary(extraction.evidence),
    )


def _group_by_source_block(
    raw_extractions: list[RawExtraction], section: ResumeSection, relevant_fields: set[str]
) -> tuple[dict[str, list[RawExtraction]], list[str]]:
    """Groups extractions by their first source block's block_id, keeping
    first-seen order stable (which follows document reading order)."""
    groups: dict[str, list[RawExtraction]] = {}
    order: list[str] = []
    for extraction in raw_extractions:
        if extraction.evidence.section != section or extraction.field_name not in relevant_fields:
            continue
        block_id = extraction.source_blocks[0].block_id if extraction.source_blocks else None
        key = block_id if block_id is not None else f"__noblock_{id(extraction)}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(extraction)
    return groups, order


def _first_per_field(group: list[RawExtraction]) -> dict[str, RawExtraction]:
    by_field: dict[str, RawExtraction] = {}
    for extraction in group:
        by_field.setdefault(extraction.field_name, extraction)
    return by_field


def _split_date_range(value: str) -> tuple[str | None, str | None, bool]:
    """Reuses extraction.dates' parsing (not reimplemented) to split a
    date_range/date RawExtraction's flat text back into start/end."""
    ranges = find_date_ranges(value)
    if ranges:
        r = ranges[0]
        is_current = r.end.precision == "present"
        end_text = None if is_current else r.end.text
        return r.start.text, end_text, is_current
    mentions = find_date_mentions(value)
    if mentions:
        return mentions[0].text, None, False
    return None, None, False


# --- contact ---


def _assemble_contact(
    raw_extractions: list[RawExtraction], scorer: ConfidenceScorer
) -> ContactInfo:
    contact = ContactInfo()
    seen_singular: set[str] = set()
    seen_links: set[str] = set()
    links: list[ScoredField[str]] = []

    for extraction in raw_extractions:
        if extraction.evidence.section != ResumeSection.CONTACT:
            continue

        if extraction.field_name == "full_name" and "full_name" not in seen_singular:
            contact.full_name = _scored_field(extraction, scorer)
            seen_singular.add("full_name")
        elif extraction.field_name == "email" and "email" not in seen_singular:
            contact.email = _scored_field(extraction, scorer)
            seen_singular.add("email")
        elif extraction.field_name == "phone" and "phone" not in seen_singular:
            contact.phone = _scored_field(extraction, scorer)
            seen_singular.add("phone")
        elif extraction.field_name == "url":
            key = extraction.value.strip().lower()
            if key not in seen_links:
                seen_links.add(key)
                links.append(_scored_field(extraction, scorer))

    contact.links = links
    return contact


# --- experience ---


def _assemble_experience(
    raw_extractions: list[RawExtraction], scorer: ConfidenceScorer
) -> list[ExperienceEntry]:
    groups, order = _group_by_source_block(
        raw_extractions, ResumeSection.EXPERIENCE, _EXPERIENCE_FIELDS
    )
    return [_build_experience_entry(groups[key], scorer) for key in order]


def _build_experience_entry(
    group: list[RawExtraction], scorer: ConfidenceScorer
) -> ExperienceEntry:
    by_field = _first_per_field(group)
    entry = ExperienceEntry()

    if "job_title" in by_field:
        entry.job_title = _scored_field(by_field["job_title"], scorer)
    if "company" in by_field:
        entry.company = _scored_field(by_field["company"], scorer)

    date_extraction = by_field.get("date_range") or by_field.get("date")
    if date_extraction is not None:
        start_text, end_text, is_current = _split_date_range(date_extraction.value)
        if start_text is not None:
            entry.start_date = _scored_field(date_extraction, scorer, value=start_text)
        if end_text is not None:
            entry.end_date = _scored_field(date_extraction, scorer, value=end_text)
        entry.is_current = is_current

    entry.provenance = _provenance_from_extraction(group[0])
    return entry


# --- education ---


def _assemble_education(
    raw_extractions: list[RawExtraction], scorer: ConfidenceScorer
) -> list[EducationEntry]:
    groups, order = _group_by_source_block(
        raw_extractions, ResumeSection.EDUCATION, _EDUCATION_FIELDS
    )
    return [_build_education_entry(groups[key], scorer) for key in order]


def _build_education_entry(group: list[RawExtraction], scorer: ConfidenceScorer) -> EducationEntry:
    by_field = _first_per_field(group)
    entry = EducationEntry()

    if "institution" in by_field:
        entry.institution = _scored_field(by_field["institution"], scorer)
    if "degree" in by_field:
        entry.degree = _scored_field(by_field["degree"], scorer)
    if "field_of_study" in by_field:
        entry.field_of_study = _scored_field(by_field["field_of_study"], scorer)

    date_extraction = by_field.get("date_range") or by_field.get("date")
    if date_extraction is not None:
        entry.graduation_date = _scored_field(date_extraction, scorer)

    entry.provenance = _provenance_from_extraction(group[0])
    return entry


# --- skills ---


def _assemble_skills(
    raw_extractions: list[RawExtraction], normalizer: SkillNormalizer, scorer: ConfidenceScorer
) -> list[SkillEntry]:
    entries_by_key: dict[str, SkillEntry] = {}
    order: list[str] = []

    for extraction in raw_extractions:
        if extraction.field_name != "skill":
            continue

        result = normalizer.normalize(extraction.value)
        canonical = result.matched_entry.canonical_name if result.matched_entry else None
        key = (
            canonical
            if canonical is not None
            else f"__unmatched::{extraction.value.strip().lower()}"
        )

        # Extraction confidence -- "did we read this text correctly" --
        # scored per mention, same as any other field.
        mention_confidence = scorer.score(extraction)
        mention = SkillMention(
            raw_text=extraction.value,
            confidence=mention_confidence,
            needs_review=scorer.needs_review(mention_confidence),
            provenance=_provenance_from_extraction(extraction),
            extraction_evidence=_evidence_summary(extraction.evidence),
        )

        if key not in entries_by_key:
            # Normalization confidence -- "did we match it to the right
            # canonical skill" -- scored once per entry, kept separate
            # from any mention's extraction confidence (see
            # confidence/scorer.py's module docstring for why).
            normalization_confidence = scorer.score_normalization(result)
            entries_by_key[key] = SkillEntry(
                canonical_name=canonical,
                mentions=[mention],
                normalization_evidence=NormalizationEvidence(
                    method=result.match_method,
                    match_score=result.match_score,
                ),
                normalization_confidence=normalization_confidence,
            )
            order.append(key)
        else:
            entries_by_key[key].mentions.append(mention)

    for entry in entries_by_key.values():
        mention_confidences = [m.confidence for m in entry.mentions if m.confidence is not None]
        best_mention_confidence = max(mention_confidences) if mention_confidences else None
        # A skill needs review if EITHER dimension is weak: normalization
        # found no/only a shaky taxonomy match, or even the best-read
        # mention of it was low-confidence extraction. Either alone is
        # reason enough to flag it.
        entry.needs_review = scorer.needs_review(
            entry.normalization_confidence
        ) or scorer.needs_review(best_mention_confidence)

    return [entries_by_key[key] for key in order]
