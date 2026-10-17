# G04 — Asenkron belge metni çıkarma ve indeksleme iş kuyruğu (PLANLANDI)

1. `jobs/queue.py`: kalıcı iş kimliği, `(document_id, revision, sha256, task_type)` birleşik idempotency anahtarı, PENDING/RUNNING/FAILED/COMPLETED/INTERRUPTED durumları.
2. `jobs/runner.py`: UI'dan ayrı iş parçacığı, SQLite connection-per-thread, iptal noktaları, parser işlem izolasyonu, CPU/RAM/zaman üst sınırı.
3. `ingest/extraction.py`: yönetilen içerik bytes'ından PDF fiziksel sayfa bazlı metin, TXT gerçek offset, DOCX paragraph span; hata/sayfa sayısı farkında fail closed.
4. `storage/db.py`: v1→v2 veri kayıpsız migration; chunks/index sürümleri için şema sözleşmesi, yalnız transaction ve backfill; benchmark ve test fixtures.
5. `ui/jobs.py`: gerçek ilerleme, iptal, başarısız nedenleri, kesinti kurtarma. Dashboard indeks bekleyen sayacı gerçek kalıcı iş tablosuna bağlanır.
6. Yalnız işlem kanıtı: 100 belge + bozuk PDF, kaynak SHA değiştirme, 2 eşzamanlı thread, iptal/yeniden başlatma, UI yanıt süresi; testler henüz yürütülmedi.
7. G05 arama **ayrı**: SQLite FTS5 index, BM25 benchmark, sonuç→kaynak resolver. Aranabilir sonuç sayısını G04 metin extraction hazır olsa bile FTS5 kurulmadan göstermeyin.

Gerçek Windows kullanıcı kabulü ve ticari release son aşamada; şimdilik HOLD.
