# G08 — Güvenli Yedekleme / Kurtarma, Windows PDF Worker ve Bağımsız PDF Korpusu

**Durum:** G08 mühendislik uygulaması ve Linux sentetik regresyonu tamamlandı; **Windows bağımsız kabulü ve ticari dağıtım HOLD**.

## Kaynak gerçeği

- Kaynak: G07 ZIP'i, G00–G07 kod ve veri modelleri değiştirilmeden devralındı.
- SQLite şeması **v3 korunmuştur**. İkinci bir `documents`, `versions`, `search_chunks` sistemi yazılmadı.
- 17 Ekim 2026 Linux Xvfb: `python -m unittest discover -s tests -v` → **95 test; 94 PASS, 1 SKIP (Windows-only)**. Kanıt: `docs/test_g08_linux_virtual_gui_FINAL.log`.
- Ekran görüntüleri: `docs/screenshots/g08_backup_*_linux_virtual_1440x900.png`; gerçek Tkinter ekranı, sentetik TXT belgesi.
- Gerçek Windows 10/11 x64, imzalı EXE ve gerçek müşteri korpusu **test edilmedi**.

## Kodlanan bileşenler

| Katman | Dosya | Davranış |
|---|---|---|
| Yedekleme | `src/localknowledge/storage/backup.py` | SQLite snapshot + tüm geçmiş SHA-256 belge nesneleri + manifest; eksik/bozuk yedek reddi |
| Restorasyon | aynı | Yalnız **yeni ve mevcut olmayan** dizine; önce nesneler, en son SQLite; job RUNNING→INTERRUPTED; FTS5 tamamlanan span'lardan tekrar kurulur |
| Servis | `application.py` | Tek `BackupService`, arayüz ve CLI aynı kod yolunda |
| CLI | `cli.py` | `--backup-dir`, `--verify-backup`, `--restore-backup ... --restore-to ...` |
| UI | `ui/backup.py` | Yedek oluştur, doğrula, başka konuma geri yükle; arka plan worker, hata kodu ve net durum; ilerlerken çıkış engeli |
| Windows subprocess | `viewer/sandbox.py` | `CREATE_SUSPENDED` + sınırları kurulmuş Job Object + `ResumeThread`; atama başarısızsa durdur |
| Gerçekçi negatif fixture | `tests/integration/test_g08_pdf_corpus.py` | 24 sayfa, PDFium/pdfplumber bağımsız PyMuPDF kontrolü; doğrulanamayan CropBox/rotasyonda konum verilmez |
| Koruma testleri | `tests/integration/test_g08_backup.py` | İndeks geri kurma, geçmiş sürümler, kaynak byte koruma, hash/manifest/path tamper, çift hedef ve kesinti |

## Yedek formatı ve değişmezler

`localknowledge.offline.backup/1` manifestosu SQLite dosyasının ve SHA-256 ile adlandırılmış tüm `objects/` üyelerinin **hash + boyut** kaydını tutar. Yedek klasörü exclusive `mkdir` ile oluşturulur, dosyalar yeni adla yazılır ve **`manifest.json` son yayınlanır**. Kesintide manifesti olmayan klasör geçersizdir.

Kopya alınırken SQLite `Connection.backup` kullanılır; kaynak nesneler kopya öncesi ve sonrası hash kontrolünden geçer. Manifest ile SQLite `versions.object_relpath` birebir doğrulanır. `integrity_check`, `foreign_key_check`, FTS5 `integrity-check` ve indexed chunk sayısı incelenir.

**Güvenlik sınırları:** Yedek şifrelenmez; güvenli cihaz profili veya BitLocker gibi işletim sistemi koruması gerekir. Aynı dizine/var olana geri yükleme yoktur. Geri yükleme **çalışan veri dizinini otomatik değiştirmez**; `LOCALKNOWLEDGE_DATA_DIR` ile yeni dizin seçilmesi ayrıca kullanıcı işlemidir. 5 GiB/toplam ve 100.000 sürüm mühendislik guard'ı vardır. Tam çok süreçli locking, depolama kotası/DACL, network share semantiği ve imzalı paket kabulü açık tutulur.

## Windows PDF worker: tasarım ve gerçeklik

Eski `subprocess.Popen` → `AssignProcessToJobObject` akışında, atamadan önce parser'ın çalışabileceği yarış aralığı vardır. Yeni tasarım native `CreateProcessW(CREATE_SUSPENDED)` ile **askıda** başlatır, Job Object'e bellek/aktif süreç ve kill-on-close limitlerini uygular, ancak sonra `ResumeThread` çağırır. Her hata kodu kapalıdır. Windows'ta `subprocess.Popen`'ın process handle'ı yanlışlıkla thread handle gibi kullanılmaz.

Bu bir **Windows AppContainer**, ağ izolasyonu, PDF virüs taraması veya güvenlik kanıtı değildir. Windows-only regresyonu Linux'ta **SKIP** oldu; gerçek Windows üzerinde Job Object nesting, timeout, memory quota, frozen EXE subprocess ve güvenli kapanma test edilmeden `PASS` denemez. Detay: `docs/G08_WINDOWS_JOB_OBJECT_ADR.md`.

## 24 sayfalık PDF değerlendirmesi

24 yapay sayfada pdfplumber / PDFium / bağımsız PyMuPDF ölçümleriyle 0/90/180/270 rotasyon, alternatif CropBox ve yinelenen kelime ele alındı. Belirli **asimetrik kırpma + rotasyon** kombinasyonlarında iki ayrıştırıcının görünür bölge koordinatları birbirini doğrulamıyor; `_viewport` **None** döndürüyor, sarı kutu bastırılıyor. Rotasyonun metin yönünü çevirebildiği ayrıca ölçüldü; karakter ofsetlerinin güvenilir olmadığı koşullarda uydurma kaynak vurgusu üretilemez.

Bu deney bağımsız **parser** kıyaslamasıdır, bağımsız gerçek dünya PDF korpusu yerine geçmez. Kötü amaçlı gerçek PDF örnekleri, taranmış/karma 20+ sayfa doküman ve Windows font/DPI kabulü açık.

## CLI örnekleri

```powershell
python -m localknowledge --data-dir C:\LocalKnowledge\Data --backup-dir D:\LK-Backup-20261017
python -m localknowledge --verify-backup D:\LK-Backup-20261017
python -m localknowledge --restore-backup D:\LK-Backup-20261017 --restore-to C:\LocalKnowledge\Restored-20261017
$env:LOCALKNOWLEDGE_DATA_DIR="C:\LocalKnowledge\Restored-20261017"
python -m localknowledge --gui
```

## GO / NO-GO

| Kapı | Durum |
|---|---|
| Linux G00–G08 sentetik regresyon | **PASS (94/94 çalıştırılan, 1 Windows-only SKIP)** |
| Yerel SQLite + SHA nesneleri + FTS5 restore | **PASS (sentetik)** |
| Gerçek Tkinter yedekleme ekranı | **PASS (Linux Xvfb)** |
| Windows suspended Job Object koruması | **IMPLEMENTED / NOT VALIDATED** |
| Windows 10/11 Python'suz EXE, Windows DPI ve gerçek kullanıcı | **HOLD** |
| Bağımsız gerçek PDF, PDFium/native wheel REDIST ve lisans | **HOLD** |
| Ticari müşteri teslim/sözleşme | **HOLD** |

**G09'e geçiş önerisi:** Önce Windows native güvenlik ve paketleme kanıtlarını ayrı CI kapısına bağla, ardından gerçek korpus/PDF kaynak doğrulaması ile arayüz erişilebilirliğini iyileştir. Nihai kullanıcı kabulü en son.
