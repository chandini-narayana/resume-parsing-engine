"""Persistence-layer data records and schema DDL.

These are plain records for what gets stored, distinct from
schema/candidate_profile.py (the pipeline's *output* data contract).
`profile_json` stores a serialized CandidateProfile so the repository
doesn't need to know about pipeline internals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CandidateRecord:
    id: str
    original_filename: str  # sanitized for display, see security/filenames.py
    stored_filename: str  # server-generated, see security/filenames.py
    file_format: str  # "pdf" | "docx"
    file_size_bytes: int
    status: str  # "uploaded" | "processing" | "completed" | "failed"
    uploaded_at: str  # ISO 8601 UTC
    processing_error: str | None = None
    # Safe-to-display message set when status == "failed" -- never a raw
    # exception, stack trace, or local file path (see pipeline.orchestrator
    # .ProcessingResult.error_message, which is what populates this).


@dataclass
class Correction:
    id: int
    candidate_id: str
    field_path: str
    original_value: str | None
    corrected_value: str
    corrected_by: str | None
    corrected_at: str  # ISO 8601 UTC


@dataclass
class ReviewState:
    candidate_id: str
    status: str  # "pending_review" | "in_review" | "approved" | "rejected"
    reviewed_by: str | None
    reviewed_at: str | None
    notes: str | None


SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_format TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    processing_error TEXT
);

CREATE TABLE IF NOT EXISTS candidate_profiles (
    candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),
    profile_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    field_path TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT NOT NULL,
    corrected_by TEXT,
    corrected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_state (
    candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),
    status TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    notes TEXT
);
"""
