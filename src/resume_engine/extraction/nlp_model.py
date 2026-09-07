"""Shared spaCy model loading.

Model: en_core_web_sm, spaCy's small pretrained English pipeline.
Version: 3.8.0 (matching spacy>=3.8,<3.9 -- see pyproject.toml/requirements.txt).

Why this model:
- Runs entirely on CPU, no external API call, no network access needed at
  inference time -- satisfies "not dependent on an external paid API" and
  "compatible with CPU/local execution".
- Deterministic given the same input (no sampling), which is what
  "deterministic enough for testing" requires.
- Small (~12MB), fast to load, easy to explain during a technical
  handover: it's a standard, off-the-shelf statistical NER model, not a
  custom-trained one.
- Provides entity types including ORG, PERSON, GPE, DATE, CARDINAL,
  NORP, FAC, LOC, PRODUCT, EVENT, WORK_OF_ART, LAW, LANGUAGE, MONEY,
  PERCENT, ORDINAL, TIME, QUANTITY -- of these, only ORG is used here
  (for company/institution candidate signals).

What post-processing this needs, and why:
en_core_web_sm is a *general-purpose* English NER model trained on news
and web text, not resumes. Ad-hoc testing during this task showed it is
NOT reliable by itself on short resume-style fragments -- for example:
  "Product Manager, Acme Widgets LLC"   -> no entities detected at all
  "VP of Engineering at Northwind Traders" -> no entities detected at all
  "Data Scientist, IBM"                 -> BOTH "Data Scientist" and
                                            "IBM" tagged ORG
  "Software Engineer, Example Corp, 2018 - 2021" -> the whole
                                            "Software Engineer, Example
                                            Corp" span tagged as one ORG
  Skills list "Python, FastAPI, SQL, Docker, Git" -> "SQL" tagged ORG,
                                            "Docker"/"Git" tagged PERSON
Because of this, ORG entities from this model are used only as one
*supporting* signal alongside deterministic keyword/structural heuristics
(see extraction/titles_companies.py and extraction/education.py) -- never
as the sole basis for a job-title, company, or institution extraction.
This module deliberately does not claim the model is sufficient on its
own for resume-specific extraction; it isn't.
"""

from __future__ import annotations

import spacy
from spacy.language import Language

MODEL_NAME = "en_core_web_sm"
MODEL_VERSION = "3.8.0"

_nlp: Language | None = None


def get_nlp() -> Language:
    """Lazily load and cache the spaCy pipeline (loading is not free)."""
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load(MODEL_NAME)
        except OSError as exc:
            raise RuntimeError(
                f"spaCy model '{MODEL_NAME}' is not installed. Install it with: "
                f"python -m spacy download {MODEL_NAME}"
            ) from exc
    return _nlp


def find_org_entities(text: str) -> list[str]:
    """Return the text of every ORG entity spaCy finds in `text`.

    A thin, single-purpose wrapper (rather than exposing the full spaCy
    Doc) so callers depend on "what entities did the model find", not on
    spaCy's API shape -- if the model is swapped out later, only this
    function needs to change.
    """
    if not text.strip():
        return []
    doc = get_nlp()(text)
    return [ent.text for ent in doc.ents if ent.label_ == "ORG"]
