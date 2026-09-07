"""Persistence interface.

The rest of the application depends only on this interface. SQLite is the
MVP implementation (see sqlite_repository.py); swapping in Postgres or
another store later means writing one new class, not touching callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from resume_engine.persistence.models import CandidateRecord, Correction, ReviewState


class CandidateRepository(ABC):
    @abstractmethod
    def create_candidate(self, record: CandidateRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_candidate(self, candidate_id: str) -> CandidateRecord | None:
        raise NotImplementedError

    @abstractmethod
    def update_candidate_status(
        self, candidate_id: str, status: str, processing_error: str | None = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_profile_json(self, candidate_id: str, profile_json: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_profile_json(self, candidate_id: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def add_correction(self, correction: Correction) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_corrections(self, candidate_id: str) -> list[Correction]:
        raise NotImplementedError

    @abstractmethod
    def set_review_state(self, state: ReviewState) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_review_state(self, candidate_id: str) -> ReviewState | None:
        raise NotImplementedError
