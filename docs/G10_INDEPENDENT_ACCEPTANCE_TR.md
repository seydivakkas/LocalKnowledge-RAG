# G10 — Bağımsız kaynak doğrulama ve ürün tamamlama

**Durum: MÜHENDİSLİK GELİŞTİRMESİ / G10 BAĞIMSIZ KABUL HOLD.**

## Kesin öncelikler

1. **G10-01 Windows iş kuyruğu:** Kaynak ve paketlenmiş EXE CI üzerinden PDF/DOCX/TXT iki işçili karma yük; iptal/yeniden deneme; SQLite durumları; kaynak SHA bütünlüğü; tekrar çalıştırılabilir JSON kanıtı. \`benchmarks/g10_queue_soak.py\` sentetik testtir, gerçek müşteri Windows kabulü değildir.
2. **G10-02 İzinli gerçek belge korpusu:** En az 20 farklı PDF/DOCX, çok sayfalı, tarama/rotasyon/CropBox, Türkçe belge varyasyonları. Sadece açık izinli veya kullanıcının kendi belgeleri; hassas veri GitHub'a aktarılmaz. Her dosya için hak/izin kaydı, SHA-256, gerçek sayfa/alan altın işareti ve iki bağımsız etiketleyicinin uyuşmazlık çözümü gerekir. Veri kümesi sağlanmadıysa **HOLD**.
3. **G10-03 Kaynak/kanıt doğruluğu:** PDF sayfa referansı, PDFium–pdfplumber koordinat uyumu, özgün metin/offset, belgelerin güncellenmesi, yanlış kaynak vurgusunun engellenmesi. Altın etiketli kaynakları otomatik değerlendir. Hedef, **yanlış doğrulanmış sarı kutu = 0**; güvenilmez eşleşmede \`UNVERIFIED_POSITION\` ve görüntüleme serbest, vurgulama kapalı.
4. **G10-04 Türkçe retrieval kalitesi:** En az 50 bağımsız, önceden etiketli Türkçe sorgu; ≥15 kaynaksız soru; Recall@5, MRR@10, kanıt doğruluğu, cevaplanamayan sorularda yanlış pozitif oranı, p50/p95 gecikme. Sentetik g05 sonuçları gerçek başarı değildir. \`safe_query\` Türkçe I/İ/ı/i morfoloji sorunları ayrı ölçülür.
5. **G10-05 Eksik UI:** 16 rota için gerçek/planlı/kapalı matrisi; tamamlanmamış modüller çalışıyormuş gibi gösterilmeyecek. Türkçe, 1100×720 DPI ve klavye yolu.
6. **G10-06 Opsiyonel yerel RAG:** Yalnız kaynaklı BM25 P0 kabulünden sonra isteğe bağlı llama.cpp/model. LLM kapalıyken tüm temel işlevler çalışmalı. Model lisansı, offline kurulum, benchmark, prompt-injection/halüsinasyon ve çekimserlik kabulü ayrı.

## Bağımsız değerlendirme veri sözleşmesi

Yerel klasörde \`corpus/\`, \`manifest.json\` ve \`judgments.jsonl\` kullan. Manifest: \`key\`, göreli \`path\`, dosya \`sha256\`, \`rights\` alanları; her hak beyanı incelemeye tabidir. Soru kaydı: \`id\`, \`query\`, \`expected=ANSWERABLE|NO_EVIDENCE\`, \`relevant=[document_key...]\`. Gold etiketleri motor sonuçlarından türetilmemeli. Kaynak sayfa/offset doğrulaması için ayrıca ayrı değerlendirici işaretlemesi gereklidir. Veri veya izin kanıtı eksikse pilot GO kararı verilemez.

## G10-01 test sözleşmesi

- En az 12 sentetik karma biçimli belge Windows-2022 CI üzerinde iki işçiyle tamamlanmalı.
- Her \`index_jobs\` işi \`COMPLETED\`, \`attempt=1\`, kaynak ve kanıt hash eşleşmesi ile doğrulanmalı.
- Kuyruğa başlamadan \`CANCELLED → PENDING\` geri dönüşü test edilmeli; gerçek çalışan süreç iptali, çöküş ve ikinci GUI örneği ayrı genişletme senaryolarıdır.
- Tek dosyadaki hata diğerini bozmamalı; bunlar için ayrı bağımsız testler beklenir.
- Süre kaydı ölçümdür; tek CI zamanına bakarak üretim performans iddiası kurulmaz.

## GO/NO-GO

| Kapı | Kanıt | Durum |
|---|---|---|
| G09 iki işletim sistemi CI | GitHub Actions güncel ana dal | PASS (G09 sentetik) |
| G10-01 iki işçili karma kuyruk | Yeni Windows/ Linux CI JSON ve başarı | CI çalışmasına bağlı |
| G10-02 izinli bağımsız belgeler | Kaynak izinleri ve altın etiketler | HOLD |
| G10-03 kesin kaynak/konum | Yanlış pozitif sıfır ve bağımsız değerlendirici | HOLD |
| G10-04 Türkçe arama | Sorgu başına kaynak ve metrik raporu | HOLD |
| G10-05 arayüz tamamlama | Görsel ve işlev doğrulama | AÇIK |
| G10-06 yerel RAG | Opsiyonel; model-lisans-performans | AÇIK |
| Son kullanıcı Windows 10/11 | Temiz gerçek kullanıcı cihazı | EN SON |
| Ticari dağıtım ve REDIST | İlk taraf lisansı, binary hakları, SBOM | HOLD |
