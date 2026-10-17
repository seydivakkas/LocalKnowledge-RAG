"""Small frozen source-reference schema used by future ingest/retrieval stages.

No citation can be marked verified merely by constructing a dataclass.
Verification is the responsibility of a future EvidenceVerifier (G07+).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class SourceKind(str, Enum):
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"


def require_sha256(value: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError("SHA-256 must be 64 lowercase hexadecimal characters")
    return value


def _nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")


@dataclass(frozen=True, slots=True)
class DocumentRef:
    document_id: str
    kind: SourceKind
    display_name: str

    def __post_init__(self) -> None:
        _nonempty(self.document_id, "document_id")
        _nonempty(self.display_name, "display_name")
        if not isinstance(self.kind, SourceKind):
            raise ValueError("kind must be SourceKind")


@dataclass(frozen=True, slots=True)
class VersionRef:
    document: DocumentRef
    sha256: str
    revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.document, DocumentRef):
            raise ValueError("document must be DocumentRef")
        require_sha256(self.sha256)
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("revision must be a positive integer")


@dataclass(frozen=True, slots=True)
class PageRef:
    """One-indexed physical PDF page reference — never used for DOCX/TXT."""
    version: VersionRef
    page_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.version, VersionRef) or self.version.document.kind is not SourceKind.PDF:
            raise ValueError("PageRef only valid for PDF versions")
        if isinstance(self.page_number, bool) or not isinstance(self.page_number, int) or self.page_number < 1:
            raise ValueError("page_number must be >= 1")


@dataclass(frozen=True, slots=True)
class SpanRef:
    """Original text offsets [start,end); no fictional Word/TXT page labels."""
    version: VersionRef
    start: int
    end: int
    paragraph_index: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.version, VersionRef) or self.version.document.kind not in (SourceKind.DOCX, SourceKind.TXT):
            raise ValueError("SpanRef only valid for DOCX or TXT versions")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (self.start, self.end)):
            raise ValueError("span offsets must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("span offset range is invalid")
        if self.paragraph_index is not None and (isinstance(self.paragraph_index, bool) or not isinstance(self.paragraph_index, int) or self.paragraph_index < 0):
            raise ValueError("paragraph_index must be >= 0")


SourceAnchor = PageRef | SpanRef


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Raw search result. BM25 rank/score are not probability/confidence."""
    anchor: SourceAnchor
    snippet: str
    rank: int
    bm25_score: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.anchor, (PageRef, SpanRef)):
            raise ValueError("anchor required")
        _nonempty(self.snippet, "snippet")
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("rank must be >= 1")
        if self.bm25_score is not None:
            import math
            if isinstance(self.bm25_score, bool) or not isinstance(self.bm25_score, (int, float)) or not math.isfinite(self.bm25_score):
                raise ValueError("bm25_score must be finite")


@dataclass(frozen=True, slots=True)
class CitationRef:
    """Candidate evidence link. Display as VERIFIED only after exact-span resolver."""
    anchor: SourceAnchor
    exact_quote: str

    def __post_init__(self) -> None:
        if not isinstance(self.anchor, (PageRef, SpanRef)):
            raise ValueError("citation anchor required")
        _nonempty(self.exact_quote, "exact_quote")
