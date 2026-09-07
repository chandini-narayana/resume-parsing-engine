"""API-level request/response models.

Kept separate from schema/candidate_profile.py (the pipeline's internal
data contract) so the public API surface can evolve independently of
internal pipeline types.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Consistent error shape for every non-2xx response.

    Never includes stack traces, file paths, or other internal detail --
    only a stable machine-readable `code` and a human-readable `message`.
    """

    code: str
    message: str


class CandidateUploadResponse(BaseModel):
    candidate_id: str
    original_filename: str
    file_format: str
    status: str
    uploaded_at: str


class CandidateStatusResponse(BaseModel):
    candidate_id: str
    original_filename: str
    file_format: str
    status: str
    uploaded_at: str
    processing_error: str | None = Field(
        default=None,
        description="Safe-to-display message set when status == 'failed'.",
    )
    profile: dict | None = Field(
        default=None,
        description="Structured candidate profile, once processing has produced one.",
    )


class CorrectionRequest(BaseModel):
    """A single recruiter correction to one field of a candidate profile.

    Validated server-side regardless of what the review UI already
    validated client-side.
    """

    field_path: str = Field(min_length=1, max_length=200)
    corrected_value: str = Field(min_length=0, max_length=5000)
    corrected_by: str | None = Field(default=None, max_length=200)


class CorrectionResponse(BaseModel):
    candidate_id: str
    field_path: str
    corrected_value: str
    corrected_by: str | None
    corrected_at: str
    original_value: str | None = Field(
        default=None,
        description="The value being replaced, captured at correction time.",
    )
    profile: dict = Field(
        description="The full candidate profile as persisted after this correction was applied, "
        "so a client can reflect the update without a second GET.",
    )
