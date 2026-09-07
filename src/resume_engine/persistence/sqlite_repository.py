"""SQLite implementation of CandidateRepository.

Uses the stdlib `sqlite3` module -- no extra dependency needed for the MVP
storage engine. One connection per call keeps this safe to use from
FastAPI's threadpool without shared-state issues; SQLite handles
concurrent readers/writers itself at this scale.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from resume_engine.persistence.models import SCHEMA_DDL, CandidateRecord, Correction, ReviewState
from resume_engine.persistence.repository import CandidateRepository


class SqliteCandidateRepository(CandidateRepository):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_DDL)

    def create_candidate(self, record: CandidateRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO candidates
                   (id, original_filename, stored_filename, file_format,
                    file_size_bytes, status, uploaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.original_filename,
                    record.stored_filename,
                    record.file_format,
                    record.file_size_bytes,
                    record.status,
                    record.uploaded_at,
                ),
            )

    def get_candidate(self, candidate_id: str) -> CandidateRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        return CandidateRecord(**dict(row)) if row else None

    def update_candidate_status(
        self, candidate_id: str, status: str, processing_error: str | None = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE candidates SET status = ?, processing_error = ? WHERE id = ?",
                (status, processing_error, candidate_id),
            )

    def save_profile_json(self, candidate_id: str, profile_json: str) -> None:
        with self._connect() as conn:
            now = _utc_now_iso()
            conn.execute(
                """INSERT INTO candidate_profiles
                   (candidate_id, profile_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(candidate_id) DO UPDATE SET
                       profile_json = excluded.profile_json,
                       updated_at = excluded.updated_at""",
                (candidate_id, profile_json, now, now),
            )

    def get_profile_json(self, candidate_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT profile_json FROM candidate_profiles WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        return row["profile_json"] if row else None

    def add_correction(self, correction: Correction) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO corrections
                   (candidate_id, field_path, original_value,
                    corrected_value, corrected_by, corrected_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    correction.candidate_id,
                    correction.field_path,
                    correction.original_value,
                    correction.corrected_value,
                    correction.corrected_by,
                    correction.corrected_at,
                ),
            )

    def list_corrections(self, candidate_id: str) -> list[Correction]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM corrections WHERE candidate_id = ? ORDER BY id", (candidate_id,)
            ).fetchall()
        return [Correction(**dict(row)) for row in rows]

    def set_review_state(self, state: ReviewState) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO review_state
                   (candidate_id, status, reviewed_by, reviewed_at, notes)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(candidate_id) DO UPDATE SET
                       status = excluded.status,
                       reviewed_by = excluded.reviewed_by,
                       reviewed_at = excluded.reviewed_at,
                       notes = excluded.notes""",
                (
                    state.candidate_id,
                    state.status,
                    state.reviewed_by,
                    state.reviewed_at,
                    state.notes,
                ),
            )

    def get_review_state(self, candidate_id: str) -> ReviewState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_state WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
        return ReviewState(**dict(row)) if row else None


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
