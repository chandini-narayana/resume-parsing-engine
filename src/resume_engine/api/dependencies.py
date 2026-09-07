"""FastAPI dependency providers.

Centralizing these means tests can override them (e.g. point at a temp
SQLite file / temp storage dir) without monkeypatching internals.
"""

from __future__ import annotations

from functools import lru_cache

from resume_engine.confidence.scorer import ConfidenceConfig, HeuristicConfidenceScorer
from resume_engine.config import Settings, get_settings
from resume_engine.persistence.repository import CandidateRepository
from resume_engine.persistence.sqlite_repository import SqliteCandidateRepository
from resume_engine.pipeline.orchestrator import ResumeProcessingPipeline
from resume_engine.storage.file_storage import FileStorage, LocalFileStorage


@lru_cache
def _settings_singleton() -> Settings:
    return get_settings()


def provide_settings() -> Settings:
    return _settings_singleton()


def provide_repository() -> CandidateRepository:
    settings = _settings_singleton()
    return SqliteCandidateRepository(settings.sqlite_db_path)


def provide_file_storage() -> FileStorage:
    settings = _settings_singleton()
    return LocalFileStorage(settings.upload_storage_dir)


@lru_cache
def _pipeline_singleton() -> ResumeProcessingPipeline:
    # Constructing this loads the skill taxonomy and the spaCy model --
    # expensive enough to build once per process, not once per request.
    settings = _settings_singleton()
    scorer = HeuristicConfidenceScorer(
        ConfidenceConfig(review_threshold=settings.confidence_review_threshold)
    )
    return ResumeProcessingPipeline(confidence_scorer=scorer)


def provide_pipeline() -> ResumeProcessingPipeline:
    return _pipeline_singleton()
