"""Resume Parsing & Skill Extraction Engine.

Top-level package for the resume intelligence pipeline. Submodules are kept
separable per the project brief so any stage (parsing, extraction,
normalization, etc.) can be replaced or extended without rewriting the
others:

    ingestion       -> file upload handling / file-type routing
    parsing         -> format-specific parsers (PDF, DOCX, ...)
    representation  -> canonical in-memory document representation
    segmentation    -> splitting a document into resume sections
    extraction      -> pulling structured fields out of each section
    normalization   -> mapping extracted skills to a canonical taxonomy
    confidence      -> per-field confidence scoring
    schema          -> the structured candidate profile data contract
    pipeline        -> orchestration wiring the stages together
    api             -> FastAPI backend exposing the pipeline
"""

__version__ = "0.0.1"
