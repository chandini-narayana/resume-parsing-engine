"""Resume intake, processing, and correction endpoints.

Upload now runs the full synchronous pipeline (parsing -> segmentation ->
extraction -> normalization -> CandidateProfile assembly) rather than
stopping at "uploaded" -- see pipeline.orchestrator.ResumeProcessingPipeline.
Processing status moves uploaded -> processing -> completed | failed.
A failure never leaks a stack trace, local path, or other internal detail
to the response -- only the safe message ResumeProcessingPipeline already
produced.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import ValidationError

from resume_engine.api.dependencies import (
    provide_file_storage,
    provide_pipeline,
    provide_repository,
    provide_settings,
)
from resume_engine.api.schemas import (
    CandidateStatusResponse,
    CandidateUploadResponse,
    CorrectionRequest,
    CorrectionResponse,
)
from resume_engine.config import Settings
from resume_engine.corrections.applier import CorrectionError, apply_correction
from resume_engine.persistence.models import CandidateRecord, Correction
from resume_engine.persistence.repository import CandidateRepository
from resume_engine.pipeline.orchestrator import ResumeProcessingPipeline
from resume_engine.schema.candidate_profile import CandidateProfile
from resume_engine.security.filenames import generate_stored_filename, sanitize_for_display
from resume_engine.security.upload_validation import (
    UploadLimits,
    UploadValidationError,
    validate_upload,
)
from resume_engine.storage.file_storage import FileStorage

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=CandidateUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile,
    settings: Settings = Depends(provide_settings),
    repository: CandidateRepository = Depends(provide_repository),
    file_storage: FileStorage = Depends(provide_file_storage),
    pipeline: ResumeProcessingPipeline = Depends(provide_pipeline),
) -> CandidateUploadResponse:
    content = await file.read()
    limits = UploadLimits(
        allowed_extensions=settings.allowed_upload_extensions,
        max_size_bytes=settings.max_upload_size_bytes,
    )
    try:
        ext = validate_upload(file.filename or "", content, limits)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stored_filename = generate_stored_filename(
        file.filename or "", settings.allowed_upload_extensions
    )
    file_storage.save(stored_filename, content)

    candidate_id = str(uuid.uuid4())
    uploaded_at = datetime.now(UTC).isoformat()
    record = CandidateRecord(
        id=candidate_id,
        original_filename=sanitize_for_display(file.filename or "unnamed"),
        stored_filename=stored_filename,
        file_format=ext.lstrip("."),
        file_size_bytes=len(content),
        status="uploaded",
        uploaded_at=uploaded_at,
    )
    repository.create_candidate(record)

    final_status, processing_error = _run_pipeline_and_persist(
        candidate_id, stored_filename, file_storage, repository, pipeline
    )

    return CandidateUploadResponse(
        candidate_id=candidate_id,
        original_filename=record.original_filename,
        file_format=record.file_format,
        status=final_status,
        uploaded_at=uploaded_at,
    )


def _run_pipeline_and_persist(
    candidate_id: str,
    stored_filename: str,
    file_storage: FileStorage,
    repository: CandidateRepository,
    pipeline: ResumeProcessingPipeline,
) -> tuple[str, str | None]:
    """Runs the pipeline for one already-stored file and persists the
    outcome. Returns (final_status, processing_error) for the caller to
    echo back in its response -- this function never raises for a
    processing failure, only for something that should genuinely be a
    500 (handled by the app's generic exception handler, which already
    strips internal detail from the response)."""
    repository.update_candidate_status(candidate_id, "processing")

    file_path = file_storage.path_for(stored_filename)
    if file_path is None:
        error_message = "This deployment's file storage does not support local processing."
        repository.update_candidate_status(candidate_id, "failed", error_message)
        return "failed", error_message

    result = pipeline.process(file_path)

    if result.status == "completed" and result.profile is not None:
        repository.save_profile_json(candidate_id, result.profile.model_dump_json())
        repository.update_candidate_status(candidate_id, "completed")
        return "completed", None

    error_message = result.error_message or "Resume processing failed."
    repository.update_candidate_status(candidate_id, "failed", error_message)
    return "failed", error_message


@router.get("/{candidate_id}", response_model=CandidateStatusResponse)
def get_resume(
    candidate_id: str,
    repository: CandidateRepository = Depends(provide_repository),
) -> CandidateStatusResponse:
    record = repository.get_candidate(candidate_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    profile_json = repository.get_profile_json(candidate_id)
    profile = json.loads(profile_json) if profile_json else None

    return CandidateStatusResponse(
        candidate_id=record.id,
        original_filename=record.original_filename,
        file_format=record.file_format,
        status=record.status,
        uploaded_at=record.uploaded_at,
        processing_error=record.processing_error,
        profile=profile,
    )


@router.post("/{candidate_id}/corrections", response_model=CorrectionResponse, status_code=201)
def submit_correction(
    candidate_id: str,
    correction: CorrectionRequest,
    repository: CandidateRepository = Depends(provide_repository),
) -> CorrectionResponse:
    """Applies a recruiter correction to the stored CandidateProfile.

    Pipeline: load profile -> apply correction (schema-aware, whitelisted
    field_path only, see corrections/applier.py) -> re-validate the whole
    profile -> persist -> record the audit log entry. Any failure in the
    first three steps raises before anything is written, so a client never
    gets a 201 for a correction that wasn't actually applied and persisted
    -- audit-log-only success without a matching profile update no longer
    happens.
    """
    record = repository.get_candidate(candidate_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    profile_json = repository.get_profile_json(candidate_id)
    if profile_json is None:
        raise HTTPException(
            status_code=400,
            detail=f"Candidate {candidate_id} has no processed profile to correct yet "
            f"(status: {record.status}).",
        )

    profile = CandidateProfile.model_validate_json(profile_json)
    profile_data = profile.model_dump(mode="json")

    try:
        applied = apply_correction(profile_data, correction.field_path, correction.corrected_value)
    except CorrectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        updated_profile = CandidateProfile.model_validate(applied.updated_profile_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail="Corrected value is not valid for this field."
        ) from exc

    repository.save_profile_json(candidate_id, updated_profile.model_dump_json())

    corrected_at = datetime.now(UTC).isoformat()
    repository.add_correction(
        Correction(
            id=0,  # assigned by the database
            candidate_id=candidate_id,
            field_path=correction.field_path,
            original_value=applied.original_value,
            corrected_value=correction.corrected_value,
            corrected_by=correction.corrected_by,
            corrected_at=corrected_at,
        )
    )

    return CorrectionResponse(
        candidate_id=candidate_id,
        field_path=correction.field_path,
        corrected_value=correction.corrected_value,
        corrected_by=correction.corrected_by,
        corrected_at=corrected_at,
        original_value=applied.original_value,
        profile=updated_profile.model_dump(mode="json"),
    )
