"""Resume ingestion.

Single entry point that turns a file path into a ParsedDocument, by
routing to the correct ResumeParser via the ParserRegistry. Upload-level
validation (extension/size/magic bytes) is security.upload_validation's
job and is assumed to have already happened before this is called; this
module focuses on routing and surfacing parser failures clearly rather
than re-validating.

Not yet wired into the FastAPI upload endpoint -- see the task report for
why that's deferred.
"""

from __future__ import annotations

from pathlib import Path

from resume_engine.parsing.base import ParserRegistry, ParsingError
from resume_engine.parsing.docx_parser import DocxResumeParser
from resume_engine.parsing.pdf_parser import PdfResumeParser
from resume_engine.representation.document import ParsedDocument


class IngestionError(Exception):
    """Raised when an uploaded file cannot be accepted for parsing."""


def build_default_parser_registry() -> ParserRegistry:
    """The MVP's parser set: PDF and DOCX.

    Adding a new input format later means implementing one ResumeParser
    and registering it here -- nothing else in ingestion/segmentation/
    extraction needs to change.
    """
    registry = ParserRegistry()
    registry.register(PdfResumeParser())
    registry.register(DocxResumeParser())
    return registry


def load_resume(file_path: Path, registry: ParserRegistry) -> ParsedDocument:
    """Parse an uploaded resume file via the registry.

    Raises IngestionError if no parser is registered for the file's
    extension, or if the underlying parser cannot open/read the file at
    all (ParsingError). A parser that *succeeds* but reports warnings
    (e.g. an image-only PDF) is not an IngestionError -- that
    ParsedDocument, warnings and all, is still returned, per the
    "never silently discard" requirement.
    """
    if not file_path.exists():
        raise IngestionError(f"File not found: {file_path.name}")

    try:
        parser = registry.get_parser(file_path)
    except ValueError as exc:
        raise IngestionError(str(exc)) from exc

    try:
        return parser.parse(file_path)
    except ParsingError as exc:
        raise IngestionError(f"Failed to parse '{file_path.name}': {exc}") from exc
