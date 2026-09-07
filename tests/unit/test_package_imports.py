"""Smoke test: every module in the skeleton must import cleanly.

This is the cheapest possible signal that the package structure and
dependency wiring (imports between stages) are sound, before any stage has
real logic.
"""

import importlib

import pytest

MODULES = [
    "resume_engine",
    "resume_engine.config",
    "resume_engine.representation.document",
    "resume_engine.parsing.base",
    "resume_engine.parsing.pdf_parser",
    "resume_engine.parsing.docx_parser",
    "resume_engine.ingestion.loader",
    "resume_engine.segmentation.segmenter",
    "resume_engine.extraction.base",
    "resume_engine.extraction.skills",
    "resume_engine.extraction.titles_companies",
    "resume_engine.extraction.dates",
    "resume_engine.extraction.education",
    "resume_engine.normalization.taxonomy",
    "resume_engine.normalization.normalizer",
    "resume_engine.confidence.scorer",
    "resume_engine.schema.candidate_profile",
    "resume_engine.pipeline.orchestrator",
    "resume_engine.security.filenames",
    "resume_engine.security.upload_validation",
    "resume_engine.storage.file_storage",
    "resume_engine.persistence.models",
    "resume_engine.persistence.repository",
    "resume_engine.persistence.sqlite_repository",
    "resume_engine.api.schemas",
    "resume_engine.api.dependencies",
    "resume_engine.api.routes.system",
    "resume_engine.api.routes.resumes",
    "resume_engine.api.main",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)
