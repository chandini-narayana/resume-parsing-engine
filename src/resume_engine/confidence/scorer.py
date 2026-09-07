"""Confidence scoring.

Turns the qualitative evidence extraction and normalization already
capture (ExtractionEvidence, NormalizationResult) into a bounded,
deterministic 0.0-1.0 score, plus a threshold-based needs_review flag.

THIS IS AN ENGINEERING HEURISTIC, NOT A CALIBRATED CONFIDENCE MODEL.
Every weight below is a documented judgment call, not a value fit to a
labeled validation set -- none exists yet (that calibration is a later
phase's job). The heuristic exists so the pipeline can produce a
consistent, explainable, bounded score today without either fabricating
an arbitrary number per field or leaving every field unscored.

How the score is derived (extraction):
    score = method_base_score[evidence.method]
            * matching_strength_multiplier[evidence.matching_strength]
          - ambiguous_penalty            (if evidence.ambiguous)
          - signals_disagree_penalty     (if not evidence.signals_agree)
          - normalization_not_ready_penalty  (if not evidence.normalization_ready)
    score = clamp(score, 0.0, 1.0)

`method_base_score` reflects how much a given extraction *technique*
should be trusted on its own, from highest to lowest:
    regex (0.95)              -- deterministic pattern match, the
                                  strongest evidence type this pipeline has
    section_heuristic (0.85)  -- a confident rule (keyword list, or taken
                                  directly from its expected section)
    elimination (0.60)        -- the *other* field in a pair matched
                                  confidently; this one was inferred by
                                  process of elimination
    seed_list_match (0.55)    -- a known term, but found outside its
                                  expected section (e.g. a skill mentioned
                                  in Experience prose)
    nlp_ner (0.55)             -- spaCy's NER alone; documented elsewhere
                                  (extraction/nlp_model.py) as unreliable
                                  by itself on short resume fragments
    positional_fallback (0.40) -- no confident signal at all; a guess
                                  based on convention (e.g. "first segment
                                  is usually the title")
    (anything else -> default_method_base_score, 0.50)

`matching_strength_multiplier` scales that base by how precisely the
match was made ("exact" full trust, "weak" scaled down, "fuzzy" -- not
currently produced by any extractor, included for forward-compatibility
-- scaled down less than "weak").

The three penalties are flat, additive deductions for red flags the
evidence itself already reports: `ambiguous` (the extractor said so
explicitly, with a reason), `signals_agree=False` (multiple internal
signals pointed different ways), and `normalization_ready=False` (the
raw text looked too rough to trust downstream matching against it).

How the score is derived (skill normalization -- kept conceptually
distinct from extraction confidence, never blended into one number):
    "exact_alias" -> exact_alias_normalization_score (1.0). Covers both a
        literal canonical-name match and an alias match: the normalizer
        itself does not distinguish between the two (both come from the
        same dictionary lookup and are equally certain), so neither is
        this scorer -- see normalization/normalizer.py.
    "fuzzy"       -> match_score * fuzzy_normalization_discount. The raw
        rapidfuzz ratio is discounted further, since any fuzzy match is
        inherently less certain than an exact/alias hit even at a high
        ratio.
    "unmatched"   -> unmatched_normalization_score (0.0). No taxonomy
        entry was found -- always the lowest possible normalization score,
        and (via the shared review threshold) always flagged for review.

needs_review is a single rule, applied uniformly everywhere a confidence
number exists: `confidence < review_threshold` (or True if confidence is
missing entirely). The threshold is configurable (ConfidenceConfig.
review_threshold, itself sourced from schema.candidate_profile.
DEFAULT_REVIEW_THRESHOLD unless overridden), not hard-coded per field
type -- keeping the rule simple keeps it explainable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from resume_engine.extraction.base import ExtractionEvidence, RawExtraction
from resume_engine.normalization.normalizer import NormalizationResult
from resume_engine.schema.candidate_profile import DEFAULT_REVIEW_THRESHOLD


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ConfidenceConfig:
    """All weights used by HeuristicConfidenceScorer, in one place so the
    whole model can be tuned (or swapped per-deployment) without touching
    scoring logic. Every default here is a documented engineering
    judgment call -- see the module docstring for the reasoning behind
    each -- not a value derived from measurement."""

    review_threshold: float = DEFAULT_REVIEW_THRESHOLD

    method_base_score: dict[str, float] = field(
        default_factory=lambda: {
            "regex": 0.95,
            "section_heuristic": 0.85,
            "elimination": 0.60,
            "seed_list_match": 0.55,
            "nlp_ner": 0.55,
            "positional_fallback": 0.40,
        }
    )
    default_method_base_score: float = 0.50  # any method name not listed above

    matching_strength_multiplier: dict[str, float] = field(
        default_factory=lambda: {
            "exact": 1.0,
            "fuzzy": 0.75,
            "weak": 0.60,
        }
    )
    default_matching_strength_multiplier: float = 0.75

    ambiguous_penalty: float = 0.20
    signals_disagree_penalty: float = 0.15
    normalization_not_ready_penalty: float = 0.05

    exact_alias_normalization_score: float = 1.0
    fuzzy_normalization_discount: float = 0.85  # multiplies NormalizationResult.match_score
    unmatched_normalization_score: float = 0.0


class ConfidenceScorer(ABC):
    """Base interface for scoring one extracted field's confidence.

    `score()` is unchanged from the original interface stub. Two
    additions in this task, both purely additive (nothing previously
    implemented this interface, so nothing breaks):
    - `score_normalization()`: a second, independent score for skill
      normalization results -- deliberately not merged into `score()`,
      since extraction confidence and normalization confidence answer
      different questions ("did we read this correctly" vs. "did we
      match it to the right canonical skill").
    - `needs_review()`: a concrete, non-abstract method every subclass
      gets for free -- the review decision is just "confidence below
      this scorer's threshold", the same rule regardless of how a
      subclass computes the score itself.
    """

    def __init__(self, review_threshold: float = DEFAULT_REVIEW_THRESHOLD) -> None:
        self.review_threshold = review_threshold

    @abstractmethod
    def score(self, extraction: RawExtraction) -> float:
        """Return a confidence score in [0.0, 1.0] for one extracted field."""
        raise NotImplementedError

    @abstractmethod
    def score_normalization(self, result: NormalizationResult) -> float:
        """Return a confidence score in [0.0, 1.0] for one skill
        normalization result. Distinct from `score()` -- see class docstring."""
        raise NotImplementedError

    def needs_review(self, confidence: float | None) -> bool:
        """True if `confidence` is missing entirely, or below this
        scorer's review_threshold. The one rule applied everywhere a
        confidence value exists in the CandidateProfile."""
        if confidence is None:
            return True
        return confidence < self.review_threshold


class HeuristicConfidenceScorer(ConfidenceScorer):
    """The MVP confidence model -- an explainable heuristic over evidence
    already captured during extraction/normalization. NOT a calibrated
    model; see this module's docstring."""

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig()
        super().__init__(review_threshold=self.config.review_threshold)

    def score(self, extraction: RawExtraction) -> float:
        return self._score_evidence(extraction.evidence)

    def score_normalization(self, result: NormalizationResult) -> float:
        cfg = self.config
        if result.match_method == "exact_alias":
            return _clamp(cfg.exact_alias_normalization_score)
        if result.match_method == "fuzzy":
            return _clamp(result.match_score * cfg.fuzzy_normalization_discount)
        return _clamp(cfg.unmatched_normalization_score)

    def _score_evidence(self, evidence: ExtractionEvidence) -> float:
        cfg = self.config
        base = cfg.method_base_score.get(evidence.method, cfg.default_method_base_score)
        strength = cfg.matching_strength_multiplier.get(
            evidence.matching_strength, cfg.default_matching_strength_multiplier
        )
        score = base * strength
        if evidence.ambiguous:
            score -= cfg.ambiguous_penalty
        if not evidence.signals_agree:
            score -= cfg.signals_disagree_penalty
        if not evidence.normalization_ready:
            score -= cfg.normalization_not_ready_penalty
        return _clamp(score)
