"""Reproducible SYNTHETIC retrieval evaluation, not user/document pilot evidence.

Creates ten isolated local documents with fifty distinct subject labels; the
queries were authored alongside the corpus, so 100% is NOT a field accuracy
claim. Tracks recall@5, MRR@10, source exactness, median latency.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path
from localknowledge.ingest.service import IntakeService
from localknowledge.jobs.runner import Runner
from localknowledge.search.service import SearchService

TOPICS = [
 'koridor genişliği','yangın merdiveni','kaçış yönlendirmesi','cephe kaplaması','statik proje',
 'çatı izolasyonu','akustik yalıtım','sığınak düzenlemesi','ısı köprüsü','doğal havalandırma',
 'sürdürülebilir mimari','güneş paneli','yağmur suyu','peyzaj tasarımı','zemin etüdü',
 'taşıyıcı sistem','beton dayanımı','çelik konstrüksiyon','temel donatısı','mekanik tesisat',
 'havalandırma kanalı','iklimlendirme kontrolü','aydınlatma armatürü','kablo güzergahı','enerji verimliliği',
 'malzeme metrajı','birim fiyat','maliyet analizi','ihale dokümanı','teknik şartname',
 'tasarım revizyonu','ruhsat başvurusu','yapı denetimi','koruma alanı','tarihi doku',
 'imar sınırı','bina yüksekliği','otopark rampası','engelli erişimi','asansör kabini',
 'döşeme kalınlığı','kolon kesiti','kiriş detayı','pencere doğraması','cam geçirgenliği',
 'ısı pompası','atık yönetimi','şantiye güvenliği','yol kotu','parsel sınırı',
]
assert len(TOPICS) == 50


def evaluate(output:Path):
    with tempfile.TemporaryDirectory(prefix='lk-g05-eval-') as td:
        base=Path(td)
        root=base/'data';svc=IntakeService(root);search=SearchService(root)
        ids=[];fixture_hashes=[]
        for i in range(10):
            body='\n'.join(f'Sentetik doküman {i+1}: {topic} inceleme kaydı ve ilgili açıklaması.' for topic in TOPICS[5*i:5*i+5])+'\n'
            file=base/f'sentetik_{i+1}.txt';file.write_text(body,encoding='utf-8')
            ids.append(svc.import_document(file).document_id)
            fixture_hashes.append(hashlib.sha256(body.encode()).hexdigest())
        runner=Runner(root,poll_interval=.01)
        start=time.monotonic()
        for _ in range(10):
            if not runner.run_one():raise RuntimeError('Missing index job')
        elapsed_extract=time.monotonic()-start
        latencies=[];hits=[];ranks=[];citation_ok=0
        cases=[]
        for i,q in enumerate(TOPICS):
            t0=time.perf_counter();result=search.search(q,limit=10);latencies.append((time.perf_counter()-t0)*1000)
            rank=next((h.rank for h in result if h.document_id==ids[i//5]),None)
            hits.append(rank is not None and rank<=5)
            ranks.append(1/rank if rank else 0.0)
            if rank is not None:
                h=next(h for h in result if h.document_id==ids[i//5])
                d=search.source_passage(h.chunk_id)
                valid=d is not None and d[1][d[2]:d[3]]==h.exact_quote and h.verified
                citation_ok+=int(valid)
            else:valid=False
            cases.append({'query':q,'expected_document_id':ids[i//5],'rank':rank,'citation_ok':valid})
        metrics={'recall_at_5':sum(hits)/len(hits),'mrr_at_10':sum(ranks)/len(ranks),'citation_correct':citation_ok,
                 'queries':len(TOPICS),'source_documents':len(ids),'index_chunks':search.stats()['indexed_chunks'],
                 'extraction_seconds':round(elapsed_extract,3),'latency_ms_p50':round(statistics.median(latencies),3),
                 'latency_ms_max':round(max(latencies),3)}
        proof={'dataset':'synthetic author-aligned queries; NOT independent real corpus','metrics':metrics,
               'fixture_sha256':fixture_hashes,'results':cases,'commercial_release':'HOLD'}
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
        return metrics


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='docs/g05_50_query_synthetic_benchmark.json')
    args=p.parse_args()
    print(json.dumps(evaluate(Path(args.output)),ensure_ascii=False,indent=2))
