"""Pipeline orchestration.

Wires ingestion -> parsing -> segmentation -> extraction -> normalization
-> confidence scoring -> CandidateProfile assembly into one
deterministic, synchronous call. Every dependency is injected (parser
registry, extractors, skill normalizer, confidence scorer) rather than
imported concretely by name inside process(), so swapping any stage's
implementation means constructing the ResumeProcessingPipeline
differently, not editing this class.

Deliberately does NOT depend on FastAPI, SQLite, any UI code, a specific
concrete parser class, or a specific NLP implementation -- only on the
interfaces those stages already expose (ParserRegistry, FieldExtractor,
SkillNormalizer, ConfidenceScorer, SegmentedDocument, RawExtraction,
CandidateProfile).

`confidence_scorer` now defaults to `HeuristicConfidenceScorer()` (an
explainable heuristic over captured evidence -- see confidence/scorer.py
for the full model and why it is explicitly NOT a calibrated one) and is
passed into assembly, which populates every ScoredField's
confidence/needs_review. Swap in a different `ConfidenceScorer`
implementation (e.g. a future calibrated model) via the constructor
without touching this class.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from resume_engine.confidence.scorer import ConfidenceScorer, HeuristicConfidenceScorer
from resume_engine.extraction.base import FieldExtractor, RawExtraction
from resume_engine.extraction.extract import extract_candidate
from resume_engine.ingestion.loader import (
    IngestionError,
    build_default_parser_registry,
    load_resume,
)
from resume_engine.normalization.normalizer import SkillNormalizer
from resume_engine.normalization.taxonomy import load_taxonomy
from resume_engine.parsing.base import ParserRegistry
from resume_engine.pipeline.assembly import assemble_profile
from resume_engine.schema.candidate_profile import CandidateProfile
from resume_engine.segmentation.segmenter import segment

logger = logging.getLogger(__name__)


def _default_skill_normalizer() -> SkillNormalizer:
    return SkillNormalizer(load_taxonomy())


@dataclass
class ProcessingResult:
    """Structured outcome of one process() call -- success or failure,
    never a bare exception propagated to the caller."""

    status: str  # "completed" | "failed"
    profile: CandidateProfile | None = None
    error_message: str | None = None  # safe to show a user -- no stack traces/paths/internals


@dataclass
class ResumeProcessingPipeline:
    parser_registry: ParserRegistry = field(default_factory=build_default_parser_registry)
    extractors: list[FieldExtractor] | None = (
        None  # None -> use extraction.extract_candidate's default set
    )
    skill_normalizer: SkillNormalizer = field(default_factory=_default_skill_normalizer)
    confidence_scorer: ConfidenceScorer = field(default_factory=HeuristicConfidenceScorer)

    def process(self, file_path: Path) -> ProcessingResult:
        """Run the full pipeline for one resume file.

        Never raises for expected failure modes (unsupported file type,
        corrupt/unreadable file, or an unexpected error partway through
        segmentation/extraction/normalization/assembly) -- those come
        back as a ProcessingResult(status="failed", error_message=...)
        with a message safe to show the person who uploaded the file.
        The real exception is logged server-side (not returned) so it's
        still debuggable.
        """
        try:
            document = load_resume(file_path, self.parser_registry)
        except IngestionError as exc:
            logger.info("Resume ingestion failed for %s: %s", file_path.name, exc)
            return ProcessingResult(status="failed", error_message=str(exc))

        try:
            segmented = segment(document)
            raw_extractions = self._run_extractors(segmented)
            profile = assemble_profile(
                document,
                segmented,
                raw_extractions,
                self.skill_normalizer,
                self.confidence_scorer,
            )
        except Exception:
            logger.exception("Unexpected error processing resume %s", file_path.name)
            return ProcessingResult(
                status="failed",
                error_message="An unexpected error occurred while processing this resume.",
            )

        return ProcessingResult(status="completed", profile=profile)

    def _run_extractors(self, segmented) -> list[RawExtraction]:  # noqa: ANN001
        if self.extractors is None:
            return extract_candidate(segmented)
        results: list[RawExtraction] = []
        for extractor in self.extractors:
            results.extend(extractor.extract(segmented))
        return results
