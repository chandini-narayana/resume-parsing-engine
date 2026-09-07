"""Parser interface.

Every format-specific parser implements this interface and returns a
ParsedDocument (see representation/document.py). The pipeline depends only
on this interface, so adding a parser for a new format later means writing
one new class here and registering it -- no changes to segmentation,
extraction, or the orchestrator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from resume_engine.representation.document import ParsedDocument


class ParsingError(Exception):
    """Raised when a document cannot be parsed at all (corrupt/unreadable).

    Distinct from a parser successfully returning a ParsedDocument that
    happens to be empty or low-content with warnings attached (e.g. a
    scanned PDF) -- that is not an error, it's an honestly-reported
    result. ParsingError is for the case where parsing cannot proceed at
    all, e.g. the file is not a valid PDF/DOCX despite its extension.
    """


class PdfParsingError(ParsingError):
    pass


class DocxParsingError(ParsingError):
    pass


class ResumeParser(ABC):
    """Base class for a single input-format parser (e.g. PDF, DOCX)."""

    #: File extensions this parser claims to handle, e.g. {".pdf"}.
    supported_extensions: frozenset[str] = frozenset()

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        """Parse `file_path` into a ParsedDocument.

        Implementations must never silently drop content: text that cannot
        be confidently placed in the layout should still be captured as a
        TextBlock (kind=UNKNOWN) with a parser_warning explaining why,
        rather than discarded. Raises ParsingError (or a format-specific
        subclass) if the file cannot be opened/parsed at all.
        """
        raise NotImplementedError


class ParserRegistry:
    """Maps file extensions to a ResumeParser instance.

    This is the extension point referenced in the architecture: a new
    format is added by implementing ResumeParser and calling `register`,
    without touching any other stage of the pipeline.
    """

    def __init__(self) -> None:
        self._parsers: dict[str, ResumeParser] = {}

    def register(self, parser: ResumeParser) -> None:
        for ext in parser.supported_extensions:
            self._parsers[ext.lower()] = parser

    def get_parser(self, file_path: Path) -> ResumeParser:
        ext = file_path.suffix.lower()
        try:
            return self._parsers[ext]
        except KeyError as exc:
            raise ValueError(f"No parser registered for file type '{ext}'") from exc
