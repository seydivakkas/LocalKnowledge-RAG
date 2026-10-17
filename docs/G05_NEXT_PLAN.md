# G05 — Kaynaklı FTS5 / BM25 arama (SONRAKİ AŞAMA)

- G04 `extracted_spans` satırları yalnız kaynak SHA, sürüm, birim ve offset ile ilişkilidir. Mevcut G03 deposunu veya G04 kuyruğunu yeniden yazma.
- SQLite FTS5/`unicode61`; tokenizer Türkçe sınırlamalarını benchmark ile ölç; metin normalizasyonunda orijinal Unicode pasajı değişmez sakla.
- Bölütleme fiziksel PDF sayfasını geçmez; DOCX ve TXT için paragraf/karakter aralığına sadık kal. `ChunkRef -> SourceRef` kanıtı bulunamıyorsa sonuç linki yok.
- İndeks güncellemesi `COMPLETED` işlerinin en güncel doküman sürümü üzerinden transaction ile yapılır. Eski belgenin stale chunkları aranabilir kalamaz.
- Güvenli FTS query escaping, BM25 sıralama ve kaynak türü/tarih filtreleri ekle. BM25 skorunu yüzde doğruluk puanı diye gösterme.
- 50+ Türkçe sorguda Recall@5, MRR@10 ve citation link bütünlüğü için bağımsız fixture/ölçüm.
- G04 performans/Windows process izolasyonu açık maddeleri tamamlanmış diye işaretleme.
- Ticari sürüm ve temiz Windows GUI kabulü en son. **HOLD**.
