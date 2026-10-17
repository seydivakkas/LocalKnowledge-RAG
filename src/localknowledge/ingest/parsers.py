"""Bounded PDF/DOCX/TXT intake preflight and positional metadata only.

G03 intentionally does NOT build chunks, FTS or verified citations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile

from ..domain.models import SourceKind

MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 300
MAX_DOCX_UNCOMPRESSED = 75 * 1024 * 1024
MAX_DOCX_FILES = 1000
MAX_TEXT_CHARS = 5_000_000

class IntakeError(ValueError):
    """Explicit user-facing failures; avoid displaying parsed document content."""
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class InspectedSource:
    kind: SourceKind
    page_chars: tuple[int, ...] = ()
    paragraph_offsets: tuple[tuple[int, int], ...] = ()
    warning: str = ""

    @property
    def page_count(self) -> int | None:
        return len(self.page_chars) if self.kind is SourceKind.PDF else None

    @property
    def paragraph_count(self) -> int | None:
        return len(self.paragraph_offsets) if self.kind is not SourceKind.PDF else None


def inspect(path: Path, declared_extension: str) -> InspectedSource:
    extension = declared_extension.lower()
    if extension not in {'.pdf', '.txt', '.docx'}:
        raise IntakeError('UNSUPPORTED_FORMAT', 'Yalnız PDF, DOCX ve TXT belgeleri desteklenir.')
    if path.stat().st_size == 0:
        raise IntakeError('EMPTY_FILE', 'Boş belge içe alınamaz.')
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise IntakeError('FILE_TOO_LARGE', '50 MiB sınırı aşıldı.')
    with path.open('rb') as file:
        header = file.read(16)
    if extension == '.pdf':
        if not header.startswith(b'%PDF-'):
            raise IntakeError('WRONG_FORMAT', 'Uzantı PDF fakat dosya PDF imzası taşımıyor.')
        try:
            import pdfplumber
        except ImportError as exc:
            raise IntakeError('PARSER_MISSING', 'PDF okuyucu bağımlılığı kurulu değil.') from exc
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages = len(pdf.pages)
                if pages == 0 or pages > MAX_PDF_PAGES:
                    raise IntakeError('PAGE_LIMIT', 'PDF sayfa sayısı geçersiz veya 300 sınırını aştı.')
                # Do not fully OCR or store extracted text at G03. Extraction is G04/G05.
                return InspectedSource(SourceKind.PDF, page_chars=(0,) * pages,
                                       warning='Sayfa kaydı hazır; PDF metni henüz indekslenmedi.')
        except IntakeError:
            raise
        except Exception as exc:
            name = type(exc).__name__.lower()
            if 'password' in name or 'encrypted' in name or 'password' in str(exc).lower():
                raise IntakeError('ENCRYPTED_PDF', 'Şifreli PDF için oturum kontrollü açma henüz desteklenmiyor.') from None
            raise IntakeError('INVALID_PDF', 'PDF açılamadı veya yapısı geçersiz.') from None
    if extension == '.docx':
        if header[:2] != b'PK':
            raise IntakeError('WRONG_FORMAT', 'DOCX dosyası ZIP/OpenXML imzası taşımıyor.')
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_DOCX_FILES or sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED:
                    raise IntakeError('ZIP_LIMIT', 'DOCX içeriği güvenli kaynak sınırını aşıyor.')
                if any(i.file_size > 20 * 1024 * 1024 or (i.compress_size and i.file_size > max(i.compress_size * 200, 2_000_000)) for i in infos):
                    raise IntakeError('ZIP_LIMIT', 'Aşırı sıkıştırılmış DOCX içeriği reddedildi.')
                if any(i.filename.startswith('/') or '..' in Path(i.filename).parts or '\\' in i.filename for i in infos):
                    raise IntakeError('UNSAFE_ARCHIVE', 'DOCX içinde geçersiz dosya yolu var.')
                if 'word/document.xml' not in archive.namelist():
                    raise IntakeError('WRONG_FORMAT', 'DOCX ana belge yapısı bulunamadı.')
            try:
                from docx import Document
            except ImportError as exc:
                raise IntakeError('PARSER_MISSING', 'DOCX okuyucu bağımlılığı kurulu değil.') from exc
            doc = Document(path)
            offsets = []
            cursor = 0
            for p in doc.paragraphs:
                segment = p.text
                if segment.strip():
                    if cursor + len(segment) > MAX_TEXT_CHARS:
                        raise IntakeError('TEXT_LIMIT', 'DOCX metin sınırını aşıyor.')
                    offsets.append((cursor, cursor + len(segment)))
                cursor += len(segment) + 1
            return InspectedSource(SourceKind.DOCX, paragraph_offsets=tuple(offsets),
                warning='Paragraf konumları kaydedildi; Word için sayfa numarası üretilmedi.')
        except IntakeError:
            raise
        except (zipfile.BadZipFile, KeyError, ValueError, OSError):
            raise IntakeError('INVALID_DOCX', 'DOCX arşivi bozuk veya açılamıyor.') from None
        except Exception:
            raise IntakeError('INVALID_DOCX', 'DOCX içeriği çözümlenemedi.') from None
    # TXT is not recognized by any magical header; disallow binary control chars.
    content = path.read_bytes()
    if b'\x00' in content or sum(c < 9 or (13 < c < 32) for c in content[:10000]) > 16:
        raise IntakeError('BINARY_TEXT', 'TXT dosyası ikili içerik taşıyor.')
    try:
        decoded = content.decode('utf-8-sig', errors='strict')
        warning = ''
    except UnicodeDecodeError:
        try:
            decoded = content.decode('cp1254', errors='strict')
            warning = 'Metin CP1254 olarak okundu. Kodlama kullanıcı tarafından doğrulanmalıdır.'
        except UnicodeDecodeError:
            raise IntakeError('TEXT_ENCODING', 'TXT metin kodlaması desteklenmiyor.') from None
    if not decoded.strip() or len(decoded) > MAX_TEXT_CHARS:
        raise IntakeError('TEXT_LIMIT', 'TXT boş veya karakter sınırının dışında.')
    offsets = []
    cursor = 0
    for line in decoded.splitlines(keepends=True):
        body = line.rstrip('\r\n')
        if body.strip():
            offsets.append((cursor, cursor + len(body)))
        cursor += len(line)
    if not offsets:  # one-line corner case
        offsets = [(0, len(decoded))]
    return InspectedSource(SourceKind.TXT, paragraph_offsets=tuple(offsets), warning=warning)
