"""Private bounded PDF renderer entrypoint. Do not import Tkinter or expose HTTP."""
from __future__ import annotations
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys


def _viewport(page,pdfpage):
    """Map pdfplumber rotated MediaBox coordinates onto PDFium cropped raster.

    The raw crop box is independently read through PDFium, and translated into
    the rotated top-left coordinate system. If any boundary disagrees, fail
    closed instead of inventing a rectangle.
    """
    media=tuple(map(float,pdfpage.get_mediabox()))
    crop=tuple(map(float,pdfpage.get_cropbox()))
    rot=int(pdfpage.get_rotation())%360
    mx0,my0,mx1,my1=media;cx0,cy0,cx1,cy1=crop
    if rot==0: expected=(cx0-mx0,my1-cy1,cx1-mx0,my1-cy0)
    elif rot==90:expected=(cy0-my0,cx0-mx0,cy1-my0,cx1-mx0)
    elif rot==180:expected=(mx1-cx1,cy0-my0,mx1-cx0,cy1-my0)
    elif rot==270:expected=(my1-cy1,mx1-cx1,my1-cy0,mx1-cx0)
    else:return None
    pw,ph=map(float,pdfpage.get_size())
    pl_crop=tuple(map(float,page.cropbox))
    pl_media=tuple(map(float,page.mediabox))
    if not all(math.isfinite(x) for x in (*expected,*pl_crop,*pl_media,pw,ph)):
        return None
    if not (pw>0 and ph>0 and all(abs(x-y)<0.6 for x,y in zip(expected,pl_crop))):
        return None
    if abs(expected[2]-expected[0]-pw)>.6 or abs(expected[3]-expected[1]-ph)>.6:
        return None
    if abs(page.width-(pl_media[2]-pl_media[0]))>.6 or abs(page.height-(pl_media[3]-pl_media[1]))>.6:
        return None
    return (expected[0],expected[1],pw,ph)


def _apply_limits():
    if os.name=='posix':
        import resource
        # PDFium/other native components must run in a memory-limited child.
        resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(14,14))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))


def _turkish_key(s: str) -> str:
    # Fixed-length and locale-explicit: do not use re.IGNORECASE (I/i/İ/ı
    # collapse incorrectly) or casefold (some chars expand and shift offsets).
    return ''.join('ı' if c == 'I' else 'i' if c == 'İ' else c.lower() for c in s)


def _term_positions(source: str, term: str):
    key = _turkish_key(source)
    needle = _turkish_key(term)
    if len(key)!=len(source) or len(needle)!=len(term) or not needle:
        return []  # ambiguous offset mapping -> no yellow
    result=[];i=0
    while True:
        found=key.find(needle,i)
        if found<0:return result
        result.append((found,found+len(term)))
        i=found+1


def _render(req,png_path:Path)->dict:
    import pdfplumber
    import pypdfium2 as pdfium
    from .service import _boxes_for_exact_quote,MAX_RENDER_PIXELS,MAX_HIGHLIGHT_CHARS
    root=Path(req['root']);sha=req['sha256']
    if not isinstance(sha,str) or len(sha)!=64 or any(x not in '0123456789abcdef' for x in sha):
        raise ValueError('invalid digest')
    path=root/'objects'/sha[:2]/(sha+'.bin')
    if any(x.is_symlink() for x in (root,root/'objects',path.parent,path)):
        raise ValueError('unsafe path')
    if not path.is_file() or path.stat().st_size>50*1024**2:raise ValueError('missing file')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha or not raw.startswith(b'%PDF-'):
        raise ValueError('source mismatch')
    with pdfplumber.open(io.BytesIO(raw)) as pl,pdfium.PdfDocument(raw) as pd:
        count=len(pd)
        if not 1<=count<=300 or len(pl.pages)!=count:raise ValueError('page mismatch')
        page_num=req['page_number'];ref_num=req['unit_number']+1
        if type(page_num)!=int or not 1<=page_num<=count or not 1<=ref_num<=count:
            raise ValueError('page out of bounds')
        scale=req['scale'];pg=pl.pages[page_num-1];render_page=pd[page_num-1]
        width,height=render_page.get_size()
        if not .5<=scale<=2 or width*height*scale*scale>MAX_RENDER_PIXELS:
            raise ValueError('render limit')
        boxes=();status='UNVERIFIED_POSITION';detail='Sayfa gösterildi; koordinat doğrulanamadı.'
        if page_num==ref_num:
            try:
                full=req['full'];quote=req['quote'];start=req['start'];viewport=_viewport(pg,render_page)
                if viewport is not None and pg.extract_text()==full and full[start:start+len(quote)]==quote:
                    q=req.get('highlight_query')
                    if q is None:
                        boxes=_boxes_for_exact_quote(pg,full,quote,start,viewport=viewport)
                    elif isinstance(q,str) and 0<len(q)<=240:
                        from ..search.service import _WORDS
                        terms=set(_WORDS.findall(q))
                        collected=[]
                        for term in sorted(terms):
                            if len(collected)>1000:break
                            for a,b in _term_positions(full[start:start+len(quote)],term):
                                pos=start+a
                                collected.extend(_boxes_for_exact_quote(pg,full,full[pos:start+b],pos,viewport=viewport))
                        boxes=tuple(collected[:1000])
            except (ValueError,KeyError,TypeError,IndexError):boxes=()
            if boxes: status='VERIFIED';detail=f'{len(boxes)} karakter özgün sayfa ve CropBox ile eşleştirildi.'
        bitmap=render_page.render(scale=scale)
        img=bitmap.to_pil().convert('RGB')
        if img.width*img.height>MAX_RENDER_PIXELS:raise ValueError('rendered pixel overflow')
        img.save(png_path,format='PNG')
        return {'sha256':sha,'page_number':page_num,'page_count':count,'image_size':list(img.size),
                'boxes':[[b.left,b.top,b.right,b.bottom] for b in boxes],
                'status':status,'detail':detail}


def main()->int:
    if len(sys.argv)!=4:return 2
    try:
        _apply_limits()
        req=Path(sys.argv[1]);reply=Path(sys.argv[2]);png=Path(sys.argv[3])
        if req.stat().st_size>1_500_000:return 2
        data=json.loads(req.read_text(encoding='utf-8'))
        out=_render(data,png)
        reply.write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
        return 0
    except Exception:return 2

if __name__=='__main__':raise SystemExit(main())
