# G00 — Kaynak gerçekliği, özellik sahipliği ve IP denetimi

**Kontrol tarihi:** 2026-10-16. **Durum:** G00 bu kaynak paketindeki inceleme kapsamında tamamlandı; GitHub depo/CI değiştirilmedi.

## Doğrulanabilir kaynaklar

- Önceki şartname ZIP: `LocalKnowledge_RAG_AI_Agent_Master_Markdown_ve_UI_Gorseller.zip`; 16 `screens/UI_XX.md`, `tasks/G00–G20.md`, `docs/03_DESIGN_SYSTEM.md`, UI-01 görseli ve iki kaynak Excel. Bu proje onları kod yazmaya yönelik normatif başlangıç referansı olarak kullanır.
- `LocalKnowledge-RAG_Gelistirme_Plani.xlsx` ve `LocalKnowledge-RAG_Asama2_Guncel.xlsx` içinde `LK-F001–LK-F024` ve `LK-S001–LK-S019` açıkça **Planlandı**. Bunlar çalışan kaynak kod kanıtı değildir.
- GitHub bağlantısı `seydivakkas/LocalKnowledge-RAG`: API 404/NOT_FOUND. Repo bulunamamış, özel erişim altında olabilir veya yok olabilir. **Mevcut commit, CI, PR veya çalışan kaynak ağacı doğrulanamadı.** Kod, mevcut repoya in-place değişiklik olarak değil, bağımsız iskelet olarak üretildi.
- Yerel kaynak / ekran maketleri kodlama referansı; tasarımda `128 belge` vb. sahte örnek sayıların yazılımdaki gerçek metrik olmadığı kayda alındı. G02'de veri yokken `—` gösterilir.

## Sahiplik matrisi: mevcut Excel özellikleri ile sonraki modüller

| Özellik kimliği | Sahip olacak servis | Şu paket |
|---|---|---|
| LK-F001–004 | `ingest/pdf.py`, `ingest/text.py`, `ingest/lifecycle.py` → DocumentService | Planlı G03 |
| LK-F005–006 | `chunk/normalizer.py`, `chunk/splitter.py` | Planlı G04 |
| LK-F007–009 | `index/fts.py`, `retrieve/bm25.py` | Planlı G05 |
| LK-F010–011 | `evidence/resolver.py`, `source/viewer.py` | Alan tipleri hazır; resolver planlı G06/G07 |
| LK-F012–013 | `ui/app.py`, `ui/routes.py`, `ui/components.py` | **G02 AppShell/route hazır; arama ve filtreler bağlı değil** |
| LK-F014 | `storage/db.py`, migration | Şema planlı G03; G01 type contract hazır |
| LK-F015 | `storage/backup.py`, `application/backup_service.py` | Planlı G08 |
| LK-F016 | `config.py`, testlerde offline invariant | G01/G02 dış ağ gerektirmeyen kod; uçtan uca offline kabul yapılmadı |
| LK-F017 | `benchmarks/evaluate.py` | Planlı G09 |
| LK-F018 | `packaging/` Windows PyInstaller + notices | Planlı G20; gerçek Windows kabul en son |
| LK-F019–023 | `llm/`, `rag/`, `embedding/`, evidence guard | Opsiyonel P1; devre dışı |
| LK-F024 | `plugins/ocr.py` | Opsiyonel P2; devre dışı |

## G00 güvenlik / telif / doğruluk kararı

1. **Tek kaynak kanıt yolu:** `DocumentRef → VersionRef(SHA-256) → PageRef(PDF) veya SpanRef(DOCX/TXT) → CitationRef`. G01 tipleri kaynak varlığını doğrulamaz, yalnız veri şeklini doğrular. Citation VERIFIED statüsü G07 EvidenceVerifier olmadan yoktur.
2. **Yanlış kaynak/kaydırılmış sayfa:** Kaynak uyuşmazlığında ileriki resolver fail-closed; hiç bağımsız PDF sarı-işaretleme kodu yazılmaz.
3. **Veri kaybı:** G03'ten itibaren migration transaction ve kaynak orijinal hash; G02 data yolunu yaratmaz, DB'yi değiştirmez.
4. **Offline:** G00–G02 hiçbir HTTP/socket çağrısı yapmaz; uygulamanın tüm sürümlerinin çevrimdışı çalıştığı henüz kanıtlanmadı.
5. **Lisanslar:** Projeye hak sahibi izni olmadan OSS LICENSE eklenmez; Windows EXE, fontlar, Python/Tcl/Tk REDIST ve üçüncü taraf hakları dağıtımdan önce ayrıca incelenir. Ticari durum HOLD.
6. **Gelecek özellikler:** P1/P2 modelleri veya index/backup işlevleri kullanılabilir gibi gösterilmez.

## G00 açık kanıtlar

- Depo aslında farklı isimde/özel ise kullanıcı erişimi veya kaynak dosyasıyla yeniden temel alınmalı.
- Gerçek Windows 10/11 paketleme, 125/150/200% DPI, klavye kabulü ve müşteri gerçek veri testleri henüz yapılmadı.
- Tam veri yaşam döngüsü, SQLite FTS, backup, retrieval, gerçek PDF/TXT/DOCX işlevleri G03 sonrası.
