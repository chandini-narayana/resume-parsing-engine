"""Structured candidate profile schema.

This is the data contract produced by the pipeline (orchestrator +
assembly) and consumed by the API, review UI, and downstream ATS
ingestion.

Adapted from the original foundation-task stub based on what extraction,
normalization, and (now) confidence scoring actually produce -- not a
redesign, an extension:
- Every extracted value's `ScoredField` now carries `Provenance` (section,
  source block IDs, page numbers where available, original text) and an
  `ExtractionEvidenceSummary` mirroring extraction's ExtractionEvidence,
  so the review UI can trace any field back to exactly what produced it.
- `confidence`/`needs_review` are OPTIONAL (`None` = no scorer ran).
  `HeuristicConfidenceScorer` (confidence/scorer.py) now populates these
  by default via pipeline/assembly.py -- an explainable heuristic over
  captured evidence, explicitly NOT a calibrated model (see that
  module's docstring). `None` still means "not scored," never "zero
  confidence" -- kept optional rather than required so a caller that
  doesn't run a scorer isn't forced to fabricate a number.
- `SkillEntry` now holds one or more `SkillMention`s (every raw
  occurrence that normalized to the same canonical skill) plus
  normalization evidence, instead of a single raw_text/canonical_name
  pair -- see pipeline/assembly.py's module docstring for the
  deduplication policy this supports. Each `SkillMention` carries its own
  extraction `confidence`/`needs_review`; `SkillEntry` separately carries
  `normalization_confidence`/`needs_review` -- the two are deliberately
  never blended into one number (see confidence/scorer.py).
- `ExperienceEntry`/`EducationEntry` gained entry-level `provenance` and
  (for experience) `is_current`, for the same traceability reason.
- `ContactInfo` gained `links` (plural) for URLs, since extraction can
  find more than one (LinkedIn, GitHub, portfolio, ...).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

# Fields with a confidence BELOW this score are flagged for recruiter
# review (ScoredField.needs_review / SkillEntry.needs_review /
# SkillMention.needs_review) -- see ConfidenceScorer.needs_review().
# confidence.scorer.ConfidenceConfig imports this as its own default, so
# schema and scorer never drift apart -- this is the single place the
# value is defined. An engineering judgment call, not a value derived
# from a labeled validation set (no calibration exists yet -- see
# confidence/scorer.py's module docstring).
DEFAULT_REVIEW_THRESHOLD = 0.6


class Provenance(BaseModel):
    """Traceability back to the exact parsed content a value came from."""

    section: str | None = None
    block_ids: list[str] = Field(default_factory=list)
    page_numbers: list[int | None] = Field(
        default_factory=list,
        description="One entry per source block, in the same order as block_ids. "
        "None means the format doesn't carry page info (e.g. DOCX) -- never fabricated.",
    )
    original_text: list[str] = Field(default_factory=list)


class ExtractionEvidenceSummary(BaseModel):
    """Pydantic mirror of extraction.base.ExtractionEvidence.

    A separate model (rather than importing the extraction module's
    dataclass directly) so this schema doesn't depend on extraction's
    internal types -- consistent with keeping pipeline stages decoupled.
    """

    method: str
    section: str | None = None
    matching_strength: str = "exact"
    signals_agree: bool = True
    ambiguous: bool = False
    ambiguity_reason: str | None = None
    normalization_ready: bool = True
    notes: str | None = None


class NormalizationEvidence(BaseModel):
    """Evidence from skill normalization -- NOT a calibrated confidence
    value. `match_score` is a string-similarity score (1.0 for an exact/
    alias hit, else the fuzzy-match ratio); it says how closely the raw
    text matched the taxonomy entry, not how likely the extraction itself
    is correct."""

    method: str  # "exact_alias" | "fuzzy" | "unmatched"
    match_score: float = Field(ge=0.0, le=1.0)


class ScoredField(BaseModel, Generic[T]):
    """A single extracted value plus its (pending) confidence/review
    status, provenance, and extraction evidence."""

    value: T
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_review: bool | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    extraction_evidence: ExtractionEvidenceSummary | None = None


class ContactInfo(BaseModel):
    full_name: ScoredField[str] | None = None
    email: ScoredField[str] | None = None
    phone: ScoredField[str] | None = None
    location: ScoredField[str] | None = (
        None  # not currently extracted; stays None rather than fabricated
    )
    links: list[ScoredField[str]] = Field(default_factory=list)


class SkillMention(BaseModel):
    """One raw occurrence of a skill phrase in the source document."""

    raw_text: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_review: bool | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    extraction_evidence: ExtractionEvidenceSummary | None = None


class SkillEntry(BaseModel):
    """One distinct skill. `mentions` holds every raw occurrence that
    normalized here (see pipeline/assembly.py for the dedup policy) --
    always at least one.

    `normalization_confidence` ("did we match this to the right canonical
    skill") is deliberately kept separate from each mention's own
    `confidence` ("did we read this text correctly") -- see
    confidence/scorer.py's module docstring. `needs_review` here is
    entry-level: true if normalization was weak OR the best-read mention
    was weak.
    """

    canonical_name: str | None = None  # None if normalization found no match
    mentions: list[SkillMention] = Field(default_factory=list)
    normalization_evidence: NormalizationEvidence | None = None
    normalization_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_review: bool | None = None


class ExperienceEntry(BaseModel):
    job_title: ScoredField[str] | None = None
    company: ScoredField[str] | None = None
    start_date: ScoredField[str] | None = None
    end_date: ScoredField[str] | None = None
    is_current: bool = False
    provenance: Provenance = Field(default_factory=Provenance)


class EducationEntry(BaseModel):
    institution: ScoredField[str] | None = None
    degree: ScoredField[str] | None = None
    field_of_study: ScoredField[str] | None = None
    graduation_date: ScoredField[str] | None = None
    provenance: Provenance = Field(default_factory=Provenance)


class CandidateProfile(BaseModel):
    """Top-level structured output for one successfully-processed resume."""

    source_filename: str
    contact: ContactInfo = Field(default_factory=ContactInfo)
    skills: list[SkillEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    parser_warnings: list[str] = Field(default_factory=list)
    unclassified_text: list[str] = Field(
        default_factory=list,
        description="Blocks segmentation could not confidently assign to a "
        "section, kept here instead of being silently dropped.",
    )

    def low_confidence_fields(self) -> list[str]:
        """Placeholder for a field-name-list traversal helper.

        Confidence and needs_review ARE now populated throughout this
        profile (see confidence/scorer.py + pipeline/assembly.py) -- a
        caller can already check any field's `.needs_review` directly.
        This method would aggregate those into one flat list of field
        names/paths, which is a convenience for whatever consumes it
        (an API endpoint or the review UI) rather than something the
        confidence-scoring stage itself needs -- left unimplemented here
        rather than guessing at that consumer's shape prematurely.
        """
        raise NotImplementedError("Low-confidence field aggregation is not implemented yet.")
