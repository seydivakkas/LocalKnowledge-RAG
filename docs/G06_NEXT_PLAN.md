# G06 — Kaynak görüntüleyici ve özgün belgeye çift yönlü bağlantı (PLAN)

- G05'in `SourceHit` ve `source_passage` protokollerini değiştirmeden `SourceViewerService` oluştur. G05 metin penceresi geçici bir güvenilir kanıttır; PDF sayfa rasteri yerine geçmez.
- PDF `document_id`, sürüm SHA, 1 tabanlı fiziksel sayfa ve özgün metin alıntısı çözülerek `pypdfium2` veya izinli eşdeğer ile PDF'nin **değişmez arşiv kopyasını** aç. OCR olmayan PDF için koordinat bulma `pdfplumber` character/bbox eşleme ile doğrulansın.
- PDF rotation, cropbox, mediabox, DPI, page transform testi; bbox yanlış veya belirsizse **sarı geometrik highlight üretme** ve kullanıcıya `UNVERIFIED_POSITION` göster.
- DOCX/TXT için sahte PDF sayfası oluşturma; paragraf numarası + karakter aralığı bağları ile yerel metin görüntüleyicisini kullan.
- Önce belge SHA ve sürüm kontrolü, sonra PDF render ve kaynak metin alıntısı eşleştirme; yanlışlıkta kaynak ekranı açılmaz.
- Sentetik 0/90/180/270 rotasyon, çok sayfalı ve aynı sözcüğün çok kez geçtiği PDF'lerle golden koordinat testi; yanlış highlight sıfır olmak zorunda.
- Yeni ekranı `UI-05 SOURCE` rotasına ekle; G05 eski pasaj görünümü veri kaybı yaşamadan geri dönülebilir kalır.
- Kayıtlı belgelerde dış ağ, ücretli API, zorunlu AI/OCR olmayacak. Otomatik sentetik regresyonlar geliştirme sırasında; gerçek Windows kabulü en son, release HOLD.
