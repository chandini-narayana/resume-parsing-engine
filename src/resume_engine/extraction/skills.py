"""Skill candidate extraction (not normalization).

This stage only identifies skill *mentions* and preserves the original
phrase -- mapping variants to a canonical taxonomy entry is the
normalization stage's job (deliberately not done here, per the task
brief).

Two different extraction rules for two different levels of trust:

1. Skills section content: split on commas/bullets/semicolons and taken
   essentially at face value. A recruiter's own Skills section is the
   strongest available signal for "this is a skill" -- we don't require
   each item to match a known-technology list, because a specific
   internal tool name or niche skill wouldn't be in any generic seed list
   but is still exactly what belongs here.

2. Skill mentions in Experience/Unclassified free text: matched ONLY
   against a curated seed list of common technology terms and
   abbreviations (see _SEED_TERMS below). This is deliberately
   conservative -- scanning free-flowing sentences for "any noun that
   might be a skill" would extract ordinary English words. The seed list
   is a placeholder pending the real canonical taxonomy (normalization
   task); it is not claimed to be complete.

No model is used to *infer* skills from context (e.g. guessing skills
implied by a job title) -- every skill extracted here is a literal
substring of the source text, per "do not invent skills merely because a
model associates them with a job title."
"""

from __future__ import annotations

import re

from resume_engine.extraction.base import ExtractionEvidence, FieldExtractor, RawExtraction
from resume_engine.representation.document import TextBlock
from resume_engine.segmentation.segmenter import ResumeSection, SegmentedDocument

# Case-insensitive: full names/multi-word terms, unlikely to collide with
# ordinary English words.
_SEED_TERMS_CI = (
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Ansible",
    "Jenkins",
    "Git",
    "Linux",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "FastAPI",
    "Django",
    "Flask",
    "React",
    "Angular",
    "Vue",
    "Node.js",
    "Spring",
    "TensorFlow",
    "PyTorch",
    "Kafka",
    "Spark",
    "Hadoop",
    "Snowflake",
    "Airflow",
    "GraphQL",
    "Golang",
    "Ruby",
    "Swift",
    "Kotlin",
    "Scala",
    "Rust",
    "PHP",
    "Bash",
    "PowerShell",
    "Excel",
    "Tableau",
    "Power BI",
    "Salesforce",
    "Jira",
    "Confluence",
    "Figma",
    "Photoshop",
    "Machine Learning",
    "Deep Learning",
    "Scikit-learn",
    "LangChain",
)

# Case-sensitive: short abbreviations, where lowercasing would risk
# matching ordinary words. Word-boundary matching still applies.
_SEED_TERMS_CS = (
    "SQL",
    "AWS",
    "GCP",
    "API",
    "ML",
    "AI",
    "NLP",
    "CI/CD",
    "REST",
    "HTML",
    "CSS",
    "ETL",
    "CRM",
    "ERP",
    "OOP",
    "TDD",
    "IAM",
    "VPC",
    "S3",
    "EC2",
    "JSON",
    "XML",
    "YAML",
    "SDK",
    "CLI",
    "GUI",
    "SaaS",
    "PaaS",
    "IaaS",
    "IoT",
)

_SPLIT_RE = re.compile(r"[,;•]|(?:^|\n)\s*[-*]\s+")


def _build_term_pattern(term: str, ignore_case: bool) -> re.Pattern[str]:
    escaped = re.escape(term)
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(rf"\b{escaped}\b", flags)


_SEED_PATTERNS_CI = [(t, _build_term_pattern(t, ignore_case=True)) for t in _SEED_TERMS_CI]
_SEED_PATTERNS_CS = [(t, _build_term_pattern(t, ignore_case=False)) for t in _SEED_TERMS_CS]


class SkillsExtractor(FieldExtractor):
    def extract(self, segmented: SegmentedDocument) -> list[RawExtraction]:
        results: list[RawExtraction] = []
        seen: set[str] = set()

        for block in segmented.sections.get(ResumeSection.SKILLS, []):
            for candidate in self._split_skill_list(block.text):
                key = candidate.lower()
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    self._make(
                        candidate,
                        block,
                        "section_heuristic",
                        section=ResumeSection.SKILLS,
                        matching_strength="exact",
                    )
                )

        for section in (ResumeSection.EXPERIENCE, ResumeSection.UNCLASSIFIED):
            for block in segmented.sections.get(section, []):
                for term, matched_text in self._find_seed_terms(block.text):
                    key = term.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        self._make(
                            matched_text,
                            block,
                            "seed_list_match",
                            section=section,
                            matching_strength="weak",
                            ambiguous=True,
                            ambiguity_reason=f"outside the Skills section ({section.value})",
                        )
                    )

        return results

    @staticmethod
    def _split_skill_list(text: str) -> list[str]:
        parts = _SPLIT_RE.split(text)
        return [p.strip(" \t.") for p in parts if p.strip(" \t.")]

    @staticmethod
    def _find_seed_terms(text: str) -> list[tuple[str, str]]:
        found = []
        for term, pattern in _SEED_PATTERNS_CI:
            m = pattern.search(text)
            if m:
                found.append((term, m.group()))
        for term, pattern in _SEED_PATTERNS_CS:
            m = pattern.search(text)
            if m:
                found.append((term, m.group()))
        return found

    @staticmethod
    def _make(
        value: str,
        block: TextBlock,
        method: str,
        section: ResumeSection,
        matching_strength: str = "exact",
        ambiguous: bool = False,
        ambiguity_reason: str | None = None,
    ) -> RawExtraction:
        return RawExtraction(
            field_name="skill",
            value=value,
            source_blocks=[block],
            evidence=ExtractionEvidence(
                method=method,
                section=section,
                matching_strength=matching_strength,
                signals_agree=not ambiguous,
                ambiguous=ambiguous,
                ambiguity_reason=ambiguity_reason,
                normalization_ready=matching_strength == "exact",
            ),
        )
