import pytest

from resume_engine.normalization.normalizer import (
    FUZZY_MATCH_THRESHOLD,
    MIN_LENGTH_FOR_FUZZY_MATCH,
    SkillNormalizer,
)
from resume_engine.normalization.taxonomy import TaxonomyEntry, load_taxonomy


@pytest.fixture(scope="module")
def normalizer():
    return SkillNormalizer(load_taxonomy())


# --- exact / alias matching ---


def test_exact_canonical_name_match(normalizer):
    result = normalizer.normalize("Python")
    assert result.matched_entry.canonical_name == "Python"
    assert result.match_score == 1.0
    assert result.match_method == "exact_alias"


@pytest.mark.parametrize(
    "raw,expected_canonical",
    [
        ("ReactJS", "React"),
        ("React.js", "React"),
        ("react js", "React"),
        ("Postgres", "PostgreSQL"),
        ("node js", "Node.js"),
        ("K8s", "Kubernetes"),
        ("ML", "Machine Learning"),
        ("AI", "Artificial Intelligence"),
        ("NLP", "Natural Language Processing"),
        ("JS", "JavaScript"),
        ("Amazon Web Services", "AWS"),
    ],
)
def test_alias_variants_resolve_to_canonical(normalizer, raw, expected_canonical):
    result = normalizer.normalize(raw)
    assert result.matched_entry is not None, f"expected a match for {raw!r}"
    assert result.matched_entry.canonical_name == expected_canonical
    assert result.match_method == "exact_alias"


def test_matching_is_case_insensitive(normalizer):
    assert normalizer.normalize("python").matched_entry.canonical_name == "Python"
    assert normalizer.normalize("PYTHON").matched_entry.canonical_name == "Python"


def test_matching_is_punctuation_insensitive(normalizer):
    assert normalizer.normalize("Node-JS").matched_entry.canonical_name == "Node.js"


def test_symbol_bearing_languages_do_not_collide():
    """C++ and C# must resolve independently -- see the taxonomy
    collision regression test for how this was found."""
    normalizer = SkillNormalizer(load_taxonomy())
    assert normalizer.normalize("C++").matched_entry.canonical_name == "C++"
    assert normalizer.normalize("C#").matched_entry.canonical_name == "C#"


# --- fuzzy matching ---


def test_typo_resolves_via_fuzzy_match(normalizer):
    result = normalizer.normalize("Pythonn")
    assert result.matched_entry.canonical_name == "Python"
    assert result.match_method == "fuzzy"
    assert 0.0 < result.match_score < 1.0


def test_word_order_variant_resolves_via_fuzzy_match(normalizer):
    result = normalizer.normalize("SQL Server Microsoft")
    assert result.matched_entry.canonical_name == "Microsoft SQL Server"


def test_fuzzy_match_below_threshold_is_unmatched():
    taxonomy = [TaxonomyEntry(canonical_name="Kubernetes")]
    normalizer = SkillNormalizer(taxonomy)
    result = normalizer.normalize("Completely unrelated phrase")
    assert result.matched_entry is None
    assert result.match_score == 0.0
    assert result.match_method == "unmatched"


def test_short_strings_skip_fuzzy_matching_entirely(normalizer):
    """Fuzzy-scoring short abbreviations against each other is noisy
    (e.g. 'AI' vs 'AWS' can score deceptively close on shared letters) --
    below MIN_LENGTH_FOR_FUZZY_MATCH, only an exact hit is accepted."""
    result = normalizer.normalize("Zq")  # 2 chars, not in taxonomy at all
    assert len("Zq") < MIN_LENGTH_FOR_FUZZY_MATCH
    assert result.matched_entry is None
    assert result.match_method == "unmatched"


# --- negative cases: must not fabricate a match ---


@pytest.mark.parametrize(
    "text",
    [
        "communication skills",
        "team player",
        "Acme InternalToolkit",
        "detail oriented",
        "fast learner",
    ],
)
def test_unrelated_or_novel_phrases_are_unmatched_not_forced(normalizer, text):
    result = normalizer.normalize(text)
    assert result.matched_entry is None
    assert result.match_score == 0.0


def test_empty_string_is_unmatched(normalizer):
    result = normalizer.normalize("")
    assert result.matched_entry is None


def test_whitespace_only_is_unmatched(normalizer):
    result = normalizer.normalize("   ")
    assert result.matched_entry is None


def test_raw_value_is_always_preserved(normalizer):
    result = normalizer.normalize("  ReactJS  ")
    assert result.raw_value == "ReactJS"


def test_threshold_is_a_reasonable_conservative_default():
    # Documents the chosen value so a future change is a deliberate edit,
    # not an accidental drift.
    assert FUZZY_MATCH_THRESHOLD == 85.0
