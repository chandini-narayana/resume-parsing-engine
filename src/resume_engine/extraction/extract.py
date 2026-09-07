"""Top-level extraction entry point.

Implements the "SegmentedDocument -> RawExtractions" step from the
project brief: runs every field-family extractor against a
SegmentedDocument and returns the combined, flat list of RawExtractions.
Operates purely on the canonical segmented representation -- no FastAPI,
no SQLite, no specific parser.

Assembling these RawExtractions into a populated CandidateProfile
(matching skills against a taxonomy, computing calibrated confidence
scores) is out of scope for this task -- see pipeline/orchestrator.py for
where that wiring will eventually live.
"""

from __future__ import annotations

from resume_engine.extraction.base import RawExtraction
from resume_engine.extraction.contact import ContactExtractor
from resume_engine.extraction.dates import DatesExtractor
from resume_engine.extraction.education import EducationExtractor
from resume_engine.extraction.skills import SkillsExtractor
from resume_engine.extraction.titles_companies import TitlesCompaniesExtractor
from resume_engine.segmentation.segmenter import SegmentedDocument

_EXTRACTORS = (
    ContactExtractor(),
    DatesExtractor(),
    TitlesCompaniesExtractor(),
    EducationExtractor(),
    SkillsExtractor(),
)


def extract_candidate(segmented: SegmentedDocument) -> list[RawExtraction]:
    """Run every field-family extractor and return the combined results.

    Tolerates missing/empty sections and malformed/partial input -- each
    extractor treats an absent or empty section as simply having nothing
    to extract, not an error. An extractor finding zero entities is a
    normal, valid result; nothing here raises because of that.
    """
    results: list[RawExtraction] = []
    for extractor in _EXTRACTORS:
        results.extend(extractor.extract(segmented))
    return results
