# LocalKnowledge-RAG — Agent devralma ve G09 sonrası kurallar

- **Dil:** GitHub README, PR, issue, UI, rapor ve yorumlar Türkçe. Teknik
  Python isimleri, API/JSON keys değiştirilmez.
- Kaynak sırası: `README.md` → `docs/G09_IMPLEMENTATION_TR.md` → `docs/G09_NEXT_PLAN.md`.
- G00–G08 kodunu yeniden yaratma; sürümlü SQLite/FTS5 ve immutable SHA kaynağını koru.
- Müşteri verisi, API anahtarı, satılabilir olmayan model ağırlığı ve PDF örneğini repoya alma.
- Kanıt kimliği, sayfa, özgün metin span ve koordinat doğrulanmamışken sarı
  işaretleme, geçerli kaynak, destekli yanıt veya PASS gösterme.
- `launcher.py` donmuş EXE'nin tek girişidir; iki worker da `runtime.py` üzerinden.
- Her PR: gerçek testler, platform, commit SHA, kanıt çıktısı ve kalan HOLD'ları içersin.
- Windows CI teknik doğrulaması son kullanıcı Windows kabulüyle karıştırılmayacak.
- PDFium/Pillow/lxml/native REDIST, model lisansları ve birinci taraf kaynak lisansı
  incelemesi tamamlanmadan Release/Commercial = HOLD.
- Son aşamada bağımsız Windows 10/11 offline PC ve gerçek veri kabulü yapılacak.
