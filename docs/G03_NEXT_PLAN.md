# G03 — İnceleme ve ilk gerçek belge servis entegrasyonu (sıradaki mühendislik işi)

## Başlangıç durumu

G00–G02: Tk AppShell ve tür sözleşmeleri uygulandı; 16 rota tanımlı, 2 ekran G02 içeriği, 9 P0 placeholder, 5 P1/P2/öneri disabled. Henüz SQLite dosya yaşam döngüsü ve FTS indeksi yok.

## Küçük iş paketleri

| Sıra | Teslim | Servis ve UI | Kabul |
|---|---|---|---|
| G03-01 | Şema v1 | `storage/db.py`, migration | `PRAGMA user_version`, FK, rebuild, invalid v/s fail closed |
| G03-02 | Hash tabanlı registry | `documents/repo.py`, typed document/version | Aynı SHA tekrar eklenince mükerrer sürüm yok |
| G03-03 | PDF/TXT/DOCX parser | `ingest/`, izinli dependencies | sayfa/offset konumu gerçek ve kaynak değişmez |
| G03-04 | UI-02 Belge Kütüphanesi | `ui/controllers/documents.py` + reusable DataGrid | Gerçek DB sayfalama/filtre; stale source flag |
| G03-05 | UI-03 İçe Alma | `ui/controllers/ingest.py` + async worker | büyük dosyada Tk bloklanmaz, hata dosya bazında |
| G03-06 | Dashboard servisi | `SqliteDashboardService.summary()` | sayaçlar SQL'e eşit; eski `—` yalnız gerçekten unavailable olduğunda |

`G04` indeksleme kuyruğu, `G05` FTS5/BM25, `G06/07` kaynak doğrulama ancak bağlı kod ve sentetik testle etkinleştirilir.

## Güvenlik

- File size/page/time budget, fail-closed parser, encrypted PDF and ZIP bomb behavior explicitly tested. Unknown format never fallback-parsed as TXT by suffix only.
- Original source hash checked at ingestion start/end and whenever evidence opened. User file never overwritten.
- G03'te PDF kaynak önizleme ve exact bbox visualization tamamlanmış sayılmaz.
