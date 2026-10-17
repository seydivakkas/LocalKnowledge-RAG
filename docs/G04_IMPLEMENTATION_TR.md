# G04 — Kalıcı Metin Çıkarma Kuyruğu / Mühendislik Raporu

**Durum:** Sentetik otomatik doğrulaması geçti; gerçek Windows kabulü **yapılmadı**. Ticari dağıtım **HOLD**.

## G03 üzerinde değişiklikler

- `storage/db.py` — SQLite `user_version=2`, veri kaybı olmadan v1→v2 migration. `index_jobs` ve `extracted_spans` tabloları. G03 `documents`, `versions`, özgün nesne deposu ve immutable revision kayıtları korunur.
- `jobs/queue.py` — v2 işlem durumları, SQLite transaction içinde tekil `(document_id, revision, sha256, task_type)` anahtarı; atomik claim, durumlar, tekrar deneme, eski sürümün geçersiz kılınması, tam sonuç yayımlama.
- `jobs/runner.py` — ana Tk thread'ini bloke etmeyen worker thread + ayrı parser subprocess. Gerçek sayfa/paragraf ilerlemesi, iptal, deadline, kaynak SHA doğrulaması, tek işlemde span commit. SQLite bağlantıları her çağrıda yenidir.
- `jobs/worker.py` — fiziksel PDF sayfaları, DOCX paragrafları, TXT gerçek karakter ofsetleri. 5 milyon karakter, 300 sayfa, ZIP/DOCX sınırları, en çok 120 saniye; Linux subprocess için RLIMIT_AS / CPU. Çıktılar özel geçici JSON üzerinden aktarılır. **Windows Job Object / bellek kotası ve paketlenmiş EXE worker yeniden giriş noktası henüz test edilmedi.**
- `ingest/service.py` — yeni belge sürümünde kuyruk kaydı aynı SQLite transaction içine eklenir; eski sürüm ve tekrar içe alma idempotent davranır.
- `documents/repository.py`, `application.py` — aktif metin bekleyen sayısını hesapla; FTS sayaçları `None` kalır. Kütüphanede metin durumu göster.
- `ui/jobs.py`, `ui/app.py` — 16 rotadan `UI-08 İş Kuyruğu` gerçek ekrana dönüşür, yenile, iptal, retry, ilerleme ve hata kodu; Tk widget erişimi yalnız ana thread.
- `cli.py` — `--list-jobs`, `--process-next`, `--cancel-job`, `--retry-job`.

## Yaşam döngüsü

```text
G03 CREATE / NEW_VERSION
        |
        v
    PENDING  ── claim ──> RUNNING ── tam SHA+revizyon ve birim sayısı kontrolü ──> COMPLETED
        |                    |    |   
        |                    |    └──> FAILED (elle retry)
        |                    ├───────> CANCELLED (elle retry)
        |                    └───────> INTERRUPTED (başlangıç kurtarması, elle retry)
        └── CANCELLED

Yeni belge sürümü geldiğinde eski bekleyen işler SUPERSEDED olur.
```

**G05 ile ayrım:** `extracted_spans` bir arama indeksi DEĞİLDİR. FTS5 / BM25, chunking ve citation resolver **yoktur**. PDF tarama OCR desteği de yoktur; görüntü tabanlı sayfalardan boş metin çıkması başarılı metin kurtarma kanıtı değildir.

## Gerçek test kapsamı

- `python -m unittest discover -s tests -v`: **49/49 PASS**, Linux Xvfb sanal grafik ekranında, sentetik fixture.
- PDF: iki fiziksel sayfadan metin; DOCX: paragraf sıralaması, sahte sayfa numarası yok; TXT: orijinal Unicode ve karakter ofseti.
- v1→v2 veri kayıpsız migration; SHA idempotency, eski sürüm yarışı, bozuk özgün nesne güvenlik kilidi, pending cancel/retry, crash recovery, iki worker ile 12 dosyada çift claim olmaması.
- 1440×900 ve 1100×720 **gerçek Tkinter ekran görüntüleri** `docs/screenshots/g04_*.png` dosyalarında.
- **100 belge / iki worker deneyinin ilk çalıştırılması 120 saniyelik araç süre sınırında kesildi. PASS kanıtı yoktur.** Ölçeklenebilirlik kapısı açık; bağımsız profilleme ve ölçülen hedefler gerekir. Test dosyası `docs/g04_100_document_benchmark.py`, kısmi sonuç başarısı ilan edilmez.

## Açık kabul riskleri

1. Gerçek Windows 10/11 üzerinde subprocess ve `--windowed` PyInstaller worker komutu; Windows Job Objects ile RAM/CPU üst sınırı ve çocuk süreç öldürme.
2. İnceleme yokken G03'ün orijinal PDF preflight işlemi hâlâ uygulama süreç/thread'i içinde. Güvenilmeyen parser ilk aşamadan itibaren ayrı izolasyona alınmalı.
3. 100 belgeli performans ölçümü, disk dolması, çok büyük dosya, kaynak erişim izinleri, beklenmeyen kapanma ve sistem güç kesintisi senaryoları.
4. İki eşzamanlı **uygulama instance** için sahiplik/lease mekanizması bu sürümde yok. Uygulama tek bilgisayar/tek aktif instance varsayımıyla tasarlandı.
5. Windows işletim sistemi üzerinde doğrulama, lisans/SBOM, üçüncü taraf codec ve müşteri kabulü en son.

## Sıradaki G05 (yeni bir PR/paket)

SQLite FTS5, gerçek metin offsetlerini kaybetmeyen sayfa/paragraph-aware chunk, Unicode NFC, BM25, filtreler, exact SHA/citation resolver ve 50 sorguluk retrieval benchmark. G05 tamamlanmadan ekranda güven puanı veya alıntı vurgusu üretme.
