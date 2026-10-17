# Bilgi mimarisi ve ekran navigasyonu

## Sol navigasyon
1. Ana Panel (`UI-01`, P0)
2. Belge Kütüphanesi (`UI-02`, P0)
3. Belge Ekle / İndeksle (`UI-03`, P0)
4. Arama (`UI-04`, P0; ürünün **birincil** eylemi)
5. Kaynak Görüntüleyici (`UI-05`, P0)
6. Kanıtlı Yanıtlar (`UI-06`, P1 opsiyonel)
7. Kanıt İnceleme (`UI-07`, P1 opsiyonel)
8. İş Kuyruğu (`UI-08`, P0)
9. Kaydedilmiş Aramalar (`UI-09`, gelecek/düzenleme önerisi)
10. Proje Koleksiyonları (`UI-10`, gelecek/düzenleme önerisi)
11. Kalite / Benchmark (`UI-11`, P0 geliştirme/ops dashboard)
12. Yedekleme ve Geri Yükleme (`UI-12`, P0)
13. Belge Sürüm Geçmişi (`UI-13`, P0)
14. Ayarlar ve Yerel Model (`UI-14`, P0 ayarlar / P1 modeller)
15. Taranmış PDF / OCR (`UI-15`, P2 opsiyonel)
16. Hakkında / Lisans / Yardım (`UI-16`, P0)

Navigasyon menüsünü solda uygun grupla; 16 öğeyi bir ekrana sıkıştırma. Basit: **Belgeler** (1–5,8,13), **Yapay Zekâ** (6,7,15; feature-gated), **Araçlar** (9–12), **Sistem** (14,16). Açık/kapalı grup konumu korunur. Görsel örneklerde düz menü vardır, gerçek UI'da hiyerarşi ve ekran küçülmesi önceliklidir.

## Ana kullanıcı yolculuğu
`UI-03 dosya içe al → UI-08 ingest/index işi → UI-02 indeks durumu → UI-04 sorgu ve FTS sonuç → UI-05 kaynak hash/sayfa/alıntı → UI-13 sürüm doğrulama`. P1 sonra `UI-04 retrieval → UI-06 taslak yanıt → UI-07 evidence checker → UI-05 özgün belge`.

## Global state
`workspace_id`, `selected_doc_id`, `selected_doc_version_sha`, `current_query`, `current_filters`, `highlight_ref`, `job_id`, `p0_index_ready`, `llm_enabled`, `ocr_enabled` tek UI state controller'da tutulur. Sayfalar arası gereksiz tekrar sorgusu yapma; stale version'ı doğru algıla.

## Boş durumlar
- Hiç belge yok: `Belge ekleyerek başlayın` tek CTA; sahte dashboard sonuçları yok.
- Sorgu boş: örnek sorgular **örnek etiketli**; query empty error yok.
- Sonuç yok: `Bu belgelerde eşleşme bulunamadı` ve filtreleri temizle.
- Model yok: AI sekmesi bilgisel placeholder olarak ancak statü açıksa, P0 arama aktif kalır.
- Kaynak yok/bozuk: stale/unaligned kaynak için güvenilir highlight düğmesi disabled ve gerekçe.
