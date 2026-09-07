"""Applies one recruiter correction onto a stored CandidateProfile.

Deliberately NOT a generic path-traversal engine over arbitrary attribute
names -- that would let a client set machine metadata (confidence,
provenance, needs_review, ...) through a text-correction endpoint, or walk
into schema internals the field_path regex shape-check alone can't rule
out. Instead, `_CORRECTABLE_FIELDS` is an explicit, closed whitelist of
every field_path *template* a recruiter may correct, each mapping to
exactly the (container, leaf_key) pair inside the profile's own
`model_dump()` dict it may overwrite. Nothing outside this list is
reachable, so there's no eval/exec, no reflection, and no way to reach
`.confidence`, `.provenance`, `.extraction_evidence`, `is_current`,
`source_filename`, `parser_warnings`, or `unclassified_text` this way.

Confidence / needs_review policy after a correction (documented here since
it's a genuine design decision, not an obvious default):
    - `needs_review` on the corrected object (the ScoredField, SkillEntry,
      or SkillMention whose leaf value changed) is set to False -- a human
      has now confirmed/fixed this field, so it's no longer an unresolved
      machine extraction.
    - `confidence` (or `normalization_confidence`) is left untouched. It's
      preserved as a historical record of the *original* machine read, not
      re-interpreted as "how confident are we in the human's correction"
      (that question doesn't make sense for a human-entered value, and
      fabricating e.g. 1.0 would misrepresent it as a machine score this
      scorer never produced -- see confidence/scorer.py). `needs_review`,
      not `confidence`, is what should now drive whether a field still
      needs attention.
    - `provenance` / `extraction_evidence` / `normalization_evidence` are
      also left untouched -- they document where the *original* text came
      from, which remains true and useful after a correction, not a claim
      about the corrected value.
    - This is applied uniformly per corrected object; correcting one skill
      mention's raw_text does not recompute the parent SkillEntry's
      entry-level needs_review (which may still legitimately reflect a
      different, uncorrected mention or a normalization concern) --
      documented as a known limitation rather than silently cascading a
      guess.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Container = dict[str, Any]
_Resolver = Callable[[dict[str, Any], "re.Match[str]"], tuple[Container, str]]


class CorrectionError(Exception):
    """Raised for any correction that can't be safely applied.

    The message is always safe to return to the client as-is (a 400) --
    never a stack trace or internal detail.
    """


@dataclass(frozen=True)
class AppliedCorrection:
    original_value: str | None
    updated_profile_data: dict[str, Any]


def _require_container(container: Container | None, label: str) -> Container:
    if container is None:
        raise CorrectionError(
            f"'{label}' has no extracted value yet -- correcting a field that was "
            "never extracted isn't supported yet."
        )
    return container


def _list_item(items: list[Any], index_str: str, label: str) -> Container:
    index = int(index_str)
    if index >= len(items):
        raise CorrectionError(f"'{label}' has no entry at index {index}.")
    return items[index]


def _contact_scalar(data: dict[str, Any], match: re.Match[str]) -> tuple[Container, str]:
    name = match.group(1)
    container = _require_container(data["contact"].get(name), f"contact.{name}")
    return container, "value"


def _contact_link(data: dict[str, Any], match: re.Match[str]) -> tuple[Container, str]:
    container = _list_item(data["contact"]["links"], match.group(1), "contact.links")
    return container, "value"


def _skill_canonical_name(data: dict[str, Any], match: re.Match[str]) -> tuple[Container, str]:
    entry = _list_item(data["skills"], match.group(1), "skills")
    return entry, "canonical_name"


def _skill_mention_raw_text(data: dict[str, Any], match: re.Match[str]) -> tuple[Container, str]:
    entry = _list_item(data["skills"], match.group(1), "skills")
    mention = _list_item(entry["mentions"], match.group(2), "skills[].mentions")
    return mention, "raw_text"


def _experience_scalar(data: dict[str, Any], match: re.Match[str]) -> tuple[Container, str]:
    entry = _list_item(data["experience"], match.group(1), "experience")
    name = match.group(2)
    container = _require_container(entry.get(name), f"experience[].{name}")
    return container, "value"


def _education_scalar(data: dict[str, Any], match: re.Match[str]) -> tuple[Container, str]:
    entry = _list_item(data["education"], match.group(1), "education")
    name = match.group(2)
    container = _require_container(entry.get(name), f"education[].{name}")
    return container, "value"


_INDEX = r"(\d+)"

# Every correctable field_path template, most specific pattern first (so
# e.g. the mentions pattern is tried before a hypothetical looser one).
# Each entry is (compiled pattern, resolver). A resolver returns the
# (container dict, leaf key) to overwrite, or raises CorrectionError.
_CORRECTABLE_FIELDS: list[tuple[re.Pattern[str], _Resolver]] = [
    (re.compile(r"^contact\.(full_name|email|phone|location)\.value$"), _contact_scalar),
    (re.compile(rf"^contact\.links\[{_INDEX}\]\.value$"), _contact_link),
    (re.compile(rf"^skills\[{_INDEX}\]\.mentions\[{_INDEX}\]\.raw_text$"), _skill_mention_raw_text),
    (re.compile(rf"^skills\[{_INDEX}\]\.canonical_name$"), _skill_canonical_name),
    (
        re.compile(rf"^experience\[{_INDEX}\]\.(job_title|company|start_date|end_date)\.value$"),
        _experience_scalar,
    ),
    (
        re.compile(
            rf"^education\[{_INDEX}\]\.(institution|degree|field_of_study|graduation_date)\.value$"
        ),
        _education_scalar,
    ),
]


def apply_correction(
    profile_data: dict[str, Any], field_path: str, corrected_value: str
) -> AppliedCorrection:
    """Applies `corrected_value` at `field_path` onto `profile_data` (a
    CandidateProfile's `model_dump(mode="json")`), mutating it in place.

    Raises CorrectionError -- always safe to surface as a 400 -- if
    `field_path` isn't one of the whitelisted correctable templates above,
    resolves to a missing list index, resolves to a field that was never
    extracted (see module docstring), or `corrected_value` is blank.
    Callers are still expected to re-validate the whole profile
    (`CandidateProfile.model_validate`) after this returns, as defense in
    depth against a future schema constraint this function doesn't know
    about.
    """
    if not corrected_value.strip():
        raise CorrectionError("corrected_value cannot be blank.")

    for pattern, resolver in _CORRECTABLE_FIELDS:
        match = pattern.fullmatch(field_path)
        if match is None:
            continue
        container, leaf_key = resolver(profile_data, match)
        original_value = container.get(leaf_key)
        container[leaf_key] = corrected_value
        container["needs_review"] = False
        return AppliedCorrection(original_value=original_value, updated_profile_data=profile_data)

    raise CorrectionError(
        f"'{field_path}' does not refer to a field of the candidate profile that can be corrected."
    )
