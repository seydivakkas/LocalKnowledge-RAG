"""Stable application errors; no business exceptions in Tk callbacks."""
from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    FTS_UNAVAILABLE = "FTS_UNAVAILABLE"
    OCR_REQUIRED = "OCR_REQUIRED"
    MODEL_NOT_INSTALLED = "MODEL_NOT_INSTALLED"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    FEATURE_NOT_READY = "FEATURE_NOT_READY"
    IO_ERROR = "IO_ERROR"


MESSAGES_TR: dict[ErrorCode, str] = {
    ErrorCode.SOURCE_MISMATCH: "Kaynak dosya değişmiş. Alıntı doğrulanamadı.",
    ErrorCode.FTS_UNAVAILABLE: "Yerel arama modülü henüz bağlanmadı.",
    ErrorCode.OCR_REQUIRED: "Bu belge için OCR gerekebilir. İsteğe bağlı OCR henüz etkin değil.",
    ErrorCode.MODEL_NOT_INSTALLED: "Yerel AI modeli kurulmadı. Belge araması bağımsız çalışır.",
    ErrorCode.UNSUPPORTED_VERSION: "Veritabanı sürümü desteklenmiyor. Veriler değiştirilmedi.",
    ErrorCode.FEATURE_NOT_READY: "Bu işlev geliştirme aşamasında; şu anda kullanılamıyor.",
    ErrorCode.IO_ERROR: "Yerel dosya işlemi gerçekleştirilemedi.",
}


class LocalKnowledgeError(RuntimeError):
    def __init__(self, code: ErrorCode, detail: str | None = None):
        self.code = code
        super().__init__(detail or MESSAGES_TR[code])
