# G03 — SQLite Belge Kaydı, Güvenli İçe Alma ve Gerçek Kütüphane

**İşlem:** G03; öncesi G00–G02 AppShell. **Durum:** Kod uygulanmış; Linux sentetik otomatik testleri PASS. **Gerçek Windows kullanıcı kabulü:** YAPILMADI. **Ticari dağıtım:** HOLD.

## 1. İşlev sahipliği

| İş | Gerçek modül | UI | Durum |
|---|---|---|---|
| SQLite şema, sürüm denetimi, FK | `storage/db.py` | arka plan | G03 kodlandı |
| Kayıt/sürüm/alias ve arşiv | `documents/repository.py` | `UI-02`, `UI-13` | G03 kodlandı |
| SHA-256 içerik deposu | `ingest/service.py` | `UI-03` | G03 kodlandı |
| PDF imzası/sayfa metadata | `ingest/parsers.py` | `UI-02` | G03 kodlandı; OCR yok |
| TXT satır/aralık metadata | `ingest/parsers.py` | `UI-02` | G03 kodlandı; sayfa uydurulmaz |
| DOCX paragraf metadata | `ingest/parsers.py` | `UI-02` | G03 kodlandı; Word sayfası uydurulmaz |
| Yerel dashboard sayaçları | `application.py` | `UI-01` | G03 kodlandı |
| Gerçek belge DataGrid, filtre, kontrol | `ui/documents.py` | `UI-02` | G03 kodlandı |
| UI dosya seçme, thread, sonuç bildirimi | `ui/documents.py` | `UI-03` | G03 kodlandı |
| İş kuyruğu/checkpoint | `jobs/` | `UI-08` | **G04, henüz yok** |
| Aranabilir metin, FTS5/BM25 | `chunk/`, `index/`, `retrieve/` | `UI-04` | **G05, henüz yok** |
| Exact span citation, source highlight | `evidence/` | `UI-05/07` | **G06–G07, henüz yok** |
| Yedek/restore | `storage/backup.py` | `UI-12` | **G08, henüz yok** |

## 2. Veri sözleşmesi

- SQLite şema sürümü **1**, `PRAGMA foreign_keys=ON`, `quick_check`, `foreign_key_check`. Sürümü bilinmeyen veya gelecekteki veritabanı reddedilir; şema sıfırlanmaz. G03 yeni bir veritabanı kurar, bilinmeyen mevcut DB otomatik migrate edilmez. Piyasaya çıkmadan önce migration sırası tanımlanacak.
- `documents`: kararlı UUID tabanlı belge kimliği, belge türü, güncel sürüm, arşiv bayrağı.
- `versions`: `document_id`, artan `revision`, gerçek kaynak SHA-256, byte, içerik-adresli nesne yolu; eski sürüm korunur.
- `source_paths`: bir kaynak dosya yolunu belge kimliğine bağlar; aynı kaynak yolu değişip yeniden içe alınırsa yeni sürüm oluşturulur. Aynı içerik farklı yol ise yeni belge değil alias olur.
- `page_metadata`: yalnız PDF için **gerçek fiziksel sayfa numarası**. `extracted_chars=0` değeri bu aşamada metin çıkarılmadığını ifade eder.
- `paragraph_metadata`: DOCX/TXT paragraf veya satır offset kayıtları; DOCX/TXT için sahte sayfa numarası oluşturulmaz.
- `import_events`: CREATED, NEW_VERSION, DUPLICATE, ALIAS, ARCHIVED, RESTORED olaylarının yerel kaydı. Bu kayıtların silinmezliği kriptografik imzalı hukukî denetim özelliği değildir.

## 3. Kaynak güvenliği ve hata davranışı

1. Kaynak 50 MiB üzerinde veya boşsa reddedilir; izin verilen uzantılar PDF/DOCX/TXT. Uzantı ile gerçek PDF/OpenXML header uyuşmuyorsa reddedilir.
2. Kaynak bytes önce özel staging kopyasına alınır, SHA-256 hesaplanır ve kaynak dosyanın tekrar hash'lenmesiyle kaynağın işlem süresince değişmediği teyit edilir. Kaynak dosya ne silinir ne yeniden adlandırılır ne de üzerine yazılır.
3. PDF sayfa üst sınırı 300; DOCX ZIP toplam açılmış boyut, girdiler ve aşırı sıkıştırma için üst sınırlar mevcuttur. Şifreli veya bozuk PDF/DOCX otomatik güvenli kabul edilmez.
4. Hash yolu yalnız hex karakterlerinden oluşturulur. Atomik, no-overwrite hardlink oluşturma işleminden sonra SQLite transaction ile kayıt bağlanır. Kayıt başarısızsa bu çağrıda yeni oluşturulan nesne temizlenir.
5. `verify()` yönetilen nesnenin beklenen boyut ve SHA-256 bütünlüğünü yeniden kontrol eder. **Bu kontrol sadece arşiv kopyasını doğrular, disk üzerindeki orijinal kullanıcı dosyasının hâlen aynı olduğuna dair sürekli izleme garantisi değildir.**
6. Kullanıcıya ulaşan hata mesajları belge içeriğini veya PDF parser traceback'lerini sızdırmaz. Veritabanı default `%LOCALAPPDATA%/LocalKnowledge` altında; kaynak dosya yolları SQLite içinde yalnız yerelde bulunur, şifreli değildir.

**Açık güvenlik işi:** PDF/DOCX parser'larının düşük yetkili süreçte CPU/RAM/zaman sınırıyla yalıtılması henüz yapılmadı. ZIP/magic ve boyut sınırı bu riski tamamen ortadan kaldırmaz. Yerel depoda şifreleme henüz yok; Windows izinleri/BitLocker gerekebilir. Erişilemeyen hedefte atomic hardlink kullanılamıyorsa işlem güvenli şekilde başarısız olur, sessiz dosya kopyası fallback yapılmaz.

## 4. UI davranışı

- Ana Panel: **Kayıtlı Belge**, **Belge Sürümü**, **İndeks Bekleyen** yalnız gerçek veritabanından sayılır; **Aranabilir Bölüm** `—` olur. G04 kuyruk öncesi `İndeks Bekleyen` mevcut aktif belge sayısıdır; kaydedilmiş kuyruk sayısı değildir.
- Belge Kütüphanesi: isim filtresi ve tür filtresi SQL parametreleriyle; aktif/arşiv kayıtları, sayfalama, sürüm geçmişi, arşivleme/geri alma ve arşivde tutulan SHA doğrulaması. Filtre ismi içinde `%`, `_` gibi LIKE karakterleri literal ele alınır.
- Belge Ekle: sistem dosya seçicisi, arka plan worker; her dosyanın başarı/başarısızlığı gerçek kayıttan gelir. Ana Tk thread bloklanmaz; kritik içe alma sürerken normal pencere kapatma uyarılır.
- Belge Sürümleri: immutable geçmiş kayıtları ve seçilen sürümde SHA doğrulaması.
- Arama/indeksleme/RAG/OCR sayfaları henüz bağlantısız veya devre dışı; yanlışlıkla çalışıyor gibi davranmaz.

## 5. Test kanıtı ve kapsam

- `python -m unittest discover -s tests -v`: **38 test**, Linux Xvfb sanal grafik oturumunda başarıyla çalıştırıldı (G03 test günlüğü).
- Gerçek PDF 2 sayfa metadatası, DOCX 2 gerçek paragraf kaydı, TXT UTF-8, alias/versiyon, arşiv/restore, tekrar ekleme, hash tamper, bozuk uzantı, future SQLite schema, CLI, Tk ekran geçişi ve UI'dan çalışan gerçek asenkron içe alma.
- Headless testte GUI sınıfı uygun görüntü olmadığı için atlanır; **Linux Xvfb’de GUI testleri çalıştırılıp geçti.** Windows 10/11'de son kullanıcı mouse/klavye davranışı, gerçek malform PDF fuzz, yüksek hacimli bellek/CPU ve Windows dosya sistemi hardlink kabulü henüz test edilmedi.
- Ekran görselleri `docs/screenshots/g03_*` içinde **gerçek Tkinter** penceresinden, yalnız sentetik test belgeleriyle elde edildi; Figma/ImageGen maketi değil.

## 6. G04 devralma sözleşmesi

G04 indeksleme iş kuyruğunu yalnız mevcut `documents` ve `versions` kayıtlarına referanslayarak ekleyecek. `IndexJob(document_id, revision, sha256, state, progress)` tipinin kaynak sürüm SHA'sına bağlı olması zorunludur. G04 ekranı gerçek worker durumunu göstermeden etkinleşmeyecek. G05 FTS5/BM25 için sayfa/metin extraction ve page-aware chunk eklenmesi ayrı iş olacak; G03'te çıkarılmayan PDF metinleri indekslenmiş varsayılmayacak. Eski sürüm arşiv kopyaları ve veritabanı şeması migration testleri olmadan değiştirilmez.
