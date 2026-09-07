import itertools

import pytest

from resume_engine.confidence.scorer import (
    ConfidenceConfig,
    HeuristicConfidenceScorer,
)
from resume_engine.extraction.base import ExtractionEvidence, RawExtraction
from resume_engine.normalization.normalizer import NormalizationResult
from resume_engine.normalization.taxonomy import TaxonomyEntry
from resume_engine.representation.document import BlockKind, TextBlock
from resume_engine.segmentation.segmenter import ResumeSection


def _extraction(method="regex", matching_strength="exact", section=ResumeSection.CONTACT, **kw):
    evidence = ExtractionEvidence(
        method=method, section=section, matching_strength=matching_strength, **kw
    )
    block = TextBlock(text="x", kind=BlockKind.PARAGRAPH, block_id="b0")
    return RawExtraction(field_name="x", value="x", source_blocks=[block], evidence=evidence)


def _norm_result(method, score=1.0):
    entry = TaxonomyEntry(canonical_name="Python") if method != "unmatched" else None
    return NormalizationResult(
        raw_value="x", matched_entry=entry, match_score=score, match_method=method
    )


# --- deterministic high-confidence extraction ---


def test_regex_exact_no_flags_is_high_confidence():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(_extraction(method="regex", matching_strength="exact"))
    assert score >= 0.9
    assert scorer.needs_review(score) is False


def test_email_and_phone_style_extractions_score_identically_given_same_evidence():
    """Both are 'regex'/'exact' with no red flags -- the scorer treats
    them the same way, since it scores evidence, not field identity."""
    scorer = HeuristicConfidenceScorer()
    email_like = scorer.score(_extraction(method="regex", matching_strength="exact"))
    phone_like = scorer.score(_extraction(method="regex", matching_strength="exact"))
    assert email_like == phone_like >= 0.9


# --- medium-confidence extraction ---


def test_section_heuristic_is_medium_high_confidence():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(
        _extraction(
            method="section_heuristic", matching_strength="exact", section=ResumeSection.EXPERIENCE
        )
    )
    assert 0.6 <= score < 0.9
    assert scorer.needs_review(score) is False


def test_elimination_without_ambiguity_flag_would_be_medium():
    """elimination's base score alone (before any ambiguous flag) sits in
    the medium range -- demonstrated directly against the base table."""
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(
        _extraction(
            method="elimination",
            matching_strength="exact",
            section=ResumeSection.EXPERIENCE,
            ambiguous=False,
        )
    )
    assert 0.4 <= score < 0.8


# --- low-confidence extraction ---


def test_positional_fallback_weak_ambiguous_disagree_is_low_confidence():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(
        _extraction(
            method="positional_fallback",
            matching_strength="weak",
            section=ResumeSection.EXPERIENCE,
            ambiguous=True,
            signals_agree=False,
        )
    )
    assert score < 0.3
    assert scorer.needs_review(score) is True


def test_nlp_ner_fallback_is_low_confidence():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(
        _extraction(
            method="nlp_ner",
            matching_strength="weak",
            section=ResumeSection.EDUCATION,
            ambiguous=True,
        )
    )
    assert score < 0.3


# --- ambiguity ---


def test_ambiguous_flag_strictly_reduces_score():
    scorer = HeuristicConfidenceScorer()
    confident = scorer.score(_extraction(method="section_heuristic", ambiguous=False))
    ambiguous = scorer.score(_extraction(method="section_heuristic", ambiguous=True))
    assert ambiguous < confident
    assert confident - ambiguous == pytest.approx(scorer.config.ambiguous_penalty)


# --- conflicting signals ---


def test_signals_disagree_strictly_reduces_score():
    scorer = HeuristicConfidenceScorer()
    agree = scorer.score(_extraction(method="section_heuristic", signals_agree=True))
    disagree = scorer.score(_extraction(method="section_heuristic", signals_agree=False))
    assert disagree < agree
    assert agree - disagree == pytest.approx(scorer.config.signals_disagree_penalty)


def test_normalization_not_ready_reduces_score():
    scorer = HeuristicConfidenceScorer()
    ready = scorer.score(_extraction(method="seed_list_match", normalization_ready=True))
    not_ready = scorer.score(_extraction(method="seed_list_match", normalization_ready=False))
    assert not_ready < ready
    assert ready - not_ready == pytest.approx(scorer.config.normalization_not_ready_penalty)


def test_multiple_red_flags_stack_additively():
    scorer = HeuristicConfidenceScorer()
    baseline = scorer.score(_extraction(method="section_heuristic"))
    all_flags = scorer.score(
        _extraction(
            method="section_heuristic",
            ambiguous=True,
            signals_agree=False,
            normalization_ready=False,
        )
    )
    expected = baseline - (
        scorer.config.ambiguous_penalty
        + scorer.config.signals_disagree_penalty
        + scorer.config.normalization_not_ready_penalty
    )
    assert all_flags == pytest.approx(max(0.0, expected))


# --- skill normalization: exact / alias / fuzzy / unresolved ---


def test_exact_taxonomy_match_is_full_normalization_confidence():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score_normalization(_norm_result("exact_alias", score=1.0))
    assert score == 1.0
    assert scorer.needs_review(score) is False


def test_alias_match_scores_the_same_as_exact_canonical_match():
    """The normalizer itself doesn't distinguish a literal canonical-name
    hit from an alias hit -- both come back as match_method='exact_alias'
    with match_score=1.0, so both score identically here. Documented
    explicitly rather than silently assumed."""
    scorer = HeuristicConfidenceScorer()
    exact_canonical = scorer.score_normalization(_norm_result("exact_alias", score=1.0))
    via_alias = scorer.score_normalization(_norm_result("exact_alias", score=1.0))
    assert exact_canonical == via_alias == 1.0


def test_fuzzy_match_confidence_scales_with_match_score():
    scorer = HeuristicConfidenceScorer()
    high_ratio = scorer.score_normalization(_norm_result("fuzzy", score=0.95))
    low_ratio = scorer.score_normalization(_norm_result("fuzzy", score=0.86))
    assert high_ratio > low_ratio
    assert high_ratio == pytest.approx(0.95 * scorer.config.fuzzy_normalization_discount)


def test_fuzzy_match_is_always_discounted_below_its_raw_ratio():
    scorer = HeuristicConfidenceScorer()
    raw_ratio = 0.90
    score = scorer.score_normalization(_norm_result("fuzzy", score=raw_ratio))
    assert score < raw_ratio


def test_unresolved_skill_normalization_is_zero_and_flagged():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score_normalization(_norm_result("unmatched", score=0.0))
    assert score == 0.0
    assert scorer.needs_review(score) is True


# --- missing evidence ---


def test_unknown_method_falls_back_to_default_base_score_not_a_crash():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(_extraction(method="some_future_method_not_in_the_table"))
    assert 0.0 <= score <= 1.0


def test_unknown_matching_strength_falls_back_to_default_multiplier():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(_extraction(method="regex", matching_strength="some_future_strength"))
    assert 0.0 <= score <= 1.0


def test_needs_review_true_when_confidence_is_none():
    scorer = HeuristicConfidenceScorer()
    assert scorer.needs_review(None) is True


# --- review threshold behavior ---


def test_default_review_threshold_matches_schema_constant():
    from resume_engine.schema.candidate_profile import DEFAULT_REVIEW_THRESHOLD

    scorer = HeuristicConfidenceScorer()
    assert scorer.review_threshold == DEFAULT_REVIEW_THRESHOLD


def test_custom_review_threshold_changes_the_boundary():
    lenient = HeuristicConfidenceScorer(ConfidenceConfig(review_threshold=0.1))
    strict = HeuristicConfidenceScorer(ConfidenceConfig(review_threshold=0.99))

    score = 0.5
    assert lenient.needs_review(score) is False
    assert strict.needs_review(score) is True


def test_score_exactly_at_threshold_is_not_flagged():
    """needs_review uses a strict '<' comparison -- a score exactly equal
    to the threshold is NOT flagged."""
    scorer = HeuristicConfidenceScorer(ConfidenceConfig(review_threshold=0.5))
    assert scorer.needs_review(0.5) is False
    assert scorer.needs_review(0.499999) is True


# --- score bounds ---


def test_score_never_goes_negative_even_with_every_penalty_stacked():
    scorer = HeuristicConfidenceScorer()
    score = scorer.score(
        _extraction(
            method="positional_fallback",
            matching_strength="weak",
            ambiguous=True,
            signals_agree=False,
            normalization_ready=False,
        )
    )
    assert score >= 0.0


def test_score_never_exceeds_one_across_every_method_and_strength_combination():
    scorer = HeuristicConfidenceScorer()
    methods = [*scorer.config.method_base_score.keys(), "unknown_method"]
    strengths = [*scorer.config.matching_strength_multiplier.keys(), "unknown_strength"]
    for method, strength, ambiguous, agree, norm_ready in itertools.product(
        methods, strengths, [True, False], [True, False], [True, False]
    ):
        score = scorer.score(
            _extraction(
                method=method,
                matching_strength=strength,
                ambiguous=ambiguous,
                signals_agree=agree,
                normalization_ready=norm_ready,
            )
        )
        assert 0.0 <= score <= 1.0, f"out of bounds for {method}/{strength}: {score}"


def test_normalization_score_bounds_across_all_methods():
    scorer = HeuristicConfidenceScorer()
    for method, raw_score in [
        ("exact_alias", 1.0),
        ("fuzzy", 0.85),
        ("fuzzy", 1.0),
        ("unmatched", 0.0),
    ]:
        score = scorer.score_normalization(_norm_result(method, score=raw_score))
        assert 0.0 <= score <= 1.0


# --- configurability ---


def test_custom_config_changes_scoring_behavior():
    custom = ConfidenceConfig(method_base_score={"regex": 0.5}, ambiguous_penalty=0.0)
    scorer = HeuristicConfidenceScorer(custom)
    score = scorer.score(_extraction(method="regex", matching_strength="exact", ambiguous=True))
    # ambiguous_penalty=0.0 means the ambiguous flag has no effect under this config
    assert score == pytest.approx(0.5)
