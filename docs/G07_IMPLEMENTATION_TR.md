# G07 — Kaynak Konumu, PDF İzolasyonu ve Ölçek Teşhisi

**Durum:** Kaynak uygulama geliştirmesi ve sentetik Linux/Xvfb entegrasyon doğrulaması tamamlandı. Gerçek Windows, hukuki dağıtım ve güvenilmeyen gerçek PDF saldırı korpusu kabulü **HOLD**. Kaynak paketinde önceki G00–G06 bileşenleri korunur.

## 1. Teknik değişiklikler

| Sahip | Dosya | Sözleşme |
| --- | --- | --- |
| Görüntüleme orkestrasyonu | `src/localknowledge/viewer/service.py` | G05 `source_passage` doğrulaması -> özgün nesne SHA -> alt süreç -> sayfa PNG ve yalnız doğrulanmış kutular -> işlem sonu tekrar SHA+revision doğrulaması |
| PDF alt süreç | `src/localknowledge/viewer/worker.py` | PDFium ve pdfplumber yalnız worker'da; 0/90/180/270 derece ve CropBox→piksel viewport koordinat dönüşümü |
| Kaynak kotası | `src/localknowledge/viewer/sandbox.py` | Süre sınırı 18 s; PDF 50 MiB; sayfa piksel limiti 12 milyon; worker mem 768 MiB; Linux `RLIMIT_AS`, `RLIMIT_CPU`; timeout/crash güvenli reddi |
| Windows için hazırlık | `sandbox.py` | Win32 Job Object bellek kotası ve kill-on-close ilk kodu; **gerçek Windows derleme/Job Object kabulü yok**; başlatma–job'a bağlama aralığının küçük yarışı giderilmedi |
| Türkçe metin eşleşmesi | `worker._term_positions` | Karakter aralığını koruyan `İ→i`, `I→ı` dönüşümü; genel `re.IGNORECASE` kullanılmaz; çok-karakterli Unicode eşleme belirsizse kutu yok |
| UI-05 | `ui/source.py`, `ui/app.py`, `ui/components.py`, `ui/routes.py` | Gerçek alt süreç verisiyle kaynak; sayfa/zoom/kaydırma, canvas odaklı PageUp/PageDown/Alt+ok/Ctrl+/Ctrl−; durumlar ve G07 önizlemesi |

## 2. Kanıt politikası

- `VERIFIED`: SHA-256, sürüm, G04 özgün tam sayfa metni, G05 pasaj/karakter konumu, PDFium sayfa sayısı ve pdfplumber geometrisi uyuşur; eğer CropBox farklıysa PDFium MediaBox/CropBox, dönüş açısı ve pdfplumber rotasyonlu viewport bütün sınırları eşleşir. Bütün karakter kutuları viewport içinde kalır.
- `UNVERIFIED_POSITION`: herhangi bir eşitlik, PDF crop dönüşümü veya occurrence seçimi kanıtlanamaz. Sayfa okunabiliyorsa açılabilir, **sarı kutu çizilmez**.
- `TEXT_ONLY`: TXT/DOCX konumu paragraf/karakter aralığıdır, yapay PDF geometrisi üretilmez.
- Fiziksel sayfa 1 tabanlı; SQL `unit_number` 0 tabanlıdır. Cache, UI veya subprocess bu farkı gizleyip yanlış sayfaya atlamaz.
- Orijinal dosyanın byte'ları ve G05 indeks kayıtları değişmez. PDF üzerinde kalıcı annotation yazılmaz.

## 3. İki işleyiciyle bağımsız konum testi

Test yalnız izinli sentetik ReportLab PDF kullanır: bir sayfadaki yazı dört kez 0/90/180/270 dereceye döndürülür, asimetrik CropBox `(60,40,540,760)` kullanılır. `pypdfium2` raster viewport boyutları ve `pdfplumber` top-left haritalaması bağımsız `PyMuPDF` (`fitz`) kelime kutusuyla ±6 pt toleransta karşılaştırılır. Bu tolerans farklı kütüphanelerin font kutu ölçümünü kapsar; evrensel piksel-kusursuz doğruluk iddiası değildir. Kutu uyuşmazsa fail-closed.

`PyMuPDF` **test-only** bağımlılıktır; ticari uygulamaya paketlenmez ve farklı lisans koşulları ayrıca değerlendirilmeden runtime modülü olarak kullanılmaz.

## 4. Benchmark

Önceki G04 100 belgeli denemesi 120 saniyelik araç sınırına takıldığı için kapatılmamıştı. G07'de kademeli zamanlayıcıyla yeniden ölçüldü:

- 100 küçük sentetik TXT içe alma: **0,618 s**.
- 2 işçiyle bütün belge çıkarma+FTS5 indeksleme: **59,138 s**.
- Nihai durum: **100/100 COMPLETED**, özgün belge hash değişimi **0**.
- Ölçüm `docs/g07_100_document_phase_benchmark.json` ve ham günlük `docs/g07_100_document_benchmark_trace.log` içinde. Daha büyük PDF/DOCX, gerçek müşteri veri kümesi veya Windows performansı için sonuç çıkarılamaz.
- Darboğaz teşhisi: içe alma aşaması değil, her bir belge için yeni Python subprocess oluşturma + extraction/index döngüsü; darboğazın yüzde katkısı ayrıca profiler ile doğrulanmadan kesin süre kırılımı iddia edilmez. Uzun yaşayan, izolasyonlu worker yeniden kullanımı **ayrı ADR/ölçüm** gerektirir.

## 5. Testler ve ekran kanıtı

- `python -m unittest discover -s tests -v` altında 78/78 Linux sanal grafik regresyonu PASS (ilk mühendislik koşusu). `docs/test_g07_virtual_gui.log` gerçek logdur. Son etiket/kozmetik değişikliğinden sonra ikinci nihai regresyon ayrıca güncellenir.
- `tests/integration/test_g07_security_geometry.py`: 4 bağımsız CropBox/rotation koordinat testi, Türkçe I/i/İ/ı eşleşme, worker timeout, başarısız worker ve yanlış crop reddi.
- `docs/screenshots/g07_verified_cropped_pdf_source_linux_virtual_1440x900.png`: gerçek Tkinter; PDF'nin **kırpılmış** görüntüsü, `Koridor` teriminin yedi harfiyle sınırlı vurgusu.
- `docs/screenshots/g07_context_page_no_highlight.png`: kaynak dışında ikinci sayfa; sarı kutu sıfır.

## 6. Kapanış sınırları

- Sentetik görüntü ve retrieval regresyonu kanıtı, düşmanca hazırlanmış PDF'lere karşı tam sandbox garantisi değildir. Linux RLIMIT ve Windows Job Object yalnız kaynak sınırlarıdır, ağ/OS ayrıcalığı sandbox'ı değildir.
- Windows Job Object kodu gerçek Windows 10/11'de doğrulanmadı. Subprocess başlatımı ile Job Object'e bağlanma arasında küçük bir yarış vardır; bu çözülmeden güçlü tehdit modelinde kesin izolasyon PASS verilmez.
- PDFium native DLL ve codec bağımlılıkları, wheel SHA-256, SBOM ve yeniden dağıtım izinleri **HOLD**.
- 20 sayfalı gerçek Türkçe PDF/OCR karışık bağımsız korpus, ekran okuyucu, 125/150/200% Windows DPI ve çift yönlü rapor bağlantıları hâlâ açık.
- İlk birinci taraf `LICENSE` ve ticari kullanım sözleşmesi kullanıcı onayı olmadan verilmez.
- GitHub deposuna commit/PR gönderilmedi.
