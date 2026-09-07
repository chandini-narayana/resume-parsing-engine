"""Contact information extraction: email, phone, URL, full name.

Email/phone/URL are purely deterministic (regex, shared with
segmentation's contact-detection patterns). Name extraction is a light
heuristic: the first Contact-section block that isn't itself an
email/phone/URL and looks name-shaped (short, no digits, starts with a
capital letter) -- flagged as lower-confidence than the regex-backed
fields, since there's no structural guarantee it's actually a name.
"""

from __future__ import annotations

from resume_engine.common.patterns import EMAIL_RE, PHONE_RE, URL_RE
from resume_engine.extraction.base import ExtractionEvidence, FieldExtractor, RawExtraction
from resume_engine.representation.document import TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument


def _looks_like_name(text: str) -> bool:
    words = text.split()
    if not (1 <= len(words) <= 5):
        return False
    if any(char.isdigit() for char in text):
        return False
    if EMAIL_RE.search(text) or PHONE_RE.search(text) or URL_RE.search(text):
        return False
    return text[:1].isupper()


class ContactExtractor(FieldExtractor):
    def extract(self, segmented: SegmentedDocument) -> list[RawExtraction]:
        results: list[RawExtraction] = []
        name_found = False

        for block in segmented.sections.get(ResumeSection.CONTACT, []):
            text = block.text

            for m in EMAIL_RE.finditer(text):
                results.append(self._make("email", m.group(), block, "regex"))
            for m in PHONE_RE.finditer(text):
                results.append(self._make("phone", m.group(), block, "regex"))
            for m in URL_RE.finditer(text):
                results.append(self._make("url", m.group().rstrip(".,;"), block, "regex"))

            if not name_found and _looks_like_name(text.strip()):
                results.append(
                    self._make(
                        "full_name",
                        text.strip(),
                        block,
                        "section_heuristic",
                        matching_strength="weak",
                        ambiguous=True,
                        ambiguity_reason="shape heuristic only, not structurally confirmed",
                    )
                )
                name_found = True

        return results

    @staticmethod
    def _make(
        field_name: str,
        value: str,
        block: TextBlock,
        method: str,
        matching_strength: str = "exact",
        ambiguous: bool = False,
        ambiguity_reason: str | None = None,
    ) -> RawExtraction:
        return RawExtraction(
            field_name=field_name,
            value=value,
            source_blocks=[block],
            evidence=ExtractionEvidence(
                method=method,
                section=ResumeSection.CONTACT,
                matching_strength=matching_strength,
                signals_agree=not ambiguous,
                ambiguous=ambiguous,
                ambiguity_reason=ambiguity_reason,
            ),
        )
