"""Unit tests for validation/evaluate.py's matching primitives.

validation/evaluate.py lives outside src/ (it's a standalone validation
script, not part of the shipped package -- see validation/README.md), so
it's loaded here by file path rather than a normal package import.
Importing it does not run the pipeline or load spaCy/the taxonomy --
that only happens inside main(), which these tests never call.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALUATE_PATH = REPO_ROOT / "validation" / "evaluate.py"

_spec = importlib.util.spec_from_file_location("validation_evaluate", EVALUATE_PATH)
assert _spec is not None and _spec.loader is not None
validation_evaluate = importlib.util.module_from_spec(_spec)
sys.modules["validation_evaluate"] = validation_evaluate
_spec.loader.exec_module(validation_evaluate)

Counts = validation_evaluate.Counts
PredItem = validation_evaluate.PredItem
compare_multiset = validation_evaluate.compare_multiset
compare_singular = validation_evaluate.compare_singular
normalize = validation_evaluate.normalize


def test_normalize_collapses_case_and_whitespace():
    assert normalize("  Python   3 ") == "python 3"
    assert normalize(None) == ""
    assert normalize("") == ""


def test_counts_precision_recall_f1_and_zero_division():
    empty = Counts()
    assert empty.precision() is None
    assert empty.recall() is None
    assert empty.f1() is None

    counts = Counts(tp=3, fp=1, fn=1)
    assert counts.precision() == 0.75
    assert counts.recall() == 0.75
    assert counts.f1() == 0.75


def test_counts_addition():
    a = Counts(tp=1, fp=2, fn=3)
    b = Counts(tp=4, fp=5, fn=6)
    total = a + b
    assert (total.tp, total.fp, total.fn) == (5, 7, 9)


def test_compare_singular_both_absent_is_not_counted():
    counts = Counts()
    compare_singular("f.pdf", "contact.phone", None, None, [], [], counts)
    assert (counts.tp, counts.fp, counts.fn) == (0, 0, 0)


def test_compare_singular_true_positive_is_case_and_whitespace_insensitive():
    counts = Counts()
    field = type(
        "F", (), {"value": "  JORDAN@EXAMPLE.com ", "confidence": 0.9, "needs_review": False}
    )()
    compare_singular("f.pdf", "contact.email", "jordan@example.com", field, [], [], counts)
    assert (counts.tp, counts.fp, counts.fn) == (1, 0, 0)


def test_compare_singular_false_negative_when_predicted_missing():
    counts = Counts()
    errors = []
    compare_singular("f.pdf", "contact.email", "jordan@example.com", None, errors, [], counts)
    assert (counts.tp, counts.fp, counts.fn) == (0, 0, 1)
    assert errors[0].kind == "false_negative"


def test_compare_singular_false_positive_when_ground_truth_absent():
    counts = Counts()
    errors = []
    field = type("F", (), {"value": "Skill", "confidence": 0.16, "needs_review": True})()
    compare_singular("f.pdf", "contact.full_name", None, field, errors, [], counts)
    assert (counts.tp, counts.fp, counts.fn) == (0, 1, 0)
    assert errors[0].kind == "false_positive"


def test_compare_singular_mismatch_counts_as_both_fp_and_fn():
    counts = Counts()
    errors = []
    field = type("F", (), {"value": "Wrong Name", "confidence": 0.16, "needs_review": True})()
    compare_singular("f.pdf", "contact.full_name", "Right Name", field, errors, [], counts)
    assert (counts.tp, counts.fp, counts.fn) == (0, 1, 1)
    assert errors[0].kind == "mismatch"


def test_compare_multiset_matches_duplicates_by_count():
    counts = Counts()
    pred = [
        PredItem("Python", 0.9, False),
        PredItem("python", 0.9, False),  # case-insensitive duplicate
        PredItem("SQL", 0.9, False),
    ]
    matched = compare_multiset(
        "f.pdf", "skills.raw_mentions", ["Python", "Python", "SQL"], pred, [], [], counts
    )
    assert (counts.tp, counts.fp, counts.fn) == (3, 0, 0)
    assert len(matched) == 3


def test_compare_multiset_is_order_independent():
    counts_a = Counts()
    counts_b = Counts()
    gt = ["Engineer", "Manager"]
    pred_forward = [PredItem("Engineer", 0.9, False), PredItem("Manager", 0.9, False)]
    pred_reversed = [PredItem("Manager", 0.9, False), PredItem("Engineer", 0.9, False)]
    compare_multiset("f.pdf", "experience.job_titles", gt, pred_forward, [], [], counts_a)
    compare_multiset("f.pdf", "experience.job_titles", gt, pred_reversed, [], [], counts_b)
    assert (
        (counts_a.tp, counts_a.fp, counts_a.fn)
        == (counts_b.tp, counts_b.fp, counts_b.fn)
        == (2, 0, 0)
    )


def test_compare_multiset_reports_unmatched_as_fp_and_fn():
    counts = Counts()
    errors = []
    pred = [PredItem("Skill", 0.85, False)]  # not in ground truth
    compare_multiset("f.pdf", "skills.raw_mentions", ["Python"], pred, errors, [], counts)
    assert (counts.tp, counts.fp, counts.fn) == (0, 1, 1)
    kinds = {e.kind for e in errors}
    assert kinds == {"false_positive", "false_negative"}
