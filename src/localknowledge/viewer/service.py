"""G06: source hash -> exact passage -> original PDF page -> verified geometry.

The same immutable bytes are passed to pdfplumber and pypdfium2. A valid PDF
page is *not* in itself proof that a rectangle marks the right characters.
When position cannot be proven, we show the page WITHOUT a yellow overlay.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import json
import os
import subprocess
import sys
import tempfile

from ..search.service import SearchService, SourceHit

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_RENDER_PIXELS = 12_000_000
MAX_MATCHES = 100
MAX_HIGHLIGHT_CHARS = 1200


class SourceViewError(ValueError):
    """Safe, stable failure state for a source whose identity cannot be proved."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class HighlightBox:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class SourcePreview:
    hit: SourceHit
    page_number: int                         # 1-based physical PDF page, or paragraph unit
    page_count: int | None
    original_unit: str
    quote_start: int
    quote_end: int
    geometry_status: str                     # VERIFIED / UNVERIFIED_POSITION / TEXT_ONLY
    highlight_boxes: tuple[HighlightBox, ...]
    image_png: bytes | None                  # rendered verified original; transient only
    image_size: tuple[int,int] | None
    detail: str


def _read_managed_bytes(root: Path, hit: SourceHit) -> bytes:
    """Read exactly the content-addressed object, bounded and hashed again.

    This prevents time-of-check/time-of-use confusion between FTS verification
    and PDF rendering. Do not follow symlinks in managed ancestors.
    """
    if not re.fullmatch(r'[0-9a-f]{64}', hit.sha256):
        raise SourceViewError('INVALID_SOURCE_ID','Geçersiz belge kimliği.')
    root = root.absolute()
    objects = root / 'objects'
    parent = objects / hit.sha256[:2]
    path = parent / (hit.sha256 + '.bin')
    if any(item.is_symlink() for item in (root, objects, parent, path)):
        raise SourceViewError('UNSAFE_SOURCE_PATH','Belge deposu beklenmeyen bağlantı içeriyor.')
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_PDF_BYTES:
            raise SourceViewError('SOURCE_NOT_AVAILABLE','Özgün belge güvenli biçimde açılamadı.')
        with path.open('rb') as fh:
            body = fh.read(MAX_PDF_BYTES + 1)
    except OSError:
        raise SourceViewError('SOURCE_NOT_AVAILABLE','Özgün belge dosyası okunamadı.') from None
    if len(body) > MAX_PDF_BYTES or hashlib.sha256(body).hexdigest() != hit.sha256:
        raise SourceViewError('SOURCE_HASH_MISMATCH','Özgün belge SHA-256 doğrulaması başarısız.')
    return body


def _boxes_for_exact_quote(page, unit_text: str, quote: str, start: int, *, viewport: tuple[float,float,float,float] | None = None) -> tuple[HighlightBox, ...]:
    """Match ORIGINAL pdfplumber extraction with search index offsets, not OCR guesses.

    For duplicate quotes require a one-to-one positional mapping from all text
    occurrences to page.search() results. No first-hit heuristic is permitted.
    """
    if not quote or len(quote) > MAX_HIGHLIGHT_CHARS or unit_text[start:start+len(quote)] != quote:
        return ()
    matches_at = [m.start() for m in re.finditer(re.escape(quote), unit_text)]
    if len(matches_at) == 0 or len(matches_at) > MAX_MATCHES or start not in matches_at:
        return ()
    matches = page.search(re.escape(quote), regex=True, case=True, return_chars=True)
    if len(matches) != len(matches_at):
        return ()
    nth = matches_at.index(start)
    chars = matches[nth].get('chars') or []
    if not chars or len(chars) > 1400:
        return ()
    xoff,yoff,w,h = viewport if viewport is not None else (0.0,0.0,float(page.width),float(page.height))
    if w <= 0 or h <= 0:
        return ()
    # Boxes are in pdfplumber's *display-oriented* top-left space. Each char
    # is separately highlighted: no massive union spanning an adjacent line.
    boxes=[]
    for c in chars:
        a,b,d,e = (float(c[k]) for k in ('x0','top','x1','bottom'))
        a-=xoff; d-=xoff; b-=yoff; e-=yoff
        if not (-0.5 <= a < d <= w+0.5 and -0.5 <= b < e <= h+0.5):
            return ()
        boxes.append(HighlightBox(max(0.0,a)/w,max(0.0,b)/h,min(w,d)/w,min(h,e)/h))
    return tuple(boxes)


class SourceViewerService:
    def __init__(self, root: Path | str, search: SearchService | None = None):
        self.root = Path(root)
        self.search = search or SearchService(self.root)

    def open(self, chunk_id: int, *, page_number: int | None = None, scale: float = 1.25, highlight_query: str | None = None) -> SourcePreview:
        if not isinstance(chunk_id,int) or isinstance(chunk_id,bool) or chunk_id < 1:
            raise SourceViewError('INVALID_REFERENCE','Kaynak kimliği geçersiz.')
        # Resolves the current, nonarchived revision; proves unit offsets and SHA.
        result = self.search.source_passage(chunk_id)
        if result is None:
            raise SourceViewError('STALE_SOURCE','Kaynak sürümü veya metin doğrulanamadı.')
        result_before=result
        hit, full, start, end = result
        if not hit.verified or full[start:end] != hit.exact_quote:
            raise SourceViewError('QUOTE_MISMATCH','Arama pasajı özgün metinle eşleşmiyor.')
        body = _read_managed_bytes(self.root, hit)
        unit_no = hit.unit_number + 1
        if hit.kind != 'PDF':
            if page_number is not None and page_number != unit_no:
                raise SourceViewError('INVALID_PAGE','Metin belgesinde yalnız özgün paragraf açılır.')
            return SourcePreview(hit,unit_no,None,full,start,end,'TEXT_ONLY',(),None,None,
                'DOCX/TXT için yapay PDF sayfası veya geometrik kutu üretilmez.')
        if not 0.5 <= scale <= 2.0:
            raise SourceViewError('INVALID_SCALE','Görüntü ölçeği 0.5–2.0 aralığında olmalıdır.')
        if not body.startswith(b'%PDF-'):
            raise SourceViewError('INVALID_PDF','Arşivdeki belge PDF biçiminde değil.')
        # Untrusted PDF parsing, font decoding and rasterization NEVER run in
        # the Tk process.  A bounded worker returns only PNG bytes+geometry.
        try:
            with tempfile.TemporaryDirectory(prefix='.g07-view-', dir=self.root) as folder:
                directory=Path(folder)
                # No PDF copy: the worker opens the immutable object by hash.
                request={'root':str(self.root.absolute()), 'sha256':hit.sha256,
                         'full':full,'quote':hit.exact_quote,'start':start,
                         'unit_number':hit.unit_number,'page_number':page_number if page_number is not None else unit_no,
                         'scale':scale,'highlight_query':highlight_query}
                req=directory/'request.json'; reply=directory/'reply.json'; png=directory/'page.png'
                req.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
                try:os.chmod(req,0o600)
                except OSError:pass
                from ..runtime import worker_command
                cmd=worker_command('pdf',str(req),str(reply),str(png))
                from .sandbox import bounded_worker
                result=bounded_worker(cmd,timeout=18.0,memory_bytes=768*1024*1024,
                    cwd=self.root, output_path=reply)
                if not result.ok:
                    raise SourceViewError(result.code,result.message)
                if reply.stat().st_size>100_000 or not png.is_file() or not 0<png.stat().st_size<=30_000_000:
                    raise SourceViewError('WORKER_OUTPUT_LIMIT','PDF çıktısı sınırları aştı.')
                data=json.loads(reply.read_text(encoding='utf-8'))
                if data.get('sha256')!=hit.sha256 or data.get('page_number')!=request['page_number']:
                    raise SourceViewError('WORKER_IDENTITY_MISMATCH','PDF işçisi kaynak kimliğiyle uyuşmuyor.')
                count=data.get('page_count');size=data.get('image_size')
                if not isinstance(count,int) or count<1 or count>300 or not isinstance(size,list) or len(size)!=2 or any(type(n)!=int or n<=0 for n in size) or size[0]*size[1]>MAX_RENDER_PIXELS:
                    raise SourceViewError('WORKER_BAD_RESULT','PDF işçisi geçersiz sayfa ölçüsü döndürdü.')
                raw=data.get('boxes',[])
                if len(raw)>1400 or any(not isinstance(b,list) or len(b)!=4 or any(not isinstance(x,(int,float)) or not 0<=x<=1 for x in b) or b[0]>=b[2] or b[1]>=b[3] for b in raw):
                    raise SourceViewError('WORKER_BAD_RESULT','PDF koordinatları doğrulanamadı.')
                status=data.get('status')
                if status not in ('VERIFIED','UNVERIFIED_POSITION') or (status!='VERIFIED' and raw):
                    raise SourceViewError('WORKER_BAD_RESULT','PDF kanıt durumu geçersiz.')
                image=png.read_bytes()
                if not image.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise SourceViewError('WORKER_BAD_RESULT','Görüntü formatı doğrulanamadı.')
                # TOCTOU guard: the source can be changed by another process
                # during the render. Also recheck DB's current active revision.
                if _read_managed_bytes(self.root,hit)!=body or self.search.source_passage(chunk_id)!=result_before:
                    raise SourceViewError('STALE_SOURCE','İşleme sırasında belge veya kaynak sürümü değişti.')
                return SourcePreview(hit,request['page_number'],count,full,start,end,status,
                    tuple(HighlightBox(*b) for b in raw),image,tuple(size),data.get('detail',''))
        except SourceViewError:
            raise
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
            raise SourceViewError('PDF_VIEW_ERROR','PDF yerel alt süreçte görüntülenemedi.') from None
