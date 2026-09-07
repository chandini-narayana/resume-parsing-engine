"""Canonical skill taxonomy loading.

Loads the curated JSON taxonomy at data/taxonomy/skills_taxonomy.json
(see scripts/build_skill_taxonomy.py for how it's generated/maintained)
into TaxonomyEntry objects the normalizer indexes for matching.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "taxonomy"
    / "skills_taxonomy.json"
)


@dataclass(frozen=True)
class TaxonomyEntry:
    canonical_name: str
    aliases: tuple[str, ...] = ()
    category: str | None = None


class TaxonomyLoadError(Exception):
    """Raised when the taxonomy file is missing or malformed."""


def load_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> list[TaxonomyEntry]:
    if not path.exists():
        raise TaxonomyLoadError(f"Taxonomy file not found: {path}")

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise TaxonomyLoadError(f"Taxonomy file is not valid JSON: {path}") from exc

    try:
        entries = raw["entries"]
    except (KeyError, TypeError) as exc:
        raise TaxonomyLoadError(f"Taxonomy file missing top-level 'entries' list: {path}") from exc

    result: list[TaxonomyEntry] = []
    for i, item in enumerate(entries):
        try:
            result.append(
                TaxonomyEntry(
                    canonical_name=item["canonical_name"],
                    aliases=tuple(item.get("aliases", [])),
                    category=item.get("category"),
                )
            )
        except (KeyError, TypeError) as exc:
            raise TaxonomyLoadError(f"Malformed taxonomy entry at index {i}: {item!r}") from exc

    return result
