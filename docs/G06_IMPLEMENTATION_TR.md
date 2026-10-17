# G06 — Kaynak Görüntüleyici ve Doğrulanabilir PDF İşaretleme

## Sonuç ve kapsam

- G05 kaynak kimliği ve SQLite v3 korunmuştur; G04 `extracted_spans` ve G05 `search_chunks` / `search_fts` yeniden yazılmadı, yeni SQLite migration eklenmedi.
- `src/localknowledge/viewer/service.py`: `SourceViewerService`, güvenli `SourcePreview` ve `HighlightBox`. Özgün PDF değişmez `objects/<sha_prefix>/<sha>.bin` deposundan belleğe okunur; SHA-256 **render öncesinde tekrar** doğrulanır. `SearchService.source_passage()` güncel belge sürümünü, pasajı, sayfayı/paragrafı ve kesin karakter aralığını doğrular.
- `pdfplumber` G04 ile aynı metin çıkarma yöntemiyle tam sayfa metnini tekrar üretir. Metin uyuşmazlığı halinde geometrik kanıt yoktur.
- `pypdfium2` doğrulanmış **aynı byte dizisinden** PDF sayfasını PNG olarak rasterleştirir. Ayrı bir kaynak dosyası/URL açılmaz.
- PDF üstünde 0/90/180/270 dönmüş sayfalarda gösterim koordinatları, pdfplumber üst-sol koordinatı ile PDFium sayfa çıktı en/boy oranı birebir uyuşuyorsa dönüştürülür. Metin ve raster en/boy uyuşmazsa sarı işaretleme kapalıdır.
- Aynı pasajın tekrarlanan oluşumlarında eşleşen bütün konum sayıları ve pasaj başlangıç ofseti kontrol edilir; ilk sözcüğe körlemesine gidilmez.
- **Kullanıcı arama sorgusu varsa** yalnız sorgunun pasaj içindeki gerçek ve koordinatı ispatlanan sözcükleri sarı işaretlenir. Query yoksa doğrulanmış G05 pasajına işaretleme uygulanabilir; asla belgedeki her benzer sözcük rastgele seçilmez.
- CropBox != MediaBox: farklı yorumlanan viewport ofsetleri riski nedeniyle ilk sürümde **UNVERIFIED_POSITION** gösterilir; PDF görseli açılır ama sarı kutu çizilmez. Bu, CropBox desteğinin tamamlandığı anlamına gelmez.
- Başka PDF sayfasına geçildiğinde eski işaretleme taşınmaz. DOCX/TXT yapay PDF sayfası olmadan yerel metin ve paragraf aralığıyla açılır.
- UI: `UI-05 / RouteId.SOURCE`; aramada `Kaynak Sayfasını Aç`, ayrıca geriye dönük G05 `Yalnız Metin` seçeneği; bir önceki/sonraki sayfa, yakınlaştırma ve kaydırma; belge kimliği, kaynak durumu, hata kodu. İşleme worker thread içinde; Tk sadece ana iş parçacığında.

## Kesin vurgulama önkoşulları

1. `chunk_id` güncel ve arşivlenmemiş belgeye ait.
2. SHA-256 ve dosya boyutu, içerik adresli nesne yoluyla birebir uyuşuyor.
3. `unit_number` fiziksel PDF sayfası ve G04 metin aralığı G05 alıntısına birebir eşit.
4. Özgün PDF'den o anda pdfplumber ile çıkarılan sayfa metni depolanmış G04 tam sayfa metniyle birebir eşit.
5. OCR kullanılmadı: PDF metin katmanı net değilse otomatik sarı kutu çizilmez.
6. Crop/medya kutusu eşit ve pdfplumber sayfa ölçüsü ile PDFium görüntülenen sayfa ölçüsü uyuşuyor.
7. Metin araması kutu üretse bile seçilen pasajın doğru occurrence indeksinde olduğundan emin olunuyor.
8. Bounding rectangle sayfa sınırları içinde; şüpheliyse `UNVERIFIED_POSITION`.

**Anlamsal ayrım:** Kaynak SHA+metin eşleşmesi `verified source` demektir; `VERIFIED` geometrik durumundan ayrıdır. Sayfa görüntüsü açılması tek başına sarı kutu yetkisi vermez.

## Çalıştırma ve kanıtlar

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python -m localknowledge --gui
```

- Linux sanal Xvfb çalışma ortamında: **73/73 unittest PASS** (log: `docs/test_g06_linux_virtual_gui.log`).
- Sentetik örnek: `docs/screenshots/g06_verified_pdf_source_linux_virtual_1440x900.png`; gerçek Tkinter uygulaması, 7 karakterlik `Koridor` sorgu vurgusu.
- İkinci sayfa: `docs/screenshots/g06_context_page_no_highlight.png`; kaynak başka sayfada olduğundan **0** geometrik kutu.
- 0/90/180/270 rotasyonlu PDF sentetik testleri; tekil/tekrarlı pasaj, CropBox durumu, eski sürüm, kaynak bozulması, TXT metin kaynağı, hatalı kimlik, ölçek sınırı, PDF PNG header ve GUI akışı test edildi.
- G05 önceki arama ve indeks regresyonları aynı test turunda yürütüldü.

## Açık engeller ve riskler

- `G04` 100 belgeli geniş yük denemesi daha önce zaman aşımına uğradı; yeniden başarılı bir benchmark bulunmuyor.
- Yerel PDF kaynak görüntüleyicisi şu anda Python worker **thread** kullanıyor; düşmanca bozuk PDF'lere karşı bağımsız native PDF raster sandbox/subprocess, sert CPU/RAM/zaman kotası tamamlanmadı. Ticari dağıtım öncesi şart.
- CropBox != MediaBox için doğrulanmış koordinat dönüşüm algoritması ayrıca geliştirilmeli; v1'de sarı kutu yok.
- Tarama PDF/OCR kanıtı, PDF sayfası içindeki tablo hücresi eşlemesi, vektör annotation yazma G06 kapsamı değil. İşaretleme **görüntüleme katmanında** kalır, kaynak PDF'ye yazılmaz.
- Yerel performans / hafıza ölçümleri ve geniş PDF korpusu yok. Test verileri sentetik; kurumsal/kullanıcı belgelerinde doğrulama yapılmadı.
- Windows 10/11 temiz bilgisayar, Python'suz portable EXE, renderer native DLL/REDIST dağıtım lisans onayı ve bağımsız son kullanıcı kabulü **yapılmadı**.
- `pypdfium2==5.8.0` (native PDFium içeren wheel), `pdfplumber==0.11.9` ve `Pillow==12.3.0` çalışma gereksinimlerine girdi. Wheel SHA, bağımlılık / PDFium third-party notices, Windows native kaynağı ve ticari yeniden dağıtım hakları ayrıca araştırılmalı. Kullanıcıya lisans onayı verilmiş gibi gösterme.
- Yeni bir birinci taraf `LICENSE` verilmedi; fikrî haklar repo sahibindedir.
- Mevcut GitHub deposuna commit/PR yapılmadı. Bu bir kaynak kod teslim paketidir.

**Karar:** G06 sentetik entegrasyon PASS; bağımsız Windows ve ticari release HOLD.
