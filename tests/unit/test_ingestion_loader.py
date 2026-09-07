import pytest

from resume_engine.ingestion.loader import (
    IngestionError,
    build_default_parser_registry,
    load_resume,
)
from tests.fixtures_path import FIXTURES_DIR


@pytest.fixture
def registry():
    return build_default_parser_registry()


def test_loads_pdf_resume(registry):
    doc = load_resume(FIXTURES_DIR / "normal_resume.pdf", registry)
    assert doc.source_format == "pdf"
    assert doc.blocks


def test_loads_docx_resume(registry):
    doc = load_resume(FIXTURES_DIR / "normal_resume.docx", registry)
    assert doc.source_format == "docx"
    assert doc.blocks


def test_unsupported_extension_raises_ingestion_error(registry, tmp_path):
    bad_file = tmp_path / "resume.txt"
    bad_file.write_text("not a resume")
    with pytest.raises(IngestionError):
        load_resume(bad_file, registry)


def test_missing_file_raises_ingestion_error(registry, tmp_path):
    with pytest.raises(IngestionError):
        load_resume(tmp_path / "does_not_exist.pdf", registry)


def test_corrupt_pdf_raises_ingestion_error_not_parsing_error(registry):
    # Ingestion wraps ParsingError as IngestionError so callers only need
    # to handle one exception type at this layer.
    with pytest.raises(IngestionError):
        load_resume(FIXTURES_DIR / "corrupt.pdf", registry)


def test_corrupt_docx_raises_ingestion_error(registry):
    with pytest.raises(IngestionError):
        load_resume(FIXTURES_DIR / "corrupt.docx", registry)


def test_empty_pdf_does_not_raise_and_carries_warnings(registry):
    # An empty/scanned document is a successful-but-low-content parse,
    # not an ingestion failure -- the warning surfaces instead of an exception.
    doc = load_resume(FIXTURES_DIR / "empty_resume.pdf", registry)
    assert doc.blocks == []
    assert doc.parser_warnings
