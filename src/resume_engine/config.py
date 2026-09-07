"""Application configuration.

All configuration is read from environment variables (optionally via a
local .env file for development) -- nothing here is hard-coded, and no
secret or credential is ever committed to source control. See .env.example
for the full list of variables a deployment must set.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from resume_engine.schema.candidate_profile import DEFAULT_REVIEW_THRESHOLD


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RESUME_ENGINE_", extra="ignore")

    app_env: str = Field(default="development")

    # Storage
    upload_storage_dir: Path = Field(default=Path("var/uploads"))
    sqlite_db_path: Path = Field(default=Path("var/db.sqlite3"))

    # Upload limits (security: strict validation / file size limits)
    max_upload_size_mb: int = Field(default=10)
    allowed_upload_extensions: tuple[str, ...] = (".pdf", ".docx")

    # CORS: the review UI is a separate origin/app
    cors_allowed_origins: tuple[str, ...] = Field(default=("http://localhost:5173",))

    # Deployment / HTTPS readiness
    force_https: bool = Field(default=False)

    # Confidence scoring: fields scored below this are flagged for
    # recruiter review. An engineering-heuristic threshold (see
    # confidence/scorer.py), not empirically calibrated -- configurable
    # per deployment without a code change. Defaults to
    # schema.candidate_profile.DEFAULT_REVIEW_THRESHOLD.
    confidence_review_threshold: float = Field(default=DEFAULT_REVIEW_THRESHOLD, ge=0.0, le=1.0)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


def get_settings() -> Settings:
    """Factory used via FastAPI dependency injection so tests can override it."""
    return Settings()
