# G09 — Windows dağıtım sertleştirmesi ve bağımsız kabul kanıtları

**Durum:** MÜHENDİSLİK ADAYI / TİCARİ DAĞITIM HOLD. 2026-10-18.

## Kaynak gerçekliği

- G08 ZIP kaynak ağacı temel alındı; G00–G08 iş mantığı ve Tkinter korunur.
- GitHub deposu bu aşama başında boştu; GitHub'a yüklenen kod geçmiş G08 mühendislik önizlemesini ve G09 eklerini taşır.
- Bağımsız Windows CI kontrolü, `main` veya PR run URL'si ile ayrıca doğrulanmalıdır.

## G09 somut kod değişiklikleri

1. `src/localknowledge/runtime.py`: `worker_command()` ve `dispatch_private_worker()`.
   Kaynak çalışmada `python -m localknowledge.viewer.worker`, donmuş EXE'de
   `LocalKnowledge.exe --internal-pdf-worker` kullanılır. Metin çıkarma için
   `--internal-extract-worker` eşleniği kullanılır.
2. `launcher.py`: PyInstaller için kökten **mutlak importlu** tek giriş noktası.
3. `viewer/service.py` ve `jobs/runner.py`: eski `sys.executable -m` şablonları
   merkezi, deterministik worker yönlendirmesine bağlandı.
4. `.github/workflows/verify.yml`: Linux+Windows regresyon; Windows Job Object
   kontrolü, `--onedir` paketleme, packaged EXE sentetik PDF kanıt testi,
   kaynak SHA ve FTS5, hash manifesti ve license HOLD kapısı.
5. `packaging/windows_probe.py`: sentetik PDF oluştur, EXE ile içe al/çıkar,
   kaynaklı FTS5 araması yap, EXE PDF worker'ını çalıştır, restore kontrol et.
6. `packaging/release_inventory.py`: paketlenen EXE/DLL/PYD dahil her dosyanın
   SHA-256 ve byte boyutu; kurulu geliştirme ortamının dist-metadata snapshot'ı.
   **Binary→kaynak/build provaları ve lisans yetkisi bununla kanıtlanmaz.**
7. `tests/unit/test_g09_worker_entrypoint.py`: iki çalıştırma modu, özel rotalar,
   gerçek kaynak Python alt süreci, bilinmeyen rota reddi.

## Güvenlik politikası

- Kaynakların SHA256 ve orijinal metin offset'leri doğrulanmazsa sarı işaretleme yok.
- Job Object `CREATE_SUSPENDED → Assign → Resume` Windows'ta gerçekten çalıştığı
  zaman ve CI kanıtıyla kayda geçtiğinde sadece **CI Windows teknik denemesi** kabul edilir.
- Alt süreçler AppContainer / Windows ACL sandbox / internet izolasyonu garantisi
  sağlamaz. Windows Defender veya antivirüs dışlaması istenmez.
- G04 100 belge performans ve G07 sentetik PDF ölçümleri gerçek müşteri benchmarkı
  olarak genellenmez.
- Test-only PyMuPDF (AGPL/commercial) runtime'a dağıtılmamalıdır;
  workflow dahilinde paket ağacında isim taraması vardır. Bu tek başına
  üçüncü taraf lisans uyumluluğunun tamamlandığı anlamına gelmez.
- PDFium/pypdfium2, Pillow codec, lxml/libxml2/libxslt, Tcl/Tk, CPython,
  UCRT/VCRUNTIME ve Visual C++ REDIST listesi birebir kaynak, sürüm, wheel hash,
  Windows binary provenance ve ticari hak yönünden incelenmelidir.
- Teslim edilen GitHub kodu ≠ ticari yayın izni. Birinci taraf LICENSE belirlenmedi;
  müşteri sözleşmesi/prod release için hak sahibi onayı gerekir.

## GO / NO-GO

| Kapı | Kabul delili | Durum |
|---|---|---|
| G09-A Kaynak worker yönlendirme | yeni unit + mevcut source regression | Çalıştırılmış loga göre |
| G09-B Windows askıda Job Object | GitHub Actions job + log | CI bekleniyor |
| G09-C PyInstaller EXE worker | EXE üzerinden sentetik PDF + TXT worker | CI bekleniyor |
| G09-D Bağımsız PDF/20+ sayfa | lisanslı gerçek PDF ve altın bbox | BEKLİYOR |
| G09-E 100 belge ve geniş veri | kaynak/süre/RAM kontrollü bench | sentetik ölçüm var; üretim kabulü BEKLİYOR |
| G09-F Native lisans/REDIST | SHA+wheel, SBOM, review kaydı | HOLD |
| G09-G Windows gerçek son kullanıcı | bağımsız temiz Windows 10/11 | EN SON |

## G10 sonrası

Önce CI kaynaklı başarısızlıklar düzeltilir. Ardından kaynaklı kalite
benchmarkları, belge/arama UX, eksik P0/P1 ekranları ve varsa yerel RAG
modülleri ayrı fazlarla tamamlanır. *G09'dan sonra ürünün bitmiş olduğu iddia edilmez.*
