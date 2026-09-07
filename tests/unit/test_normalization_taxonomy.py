import json

import pytest

from resume_engine.normalization.taxonomy import (
    DEFAULT_TAXONOMY_PATH,
    TaxonomyEntry,
    TaxonomyLoadError,
    load_taxonomy,
)


def test_loads_default_taxonomy():
    entries = load_taxonomy()
    assert len(entries) > 50
    assert any(e.canonical_name == "Python" for e in entries)


def test_default_taxonomy_path_points_at_real_file():
    assert DEFAULT_TAXONOMY_PATH.exists()


def test_missing_file_raises_taxonomy_load_error(tmp_path):
    with pytest.raises(TaxonomyLoadError):
        load_taxonomy(tmp_path / "does_not_exist.json")


def test_malformed_json_raises_taxonomy_load_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    with pytest.raises(TaxonomyLoadError):
        load_taxonomy(path)


def test_missing_entries_key_raises_taxonomy_load_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not_entries": []}))
    with pytest.raises(TaxonomyLoadError):
        load_taxonomy(path)


def test_malformed_entry_missing_canonical_name_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"entries": [{"aliases": ["X"]}]}))
    with pytest.raises(TaxonomyLoadError):
        load_taxonomy(path)


def test_entry_without_aliases_or_category_defaults_correctly(tmp_path):
    path = tmp_path / "minimal.json"
    path.write_text(json.dumps({"entries": [{"canonical_name": "Widget"}]}))
    entries = load_taxonomy(path)
    assert entries == [TaxonomyEntry(canonical_name="Widget", aliases=(), category=None)]


# --- data-quality checks on the real curated taxonomy ---


def test_no_duplicate_canonical_names():
    entries = load_taxonomy()
    names = [e.canonical_name for e in entries]
    assert len(names) == len(set(names))


def test_no_normalized_key_collisions_across_different_entries():
    """Regression test: an earlier normalization scheme stripped ALL
    punctuation, collapsing 'C++' and 'C#' to the same lookup key ('c'),
    which would silently shadow one entry in the exact-match index."""
    from resume_engine.normalization.normalizer import _normalize_key

    entries = load_taxonomy()
    key_to_canonical: dict[str, str] = {}
    collisions = []
    for entry in entries:
        for name in (entry.canonical_name, *entry.aliases):
            key = _normalize_key(name)
            if key in key_to_canonical and key_to_canonical[key] != entry.canonical_name:
                collisions.append((key, key_to_canonical[key], entry.canonical_name))
            key_to_canonical[key] = entry.canonical_name
    assert collisions == []
