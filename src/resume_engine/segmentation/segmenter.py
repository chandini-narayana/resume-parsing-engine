"""Section segmentation.

Splits a ParsedDocument's blocks into the required resume sections
(Contact, Experience, Education, Skills), tolerating heading variants,
missing headings, reordered sections, and table/multi-column content.

Strategy (in priority order, walking blocks in the order the parser
produced them -- which already encodes column/table reading order):

1. Heading detection. A block matches a section heading if its normalized
   text exactly matches one of the phrase variants named in the project
   brief, OR (for a block that otherwise "looks like a heading" -- short,
   title-case/caps, no sentence punctuation, or explicitly tagged
   BlockKind.HEADING by the parser) its normalized text contains one of a
   broader set of keyword stems. Once a heading is matched, all following
   blocks are assigned to that section until the next heading changes it
   -- this matches how a human reads a resume.
2. Contact detection by content (email/phone/URL patterns) applies
   regardless of heading state, so contact details -- including a
   LinkedIn/GitHub/portfolio link on its own line -- embedded without a
   "Contact" heading are still found -- unless a different section has
   already been explicitly headed, to avoid misfiling e.g. a reference's
   email inside an Experience entry.
3. Before any heading has been seen: a short, non-numeric first block is
   treated as the candidate's name (contact); content matching a date
   range is treated as Experience; content matching common degree
   keywords is treated as Education; a short comma-separated list is
   treated as Skills. Anything else with no signal goes to UNCLASSIFIED,
   never dropped.

No numeric segmentation confidence is emitted -- see SegmentedDocument's
docstring for why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from resume_engine.common.patterns import EMAIL_RE, PHONE_RE, URL_RE
from resume_engine.representation.document import BlockKind, ParsedDocument, TextBlock


class ResumeSection(StrEnum):
    CONTACT = "contact"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    UNCLASSIFIED = "unclassified"


_NAMED_SECTIONS = (
    ResumeSection.CONTACT,
    ResumeSection.EXPERIENCE,
    ResumeSection.EDUCATION,
    ResumeSection.SKILLS,
)


@dataclass
class SegmentedDocument:
    """A ParsedDocument split into resume sections.

    `section_headings` records which heading block(s) triggered each
    section, for source-to-extraction traceability in later review.

    Deliberately no per-block confidence field: a meaningful confidence
    number depends on the confidence-scoring stage (not yet implemented),
    and fabricating one here would violate the project's "no fake
    metrics" rule. The block-level provenance already retained (page,
    column, bbox, table position, block_id) is what that stage will
    score against.
    """

    source_filename: str
    sections: dict[ResumeSection, list[TextBlock]] = field(default_factory=dict)
    section_headings: dict[ResumeSection, list[TextBlock]] = field(default_factory=dict)


# --- Heading phrase variants named in the project brief (tier 1: exact match) ---
_HEADING_PHRASES: dict[ResumeSection, tuple[str, ...]] = {
    ResumeSection.EXPERIENCE: (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "career history",
    ),
    ResumeSection.EDUCATION: (
        "education",
        "academic background",
        "qualifications",
        "academic history",
    ),
    ResumeSection.SKILLS: (
        "skills",
        "technical skills",
        "core skills",
        "core competencies",
        "expertise",
        "technologies",
    ),
    ResumeSection.CONTACT: (
        "contact",
        "contact information",
        "contact info",
        "personal information",
        "personal details",
    ),
}

# --- Broader keyword stems (tier 2: only applied to blocks that already look like headings) ---
_HEADING_KEYWORD_STEMS: dict[str, ResumeSection] = {
    "experience": ResumeSection.EXPERIENCE,
    "employment": ResumeSection.EXPERIENCE,
    "career": ResumeSection.EXPERIENCE,
    "education": ResumeSection.EDUCATION,
    "academic": ResumeSection.EDUCATION,
    "qualification": ResumeSection.EDUCATION,
    "qualifications": ResumeSection.EDUCATION,
    "skill": ResumeSection.SKILLS,
    "skills": ResumeSection.SKILLS,
    "competency": ResumeSection.SKILLS,
    "competencies": ResumeSection.SKILLS,
    "expertise": ResumeSection.SKILLS,
    "technology": ResumeSection.SKILLS,
    "technologies": ResumeSection.SKILLS,
    "contact": ResumeSection.CONTACT,
    "personal": ResumeSection.CONTACT,
}

_DATE_RANGE_RE = re.compile(
    r"\b(19|20)\d{2}\b\s*(-|–|—|to)\s*(\b(19|20)\d{2}\b|present|current)", re.IGNORECASE
)
_DEGREE_KEYWORDS = (
    "bachelor",
    "master",
    "phd",
    "ph.d",
    "b.s.",
    "m.s.",
    "b.a.",
    "m.a.",
    "associate degree",
    "university",
    "college",
    "institute of technology",
    "diploma",
)


def segment(document: ParsedDocument) -> SegmentedDocument:
    sections: dict[ResumeSection, list[TextBlock]] = {s: [] for s in ResumeSection}
    section_headings: dict[ResumeSection, list[TextBlock]] = {s: [] for s in _NAMED_SECTIONS}

    current_section: ResumeSection | None = None
    seen_first_heading = False

    for block in document.blocks:
        text = block.text.strip()
        if not text:
            continue

        heading_match = _match_heading(block)
        if heading_match is not None:
            current_section = heading_match
            section_headings[heading_match].append(block)
            seen_first_heading = True
            continue  # the heading itself is a label, not section content

        if (
            EMAIL_RE.search(text) or PHONE_RE.search(text) or URL_RE.search(text)
        ) and current_section in (None, ResumeSection.CONTACT):
            sections[ResumeSection.CONTACT].append(block)
            # Deliberately NOT setting current_section here. Content-based
            # contact detection should file *this* block as contact info
            # without permanently latching the state machine to CONTACT --
            # otherwise, in a headingless document, every block after the
            # first email/phone/URL would incorrectly fall through to the
            # "current_section is not None" branch below instead of going
            # through its own fallback classification (date range, degree
            # keyword, skill list). Only an explicit heading should change
            # what "current section" means for the blocks that follow.
            continue

        if current_section is not None:
            sections[current_section].append(block)
            continue

        fallback = _fallback_classify(text)
        if fallback is not None:
            sections[fallback].append(block)
            continue

        if (
            not seen_first_heading
            and not sections[ResumeSection.CONTACT]
            and _looks_like_name(text)
        ):
            sections[ResumeSection.CONTACT].append(block)
            continue

        sections[ResumeSection.UNCLASSIFIED].append(block)

    return SegmentedDocument(
        source_filename=document.source_filename,
        sections=sections,
        section_headings=section_headings,
    )


def _match_heading(block: TextBlock) -> ResumeSection | None:
    text = block.text.strip()
    if not text:
        return None
    normalized = _normalize_heading(text)

    for section, phrases in _HEADING_PHRASES.items():
        if normalized in phrases:
            return section

    if _looks_like_heading(block):
        for word in normalized.split():
            mapped = _HEADING_KEYWORD_STEMS.get(word)
            if mapped is not None:
                return mapped
    return None


def _looks_like_heading(block: TextBlock) -> bool:
    if block.kind == BlockKind.HEADING:
        return True
    if block.kind not in (BlockKind.PARAGRAPH, BlockKind.UNKNOWN):
        return False
    text = block.text.strip()
    words = text.split()
    if not (1 <= len(words) <= 5):
        return False
    if text.endswith((".", ",", ";")):
        return False
    return text.isupper() or text.istitle()


def _fallback_classify(text: str) -> ResumeSection | None:
    if _DATE_RANGE_RE.search(text):
        return ResumeSection.EXPERIENCE
    lowered = text.lower()
    if any(keyword in lowered for keyword in _DEGREE_KEYWORDS):
        return ResumeSection.EDUCATION
    if _looks_like_skill_list(text):
        return ResumeSection.SKILLS
    return None


def _looks_like_skill_list(text: str) -> bool:
    if text.count(",") < 2:
        return False
    if text.rstrip().endswith((".", "!", "?")):
        return False
    tokens = [t.strip() for t in text.split(",") if t.strip()]
    if not tokens:
        return False
    avg_words = sum(len(t.split()) for t in tokens) / len(tokens)
    return avg_words <= 3


def _looks_like_name(text: str) -> bool:
    words = text.split()
    if not (1 <= len(words) <= 5):
        return False
    if any(char.isdigit() for char in text):
        return False
    if EMAIL_RE.search(text):
        return False
    return text[:1].isupper()


def _normalize_heading(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
