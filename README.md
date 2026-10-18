# LocalKnowledge-RAG — G09 Mühendislik Sürümü

**Offline-first Windows öncelikli yerel belge kütüphanesi ve kaynaklı arama.** G00–G07 kaynak kodu üzerine G08 yedekleme/kurtarma, izole PDF worker Windows hazırlığı ve bağımsız PDF geometri testleri eklenmiştir.

**Durum:** G09 Linux + Windows otomatik mühendislik CI başarılı ([kanıt](https://github.com/seydivakkas/LocalKnowledge-RAG/actions/runs/39075582047)); gerçek Windows son kullanıcı kabulü, PDFium/native lisans/REDIST ve ticari dağıtım **HOLD**. Önceki G08 regresyonu: 95 test / 94 PASS / 1 Windows-only SKIP.

## Çalışan modüller

- PDF/DOCX/TXT güvenli kayıt, içerik adresli SHA-256 saklama, SQLite v3 sürümler ve eski belge geçmişi
- G04 ayrı süreçte metin çıkarma, iş kuyruğu ve kalıcı iş durumları
- G05 FTS5/BM25, özgün pasaj ve SHA-256 doğrulama
- G06/G07 PDFium orijinal PDF görüntüsü, temkinli CropBox/rotasyon işaretlemesi
- **G08 gerçek Yedekleme ekranı:** SQLite snapshot, geçmiş belge SHA nesneleri, hash manifestosu, yedek doğrulama, yeni veri klasörüne restore, arama indeksinin yeniden kurulması
- G08 Windows `CreateProcessW(CREATE_SUSPENDED) → Job Object → ResumeThread` **kodlandı fakat Windows doğrulanmadı**

## Geliştirme ve Linux otomatik test

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m localknowledge --gui
```

Python/paket indirme geliştirme ortamında gerekebilir; çalıştırılan uygulama çekirdeği bulut API istemez. Kullanıcıya çevrimdışı çalışan portable EXE **henüz üretilmiş kabul edilmez**.

## Yedek CLI

```powershell
python -m localknowledge --data-dir "C:\LK\Data" --backup-dir "D:\LK-Backup-001"
python -m localknowledge --verify-backup "D:\LK-Backup-001"
python -m localknowledge --restore-backup "D:\LK-Backup-001" --restore-to "C:\LK\Restored-001"
$env:LOCALKNOWLEDGE_DATA_DIR="C:\LK\Restored-001"
python -m localknowledge --gui
```

Var olan kaynak/veritabanı üzerine yazmak yasaktır. Yedek şifreli değildir; fiziksel depolama erişimi Windows ACL/BitLocker ve cihaz sahibi sorumluluğundadır.

## Kanıt ve devam planı

- [G08 uygulama raporu](docs/G08_IMPLEMENTATION_TR.md)
- [G08 yedek formatı ve bütünlük](docs/G08_IMPLEMENTATION_TR.md#yedek-formatı-ve-değişmezler)
- [Windows askıda worker mimari kararı](docs/G08_WINDOWS_JOB_OBJECT_ADR.md)
- [REDIST/lisans açık maddeleri](docs/G08_LICENSE_SBOM_HOLD.md)
- [G09 bağımlılık sırası](docs/G09_NEXT_PLAN.md)
- [Linux tam test günlüğü](docs/test_g08_linux_virtual_gui_FINAL.log)
- [Gerçek Tkinter G08 ekran görüntüleri](docs/screenshots/g08_backup_verified_linux_virtual_1440x900.png)

**Proje kaynak lisansı sahibi tarafından açıkça kararlaştırılmadı.** Bu paket lisans izni vermez; ticari dağıtım **HOLD**.

## G09 — Windows EXE ve native bağımlılık mühendislik kapısı (HOLD)

G09'dan itibaren `launcher.py` paketlenmiş Windows uygulamasının giriş noktasıdır.
Kaynak modda `python -m localknowledge`, donmuş EXE'de `LocalKnowledge.exe`
kullanılır. PDF sayfa worker'ı ve belge çıkarma worker'ı her iki giriş üzerinden
uygulama içi özel worker rotasına yönlendirilir; hiçbir durumda `LocalKnowledge.exe -m`
çalıştırılmaya kalkışılmaz.

- Windows otomatik CI: `.github/workflows/verify.yml` (kaynak testleri + Windows Job Object +
  gerçek `--onedir` EXE + sentetik kaynak→arama→PDF vurgusu→yedek/geri yükleme).
- `packaging/wheel_evidence.py` kurulu runtime kapanışını ve Windows wheel adaylarının SHA-256, NOTICE yolları ve paketlenmiş native byte eşleşmelerini kaydeder; **ticari lisans izni üretmez**.
- `packaging/release_inventory.py` paketlenen dosyaların SHA-256 ve native listesini
  raporlar, **hak doğrulaması yapmaz**.
- `docs/G09_IMPLEMENTATION_TR.md` tamamlanan işler, kalan kaynak/hukuk/Windows
  kabulleri, gerçek kanıt linkleri için tek referanstır.
- İlgili kaynak lisans kararı verilmedi. Projeye açık kaynak `LICENSE` eklenmedi.
- Repo README veya CI yeşil olsa bile **ticari release veya Windows son kullanıcı
  kabulü otomatik ONAYLANMAZ**.

Windows aday EXE yapımı (geliştirici bilgisayarı/CI, üretim lisans izni değil):

```powershell
py -3.13 -m pip install -e ".[test]"
py -3.13 -m pip install pyinstaller==6.22.3
py -3.13 -m PyInstaller --noconfirm --clean --onedir --windowed --name LocalKnowledge --collect-all pypdfium2 --collect-all pdfplumber --collect-all pdfminer launcher.py
py -3.13 packaging/windows_probe.py dist/LocalKnowledge/LocalKnowledge.exe evidence/windows_portable_probe.json
py -3.13 packaging/release_inventory.py dist/LocalKnowledge evidence/native_file_inventory.json
```

> Görseller, lisanssız model ağırlıkları, gerçek müşteri belgeleri ve kurumsal
> veritabanları GitHub'a yüklenmez.
