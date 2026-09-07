"""Skill normalization: map an extracted skill string to a taxonomy entry.

Two-tier matching, in priority order:

1. Exact/alias lookup, after aggressive normalization (lowercase, strip
   all non-alphanumeric characters). This makes "Node.js", "NodeJS",
   "Node JS", and "node-js" all resolve to the same lookup key, without
   needing every punctuation variant spelled out as a separate alias.
2. Fuzzy matching via rapidfuzz (token-sort ratio, robust to word-order
   differences like "SQL Server Microsoft" vs "Microsoft SQL Server),
   above a fixed similarity threshold. Skipped entirely for very short
   raw values (<=3 characters) -- fuzzy-scoring short abbreviations
   against each other is noisy (e.g. "AI" can score deceptively close to
   "AWS" purely from shared letters), so short strings must match
   exactly or not at all.

A skill that matches neither tier is returned as unmatched (match_score
0.0, matched_entry None) -- never dropped, and never forced into a wrong
bucket. Matching a raw skill against nothing is itself useful information
for the confidence-scoring stage, not a failure to hide.

The fuzzy threshold (85/100) is a judgment call, not a value derived from
a labeled validation set -- there isn't one yet. It is intentionally
conservative (favors leaving a borderline skill unmatched over silently
merging two different skills).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from resume_engine.normalization.taxonomy import TaxonomyEntry

FUZZY_MATCH_THRESHOLD = 85.0
MIN_LENGTH_FOR_FUZZY_MATCH = 4

_SEPARATOR_RE = re.compile(r"[\s\-_./]+")


def _normalize_key(text: str) -> str:
    """Lowercase and strip separator punctuation only (whitespace, hyphen,
    underscore, dot, slash) -- NOT all punctuation. Stripping every
    non-alphanumeric character was found (via testing) to collapse "C++"
    and "C#" to the same key ("c"), silently shadowing one entry in the
    exact-match index. Symbols like "+" and "#" carry real distinguishing
    meaning for language names and must survive normalization."""
    return _SEPARATOR_RE.sub("", text.lower())


@dataclass
class NormalizationResult:
    raw_value: str
    matched_entry: TaxonomyEntry | None
    match_score: float  # 0.0-1.0, similarity/confidence of the match itself
    match_method: str = "unmatched"  # "exact_alias" | "fuzzy" | "unmatched"


class SkillNormalizer:
    def __init__(self, taxonomy: list[TaxonomyEntry]) -> None:
        self._taxonomy = taxonomy
        self._exact_index: dict[str, TaxonomyEntry] = {}
        self._fuzzy_candidates: list[tuple[str, TaxonomyEntry]] = []

        for entry in taxonomy:
            for name in (entry.canonical_name, *entry.aliases):
                key = _normalize_key(name)
                if key and key not in self._exact_index:
                    self._exact_index[key] = entry
                self._fuzzy_candidates.append((name, entry))

    def normalize(self, raw_skill: str) -> NormalizationResult:
        raw_skill = raw_skill.strip()
        if not raw_skill:
            return NormalizationResult(raw_value=raw_skill, matched_entry=None, match_score=0.0)

        exact = self._exact_index.get(_normalize_key(raw_skill))
        if exact is not None:
            return NormalizationResult(
                raw_value=raw_skill,
                matched_entry=exact,
                match_score=1.0,
                match_method="exact_alias",
            )

        if len(raw_skill) < MIN_LENGTH_FOR_FUZZY_MATCH or not self._fuzzy_candidates:
            return NormalizationResult(raw_value=raw_skill, matched_entry=None, match_score=0.0)

        names = [name for name, _entry in self._fuzzy_candidates]
        best = process.extractOne(raw_skill, names, scorer=fuzz.token_sort_ratio)
        if best is None:
            return NormalizationResult(raw_value=raw_skill, matched_entry=None, match_score=0.0)

        _matched_name, score, index = best
        if score < FUZZY_MATCH_THRESHOLD:
            return NormalizationResult(raw_value=raw_skill, matched_entry=None, match_score=0.0)

        return NormalizationResult(
            raw_value=raw_skill,
            matched_entry=self._fuzzy_candidates[index][1],
            match_score=score / 100.0,
            match_method="fuzzy",
        )
