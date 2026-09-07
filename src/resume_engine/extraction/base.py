"""Extractor interface and shared extraction data types.

Each field family (contact, titles/companies, dates, education, skills)
is extracted by a class implementing FieldExtractor. The pipeline depends
only on this interface, so an extractor's internal approach (regex vs.
NLP vs. a future model) can change without touching segmentation,
normalization, confidence scoring, or the orchestrator.

Extractors consume a SegmentedDocument -- not a raw ParsedDocument, not a
specific parser's output, and nothing from the API/persistence layer.
That is what keeps extraction decoupled from FastAPI, SQLite, the
frontend, and any particular parser implementation. Section context is
required input, not optional: several fields (job title vs. company vs.
skill) are only distinguishable *given* which section they were found in
-- this is why the interface changed from accepting `list[TextBlock]` (as
originally stubbed during repository setup, before extraction's real
requirements were known) to accepting the whole SegmentedDocument.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from resume_engine.representation.document import TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument


@dataclass
class ExtractionEvidence:
    """Metadata a later ConfidenceScorer will need.

    Deliberately NOT a confidence score. These are qualitative/structural
    signals an extractor can honestly report about itself right now;
    turning them into a single calibrated number is the confidence-scoring
    stage's job, using a labeled validation set it doesn't have yet. See
    the project brief's "no fake metrics" rule.
    """

    method: str
    # e.g. "regex", "nlp_ner", "section_heuristic", "positional_fallback"
    section: ResumeSection
    matching_strength: str = "exact"  # "exact" | "fuzzy" | "weak"
    signals_agree: bool = True
    # e.g. a keyword heuristic and an NLP entity both pointed the same way
    ambiguous: bool = False
    ambiguity_reason: str | None = None
    normalization_ready: bool = True
    # False if the raw text looks malformed/incomplete for its field type
    notes: str | None = None


@dataclass
class RawExtraction:
    """A single unscored, unnormalized field pulled from a section.

    `value` is always the literal extracted text (or a lightly-joined
    version of it, e.g. a date range like "2021 - Present") -- never an
    invented or inferred value. `source_blocks` is what gives every
    extraction traceability back to the exact TextBlock(s) it came from
    (which themselves carry block_id, page_number, bbox, table position).
    """

    field_name: str
    value: str
    source_blocks: list[TextBlock]
    evidence: ExtractionEvidence


class FieldExtractor(ABC):
    """Base class for extracting one family of fields from a segmented document."""

    @abstractmethod
    def extract(self, segmented: SegmentedDocument) -> list[RawExtraction]:
        raise NotImplementedError
