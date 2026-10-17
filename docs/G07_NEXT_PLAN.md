# G07 — Kanıt Tutarlılığı, Kaynak Konumu ve Sorgu Deneyimi (PLAN)

## Ön koşul
G06'nın SHA doğrulama, sayfa sınırları ve fail-closed sarı işaretleme kuralları korunacak. G04/FTS5 kaynak motoru ayrı kopya şeklinde tekrar yazılmayacak.

1. PDF konum motorunu CropBox != MediaBox için iki renderer arası bağımsız altın test seti ile doğrula. `UNVERIFIED_POSITION` durumunu yalnız bütün transform bileşenleri ölçülünce `VERIFIED` yap.
2. Yüksek uzunluklu ve sıkıştırılmış PDF'lerin parse+render işlemlerini sert sınırları olan alt sürece taşı; Windows Job Object / proses terminasyonu, bellek ve timeout denetimi geliştir.
3. FTS5 `SourceHit` için tam pasaj ile yalnız sorgu sözcüğünün ayırt edilmesini geliştir: kaynak alıntısını asla değiştirme, kullanıcıya tüm alıntının kanıtını gösterirken hedef terimi ayrı işaretle.
4. G05 Unicode/Türkçe, tekrarlı tablo metni, döndürülmüş ve kırpılmış sayfalar, 20 sayfalı/taranmış PDF karışık golden korpusu hazırla; yanlış sarı işaret sayısı sıfır kapısı ile test et.
5. UI-05 için kaydırma, zoom, klavye kısayolları, büyük font/DPI ve ekran okuyucu erişilebilirlik regresyonları ekle.
6. Aşama sonunda arama → orijinal belge → sarı kanıt → ileri/geri seyir → rapor bağlantısını çift yönlü kontrol et.
7. G04 100 belgeli yük testinin zaman aşımı kaynağını izole et; baseline bir kez ölçülmeden performans PASS deme.

Gerçek Windows kullanıcı kabulü ve ticari lisans onayı en son; dağıtım HOLD.
