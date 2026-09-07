#!/usr/bin/env python3
"""Reproducible extraction-quality evaluation against a small, hand-labeled
validation set.

Usage (from the repo root):
    python validation/evaluate.py

Reads every validation/ground_truth/*.json file, runs the real pipeline
(ResumeProcessingPipeline, the same one the API uses) against the fixture
it names under tests/fixtures/, compares the result against the
hand-labeled ground truth using the matching rules documented below, and
writes validation/results/metrics.json, validation/results/errors.json,
and prints a summary to stdout. See validation/README.md for the full
methodology, scope, and limitations -- this docstring covers only the
matching rules, since those need to live next to the code that implements
them.

MATCHING RULES (deliberately strict -- no fuzzy matching, to avoid
inflating scores):
- All string comparison is case-insensitive with whitespace collapsed
  and leading/trailing whitespace stripped (`normalize`). No further
  normalization (no punctuation stripping, no date parsing/canonicalizing)
  -- "2021" and "2021 " match, "2021" and "Jan 2021" do not.
- Singular fields (contact.full_name / email / phone): both absent is a
  true negative (not counted). One absent + one present is a single FN or
  FP. Both present but different values is counted as BOTH one FP and one
  FN (standard information-extraction convention: a wrong answer is both
  "the right answer wasn't found" and "a wrong answer was produced").
- Repeatable fields (links, job titles, companies, dates, degrees,
  institutions, raw skill mentions) are matched as a normalized multiset
  (exact string match, order-independent, duplicate-count-aware) via
  greedy consumption -- NOT positionally tied to a specific experience/
  education entry index, so re-ordered entries (e.g. a two-column layout
  read in a different order) are not penalized. This does mean a title
  extracted correctly but attached to the wrong company within the same
  fixture would not be caught by this evaluation -- see the README's
  Limitations section.
- Skill normalization accuracy is computed ONLY over raw mentions that
  were themselves correctly extracted (true positives) -- normalization
  of a skill the pipeline never found isn't a meaningful question. A
  "correct" mapping is an exact (normalized) match of canonical names,
  including both sides being "unmatched" (None).
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from resume_engine.pipeline.orchestrator import ResumeProcessingPipeline  # noqa: E402
from resume_engine.schema.candidate_profile import CandidateProfile, ScoredField  # noqa: E402

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def normalize(value: str | None) -> str:
    """Case-insensitive, whitespace-collapsed comparison key. `None` and
    `""` both normalize to `""` (used as the "field absent" sentinel)."""
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


# --------------------------------------------------------------------------
# Counting
# --------------------------------------------------------------------------


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: Counts) -> Counts:
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return self.tp / denom if denom else None

    def recall(self) -> float | None:
        denom = self.tp + self.fn
        return self.tp / denom if denom else None

    def f1(self) -> float | None:
        p, r = self.precision(), self.recall()
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    def as_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": self.precision(),
            "recall": self.recall(),
            "f1": self.f1(),
        }


@dataclass
class PredItem:
    value: str
    confidence: float | None
    needs_review: bool | None
    ref: object = None  # extra payload (e.g. the owning SkillEntry), for normalization scoring


@dataclass
class ErrorRecord:
    fixture: str
    field: str
    kind: str  # "false_positive" | "false_negative" | "mismatch" | "normalization"
    expected: object
    predicted: object
    confidence: float | None
    needs_review: bool | None
    reason: str


@dataclass
class ConfidenceSample:
    fixture: str
    field: str
    correct: bool
    confidence: float | None
    needs_review: bool | None


@dataclass
class NormalizationStats:
    correct: int = 0
    total: int = 0

    def accuracy(self) -> float | None:
        return self.correct / self.total if self.total else None


# --------------------------------------------------------------------------
# Known-cause lookup for error reasons
# --------------------------------------------------------------------------
# Filled in from manual inspection of this exact validation set (see
# validation/README.md's Error Analysis section) -- NOT auto-generated, so
# the fallback strings below are a deliberate honesty check: if a future
# fixture/ground-truth change produces an error this table doesn't know
# about, it is reported as "needs manual review", never silently mislabeled.


def infer_reason(
    fixture: str, field_label: str, kind: str, expected: object, predicted: object
) -> str:
    if (
        fixture == "table_resume.pdf"
        and field_label == "contact.full_name"
        and predicted == "Skill"
    ):
        return (
            "The table's header cell 'Skill' is the very first block in a document with "
            "no preceding heading, so the name-shape heuristic (short, capitalized, no "
            "digits) misfires on it. Category: heading detection / table interpretation."
        )
    if (
        fixture == "two_column_resume.pdf"
        and field_label == "experience.companies"
        and predicted == "Built distributed systems."
    ):
        return (
            "The ordinary word 'systems' in this description sentence collides with the "
            "company-suffix keyword list (_COMPANY_SUFFIXES includes 'systems', for names "
            "like 'Acme Systems'), so the whole sentence is misclassified as a confident "
            "company match (section_heuristic, exact, not flagged for review). Category: "
            "job-title/company heuristics -- keyword-list false positive, not an NLP issue."
        )
    if fixture == "varied_formats_resume.pdf" and field_label == "contact.links":
        return (
            "GENUINE GAP surfaced by this validation pass: segmentation's content-based "
            "Contact detection (segmentation/segmenter.py) only checks for an EMAIL_RE or "
            "PHONE_RE match; a line containing only URLs never gets classified into the "
            "Contact section, so ContactInfo.links is unreachable whenever links appear on "
            "their own line rather than sharing a line with an email/phone. Category: "
            "heading/section detection. NOT fixed as part of this validation task -- "
            "reported per instructions, no production code changed."
        )
    if (
        fixture == "varied_formats_resume.pdf"
        and field_label == "education.degrees"
        and (predicted == "M.S" or expected == "M.S.")
    ):
        return (
            "The abbreviated-degree regex (\\bM\\.?S\\.?c?\\.?\\b(?!\\w)) drops the source "
            "text's trailing period ('M.S.' -> 'M.S'), so it's recorded as both a false "
            "positive ('M.S') and a false negative ('M.S.') by the strict string match. "
            "Category: date/degree text-boundary regex quirk, not a wrong degree."
        )
    if (
        fixture == "table_resume.docx"
        and field_label == "skills.raw_mentions"
        and kind == "false_positive"
    ):
        return (
            "Known, already-documented limitation (top-level README Limitations): "
            "Skills-section table header/rating cells ('Skill', 'Level', 'Expert', "
            "'Advanced', 'Intermediate') are taken at face value as skill candidates. "
            "Category: table interpretation / noisy skill candidates."
        )
    if kind == "false_positive":
        return (
            "Predicted a value with no corresponding ground-truth entry -- "
            "unexplained false positive, needs manual review."
        )
    if kind == "false_negative":
        return (
            "Ground-truth value was not extracted at all -- "
            "unexplained false negative, needs manual review."
        )
    if kind == "normalization":
        return "Raw mention normalized to an unexpected canonical skill -- needs manual review."
    return (
        "Predicted value does not match ground truth -- unexplained mismatch, needs manual review."
    )


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


def compare_singular(
    fixture: str,
    field_label: str,
    gt_value: str | None,
    pred_field: ScoredField | None,
    errors: list[ErrorRecord],
    confidence_samples: list[ConfidenceSample],
    counts: Counts,
) -> None:
    gt_norm = normalize(gt_value)
    pred_value = pred_field.value if pred_field is not None else None
    pred_norm = normalize(pred_value)
    confidence = pred_field.confidence if pred_field is not None else None
    needs_review = pred_field.needs_review if pred_field is not None else None

    if gt_norm == "" and pred_norm == "":
        return  # true negative -- not a meaningful data point for P/R/F1

    if gt_norm == pred_norm:
        counts.tp += 1
        confidence_samples.append(
            ConfidenceSample(fixture, field_label, True, confidence, needs_review)
        )
        return

    if gt_norm != "" and pred_norm == "":
        counts.fn += 1
        errors.append(
            ErrorRecord(
                fixture,
                field_label,
                "false_negative",
                gt_value,
                None,
                None,
                None,
                infer_reason(fixture, field_label, "false_negative", gt_value, None),
            )
        )
        return

    if gt_norm == "" and pred_norm != "":
        counts.fp += 1
        errors.append(
            ErrorRecord(
                fixture,
                field_label,
                "false_positive",
                None,
                pred_value,
                confidence,
                needs_review,
                infer_reason(fixture, field_label, "false_positive", None, pred_value),
            )
        )
        confidence_samples.append(
            ConfidenceSample(fixture, field_label, False, confidence, needs_review)
        )
        return

    # Both present, different values: counted as one FP + one FN (see module docstring).
    counts.fp += 1
    counts.fn += 1
    errors.append(
        ErrorRecord(
            fixture,
            field_label,
            "mismatch",
            gt_value,
            pred_value,
            confidence,
            needs_review,
            infer_reason(fixture, field_label, "mismatch", gt_value, pred_value),
        )
    )
    confidence_samples.append(
        ConfidenceSample(fixture, field_label, False, confidence, needs_review)
    )


def compare_multiset(
    fixture: str,
    field_label: str,
    gt_values: list[str],
    pred_items: list[PredItem],
    errors: list[ErrorRecord],
    confidence_samples: list[ConfidenceSample],
    counts: Counts,
) -> list[tuple[str, PredItem]]:
    """Greedy multiset match. Returns the (original_gt_value, matched PredItem)
    pairs, for callers that need to inspect a TP's ground-truth text
    further (e.g. skill normalization scoring)."""
    gt_values = [v for v in gt_values if normalize(v)]
    remaining: Counter[str] = Counter(normalize(v) for v in gt_values)
    originals_by_key: dict[str, list[str]] = defaultdict(list)
    for v in gt_values:
        originals_by_key[normalize(v)].append(v)

    matched_pairs: list[tuple[str, PredItem]] = []
    for item in pred_items:
        key = normalize(item.value)
        if not key:
            continue
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            counts.tp += 1
            original = originals_by_key[key].pop(0)
            matched_pairs.append((original, item))
            confidence_samples.append(
                ConfidenceSample(fixture, field_label, True, item.confidence, item.needs_review)
            )
        else:
            counts.fp += 1
            errors.append(
                ErrorRecord(
                    fixture,
                    field_label,
                    "false_positive",
                    None,
                    item.value,
                    item.confidence,
                    item.needs_review,
                    infer_reason(fixture, field_label, "false_positive", None, item.value),
                )
            )
            confidence_samples.append(
                ConfidenceSample(fixture, field_label, False, item.confidence, item.needs_review)
            )

    for key, leftover_count in remaining.items():
        for _ in range(leftover_count):
            original = originals_by_key[key].pop(0) if originals_by_key[key] else key
            counts.fn += 1
            errors.append(
                ErrorRecord(
                    fixture,
                    field_label,
                    "false_negative",
                    original,
                    None,
                    None,
                    None,
                    infer_reason(fixture, field_label, "false_negative", original, None),
                )
            )

    return matched_pairs


# --------------------------------------------------------------------------
# Per-fixture evaluation
# --------------------------------------------------------------------------


def evaluate_fixture(
    ground_truth: dict,
    pipeline: ResumeProcessingPipeline,
    counts: dict[str, Counts],
    errors: list[ErrorRecord],
    confidence_samples: list[ConfidenceSample],
    norm_stats: NormalizationStats,
) -> dict:
    fixture_name = ground_truth["fixture"]
    fixture_path = FIXTURES_DIR / fixture_name
    result = pipeline.process(fixture_path)
    profile: CandidateProfile = result.profile or CandidateProfile(source_filename=fixture_name)

    def bucket(label: str) -> Counts:
        if label not in counts:
            counts[label] = Counts()
        return counts[label]

    contact = profile.contact
    compare_singular(
        fixture_name,
        "contact.full_name",
        ground_truth["contact"]["full_name"],
        contact.full_name,
        errors,
        confidence_samples,
        bucket("contact.full_name"),
    )
    compare_singular(
        fixture_name,
        "contact.email",
        ground_truth["contact"]["email"],
        contact.email,
        errors,
        confidence_samples,
        bucket("contact.email"),
    )
    compare_singular(
        fixture_name,
        "contact.phone",
        ground_truth["contact"]["phone"],
        contact.phone,
        errors,
        confidence_samples,
        bucket("contact.phone"),
    )

    pred_links = [
        PredItem(link.value, link.confidence, link.needs_review) for link in contact.links
    ]
    compare_multiset(
        fixture_name,
        "contact.links",
        ground_truth["contact"]["links"],
        pred_links,
        errors,
        confidence_samples,
        bucket("contact.links"),
    )

    gt_titles = [e["job_title"] for e in ground_truth["experience"] if e.get("job_title")]
    gt_companies = [e["company"] for e in ground_truth["experience"] if e.get("company")]
    gt_exp_dates = [
        d for e in ground_truth["experience"] for d in (e.get("start_date"), e.get("end_date")) if d
    ]

    pred_titles = [
        PredItem(e.job_title.value, e.job_title.confidence, e.job_title.needs_review)
        for e in profile.experience
        if e.job_title
    ]
    pred_companies = [
        PredItem(e.company.value, e.company.confidence, e.company.needs_review)
        for e in profile.experience
        if e.company
    ]
    pred_exp_dates = []
    for e in profile.experience:
        if e.start_date:
            pred_exp_dates.append(
                PredItem(e.start_date.value, e.start_date.confidence, e.start_date.needs_review)
            )
        if e.end_date:
            pred_exp_dates.append(
                PredItem(e.end_date.value, e.end_date.confidence, e.end_date.needs_review)
            )

    compare_multiset(
        fixture_name,
        "experience.job_titles",
        gt_titles,
        pred_titles,
        errors,
        confidence_samples,
        bucket("experience.job_titles"),
    )
    compare_multiset(
        fixture_name,
        "experience.companies",
        gt_companies,
        pred_companies,
        errors,
        confidence_samples,
        bucket("experience.companies"),
    )
    compare_multiset(
        fixture_name,
        "experience.dates",
        gt_exp_dates,
        pred_exp_dates,
        errors,
        confidence_samples,
        bucket("experience.dates"),
    )

    gt_degrees = [e["degree"] for e in ground_truth["education"] if e.get("degree")]
    gt_institutions = [e["institution"] for e in ground_truth["education"] if e.get("institution")]
    gt_edu_dates = [
        e["graduation_date"] for e in ground_truth["education"] if e.get("graduation_date")
    ]

    pred_degrees = [
        PredItem(e.degree.value, e.degree.confidence, e.degree.needs_review)
        for e in profile.education
        if e.degree
    ]
    pred_institutions = [
        PredItem(e.institution.value, e.institution.confidence, e.institution.needs_review)
        for e in profile.education
        if e.institution
    ]
    pred_edu_dates = [
        PredItem(
            e.graduation_date.value, e.graduation_date.confidence, e.graduation_date.needs_review
        )
        for e in profile.education
        if e.graduation_date
    ]

    compare_multiset(
        fixture_name,
        "education.degrees",
        gt_degrees,
        pred_degrees,
        errors,
        confidence_samples,
        bucket("education.degrees"),
    )
    compare_multiset(
        fixture_name,
        "education.institutions",
        gt_institutions,
        pred_institutions,
        errors,
        confidence_samples,
        bucket("education.institutions"),
    )
    compare_multiset(
        fixture_name,
        "education.dates",
        gt_edu_dates,
        pred_edu_dates,
        errors,
        confidence_samples,
        bucket("education.dates"),
    )

    # --- skills: raw mentions + normalization (scoped to matched raw mentions) ---
    pred_skill_items = [
        PredItem(mention.raw_text, mention.confidence, mention.needs_review, ref=entry)
        for entry in profile.skills
        for mention in entry.mentions
    ]
    gt_raw_skills = [s["raw"] for s in ground_truth["skills"]]
    matched_skill_pairs = compare_multiset(
        fixture_name,
        "skills.raw_mentions",
        gt_raw_skills,
        pred_skill_items,
        errors,
        confidence_samples,
        bucket("skills.raw_mentions"),
    )

    gt_canonical_by_raw = {normalize(s["raw"]): s["canonical"] for s in ground_truth["skills"]}
    for original_raw, item in matched_skill_pairs:
        entry = item.ref
        expected_canonical = gt_canonical_by_raw.get(normalize(original_raw))
        predicted_canonical = entry.canonical_name if entry is not None else None
        is_correct = normalize(expected_canonical) == normalize(predicted_canonical)
        norm_stats.total += 1
        entry_confidence = entry.normalization_confidence if entry is not None else None
        entry_needs_review = entry.needs_review if entry is not None else None
        if is_correct:
            norm_stats.correct += 1
        else:
            errors.append(
                ErrorRecord(
                    fixture_name,
                    "skills.normalization",
                    "normalization",
                    expected_canonical,
                    predicted_canonical,
                    entry_confidence,
                    entry_needs_review,
                    infer_reason(
                        fixture_name,
                        "skills.normalization",
                        "normalization",
                        expected_canonical,
                        predicted_canonical,
                    )
                    + f" (raw mention: '{original_raw}')",
                )
            )
        confidence_samples.append(
            ConfidenceSample(
                fixture_name,
                "skills.normalization",
                is_correct,
                entry_confidence,
                entry_needs_review,
            )
        )

    return {"fixture": fixture_name, "status": result.status}


# --------------------------------------------------------------------------
# Aggregation + reporting
# --------------------------------------------------------------------------

_CONTACT_FIELDS = ["contact.full_name", "contact.email", "contact.phone", "contact.links"]
_EXPERIENCE_FIELDS = ["experience.job_titles", "experience.companies", "experience.dates"]
_EDUCATION_FIELDS = ["education.degrees", "education.institutions", "education.dates"]
_SKILL_FIELDS = ["skills.raw_mentions"]


def sum_counts(counts: dict[str, Counts], labels: list[str]) -> Counts:
    total = Counts()
    for label in labels:
        total = total + counts.get(label, Counts())
    return total


def main() -> None:
    pipeline = ResumeProcessingPipeline()
    counts: dict[str, Counts] = {}
    errors: list[ErrorRecord] = []
    confidence_samples: list[ConfidenceSample] = []
    norm_stats = NormalizationStats()
    fixture_reports = []

    gt_files = sorted(GROUND_TRUTH_DIR.glob("*.json"))
    for gt_file in gt_files:
        ground_truth = json.loads(gt_file.read_text())
        fixture_reports.append(
            evaluate_fixture(ground_truth, pipeline, counts, errors, confidence_samples, norm_stats)
        )

    field_metrics = {label: c.as_dict() for label, c in sorted(counts.items())}

    category_metrics = {
        "contact": sum_counts(counts, _CONTACT_FIELDS).as_dict(),
        "experience": sum_counts(counts, _EXPERIENCE_FIELDS).as_dict(),
        "education": sum_counts(counts, _EDUCATION_FIELDS).as_dict(),
        "skills": sum_counts(counts, _SKILL_FIELDS).as_dict(),
    }

    all_labels = _CONTACT_FIELDS + _EXPERIENCE_FIELDS + _EDUCATION_FIELDS + _SKILL_FIELDS
    overall_micro = sum_counts(counts, all_labels).as_dict()
    category_f1s = [m["f1"] for m in category_metrics.values() if m["f1"] is not None]
    overall_macro_f1 = mean(category_f1s) if category_f1s else None

    correct_samples = [s for s in confidence_samples if s.correct]
    incorrect_samples = [s for s in confidence_samples if not s.correct]
    correct_confidences = [s.confidence for s in correct_samples if s.confidence is not None]
    incorrect_confidences = [s.confidence for s in incorrect_samples if s.confidence is not None]

    confidence_sanity = {
        "sample_size_note": (
            f"{len(confidence_samples)} scored field-level data points across "
            f"{len(gt_files)} fixtures -- small; treat all of the below as directional, "
            "not a statistically powered result. This is a heuristic sanity check, "
            "not a calibration curve, and confidence values here are NOT probabilities."
        ),
        "correct_count": len(correct_samples),
        "incorrect_count": len(incorrect_samples),
        "mean_confidence_correct": mean(correct_confidences) if correct_confidences else None,
        "mean_confidence_incorrect": mean(incorrect_confidences) if incorrect_confidences else None,
        "correct_fields_flagged_needs_review": sum(1 for s in correct_samples if s.needs_review),
        "correct_fields_scored_total": len(correct_samples),
        "incorrect_fields_not_flagged_needs_review": sum(
            1 for s in incorrect_samples if s.needs_review is False
        ),
        "incorrect_fields_scored_total": len(incorrect_samples),
    }

    metrics = {
        "dataset_size": len(gt_files),
        "fixtures": [r["fixture"] for r in fixture_reports],
        "per_field": field_metrics,
        "per_category": category_metrics,
        "overall_micro": overall_micro,
        "overall_macro_f1_across_categories": overall_macro_f1,
        "skill_normalization_accuracy": {
            "correct": norm_stats.correct,
            "total": norm_stats.total,
            "accuracy": norm_stats.accuracy(),
            "scope_note": (
                "Computed only over raw skill mentions that were themselves correctly "
                "extracted (true positives) -- normalization of a never-extracted skill "
                "isn't a meaningful question."
            ),
        },
        "confidence_sanity_check": confidence_sanity,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str) + "\n")
    (RESULTS_DIR / "errors.json").write_text(
        json.dumps([asdict(e) for e in errors], indent=2, default=str) + "\n"
    )

    print(f"Evaluated {len(gt_files)} fixtures.")
    print()
    print("Per-category (precision / recall / F1):")
    for name, m in category_metrics.items():
        prf = f"P={m['precision']!s:>6} R={m['recall']!s:>6} F1={m['f1']!s:>6}"
        counts_str = f"(tp={m['tp']} fp={m['fp']} fn={m['fn']})"
        print(f"  {name:12s} {prf}  {counts_str}")
    print()
    mp, mr, mf = overall_micro["precision"], overall_micro["recall"], overall_micro["f1"]
    print(f"Overall micro: P={mp} R={mr} F1={mf}")
    print(f"Overall macro F1 (mean of 4 category F1s): {overall_macro_f1}")
    print()
    print(
        f"Skill normalization accuracy: {norm_stats.correct}/{norm_stats.total} "
        f"({norm_stats.accuracy()})"
    )
    print()
    print(f"Total errors recorded: {len(errors)} -- see validation/results/errors.json")
    print("Full metrics written to validation/results/metrics.json")


if __name__ == "__main__":
    main()
