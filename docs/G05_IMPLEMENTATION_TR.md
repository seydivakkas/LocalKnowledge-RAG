# İşlem G05 — Kaynaklı FTS5/BM25 arama ve kanıt bağlantısı

**Durum: G05 MÜHENDİSLİK ADAYI / OTOMATİK TEST PASS; kullanıcı/Windows kabulü BEKLEMEDE.**

## Gerçek kod değişiklikleri

| Bileşen | Sorumluluk | Dosya |
|---|---|---|
| Sürümlü şema | v1→v2→v3 migrations; FTS5 ve trigger bütünlüğü | `src/localknowledge/storage/db.py` |
| İndeks | Sayfa/paragraf sadık ≤780 karakter chunk + 100 overlap; transactional FTS; yeniden oluşturma | `src/localknowledge/search/index.py` |
| Arama | Güvenli sorgu, parametreli tür/tarih filtreleri, BM25, arşiv ve eski sürümü çıkarma | `src/localknowledge/search/service.py` |
| Kaynak | SHA-256 kontrollü nesne + DB kaynak sürümü + G04 özgün birim metni+offset eşleşmesi | `src/localknowledge/search/service.py` |
| Kuyruk | `JobQueue.complete()` metin ve indeks sonucunu **tek SQLite transaction** ile yayımlar | `src/localknowledge/jobs/queue.py` |
| Belge kütüphanesi | Kayıtlı / çıkarılmış / gerçekten aranabilir ayrımı | `src/localknowledge/documents/repository.py`, `ui/documents.py` |
| Kullanıcı ekranı | Gerçek arama, filtreler, sonuca git, yerel kaynak pasajını vurgula | `src/localknowledge/ui/search.py`, `ui/app.py` |
| CLI | `--search`, `--kind`, `--limit`, `--rebuild-search`, doğru G05 smoke çıktısı | `src/localknowledge/cli.py` |

## İş kuralları

1. G04 extraction tamamlanmadan G05 arama sonucu üretilemez. Kaynak SHA/versiyon geçerliyse indekslenir; işlem dışına çıkan eski sürüm ve arşivlenmiş belge görünmez.
2. `search_chunks.original_text` G04 `extracted_spans` üzerinde **değiştirilmeden saklanan özgün karakter aralığıdır**; indeksin metni normalize edebilmesi bu gösterim metninin değiştirilmesine izin vermez.
3. `SourceHit.verified` yalnızca **kayıtlı nesnenin SHA-256**, boyut ve güvenli yol kontrolü, güncel sürüm, G04 birim/offset metninin birebir eşleşmesini belirtir. PDF yeniden parse edilerek metin bağımsızca doğrulanmadığı için "hukukî kanıt kesin" veya "PDF koordinatı doğrulandı" denemez.
4. Kaynak sekmesine girerken tekrar doğrulanır; yanlış eşleşmede kaynak penceresi açılmaz.
5. `unicode61 remove_diacritics 2` Türkçe ek/çekim/kök bulma için özel morfolojik analiz değildir; noktalı/noktasız i ve sözcük eşleştirmeleri bağımsız Türkçe korpusta ölçülecektir.
6. BM25 skoru kesinlik yüzdesine çevrilmez. Skor sıralama içindir, kullanıcıya sonuç sayısı ve gerçek referans sunulur.
7. G05 arayüzündeki sarı vurgulama G04 çıkarılmış **metin pasajı** içindedir; PDF raster koordinatları/bbox G06+ kapsamındadır.
8. PDF sayfa numarası 1 tabanlıdır, DOCX/TXT **gerçek sayfa** iddiası yoktur; paragraflar ve orijinal metin aralıkları gösterilir.
9. Eski `versions`, `import_events`, `extracted_spans` içerikleri silinmez. Görünür FTS indeksinin eski satırları temizlenebilir çünkü yeniden üretilebilir bir türevidir.
10. Ağ/ücretli servis gerekmez; sentetik fixture'dan başka kullanıcı belgeleri pakete alınmaz.

## Doğrulama kanıtı

- `tests/integration/test_g05_search.py`: SHA bozulması, sürüm değiştirme, arşivleme/geri alma, FTS enjeksiyonuna karşı parametrik sorgu, satır aralıkları, PDF fiziksel sayfa ve DOCX paragrafı, v2→v3 backfill, FTS yeniden inşa ve hayalet kayıt silme.
- `tests/ui/test_shell.py`: gerçek Tkinter arama–sonuç–kaynak diyaloğu altında sentetik demo veri.
- `docs/test_g05_linux_virtual_gui.log`: 59 test PASS, sanal Xvfb. Son çalıştırmada Tkinter finalizer uyarısı görülmedi; kullanıcı kabulü değildir.
- `docs/g05_50_query_synthetic_benchmark.json`: 50 sentetik sorgu; Recall@5=1,00; MRR@10=1,00; 50/50 bağlantı. **İçerik ve sorgular birlikte hazırlanmıştır; genelleme yapılamaz.**
- `docs/g05_cli_verified_flow.json`: içe alma → process → search → stats → yeniden indeksleme → tekrar search. Gerçek SQLite ve özgün SHA kanıtları, sentetik dosyayla.
- `docs/screenshots/g05_*.png`: gerçek Tkinter (Linux sanal GUI).

## Açık kapılar

- 50+ **bağımsız etiketlenmiş** gerçek/sentetik karışık Türkçe kullanıcı sorusu; retrieval pilot hedefi ayrı raporlanacak. 50 sentetik benchmark bu kapıyı kapatmaz.
- Mevcut G04 100 doküman performans testi TIMEOUT, yeniden ölçülmemiştir.
- SQLite indeks büyük boyutta bellek ve gecikme benchmarkı; ticari dağıtımın her şeyi tamamlandığına dair iddia yok.
- Windows PyInstaller worker çağrısı, izolasyon/ölçüm, gerçek ekran ve Windows kullanıcı kabulü **en son**.
- Font, PyInstaller, Python bileşenleri ve tüm üçüncü taraf lisanslarının ticari dağıtım denetimi: HOLD.
- Repo bulunmadığı için GitHub PR/CI gerçekleştirilmedi.

## Sonraki aşama

G06: PDF sayfa görseli, güvenilir koordinat dönüşümleri ve doğrulanabilir birebir vurgulama; DOCX/TXT paragraf/karakter aralığı aynı kaynak sistemi ile açılmalı. Yerel model/OCR zorunlu olmamalı.
