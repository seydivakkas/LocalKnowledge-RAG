"""Immutable typed domain contracts. No persistence or UI imports."""
from .models import CitationRef, DocumentRef, PageRef, SearchHit, SourceKind, SpanRef, VersionRef
from .errors import ErrorCode, LocalKnowledgeError

__all__ = ["CitationRef", "DocumentRef", "PageRef", "SearchHit", "SourceKind", "SpanRef", "VersionRef", "ErrorCode", "LocalKnowledgeError"]
