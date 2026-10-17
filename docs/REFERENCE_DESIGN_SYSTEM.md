# Tasarım sistemi — Windows desktop, işlev öncelikli

## Görsel hedef
`assets/ui_mockups/` içindeki 1600×960 PNG'ler ana ekranların referansıdır. **Tasarımın maksadı screenshot replikası değil; aynı hiyerarşide işlevsel UI'dır.** Modern, serinkanlı, açık içerik yüzeyi + koyu navigasyon, minimal ikon, erişilebilir metin.

| Token | Değer | Kullanım |
|---|---|---|
| `nav` | `#132238` | Sol menü |
| `nav-hover` | `#1B314D` | Hover |
| `nav-active` | `#2852A0` | Aktif sayfa |
| `primary` | `#246BDA` | Temel CTA ve link |
| `canvas` | `#F4F7FB` | Ana içerik zemin |
| `card` | `#FFFFFF` | Kart, tablo |
| `border` | `#E4EAF1` | İnce 1px ayırıcı |
| `text` | `#17253B` | Başlık/gövde |
| `secondary` | `#6A798E` | Yardımcı metin |
| `success` | `#139568` | GERÇEKTEN doğrulanmış kaynak/iş |
| `warn` | `#B86F1C` | Eski kaynak/OCR gerekli/şüpheli |
| `danger` | `#C84149` | Kaynak uyuşmazlığı/başarısız |

- Ana pencere: 1440×900 ideal; min 1100×720; 125/150/200% Windows DPI; `tk scaling` ve test.
- Sidebar 232–248 px; topbar 64–68 px; içerik margin 24–32 px; 8px spacing unit; kart radius 10–14 px.
- Font: cihazdaki `Segoe UI`, fallback `DejaVu Sans`; dosya paketleme hakkı olmadan font gömme. Başlık 21–25pt, body 10–11pt, caption 9pt; TR karakter net.
- Sol menüde aktif ekran görünür; P1/P2 sayfa implementation gate sağlanmadıysa "Opsiyonel / Yakında" etiketi ve disabled davranış; phantom features yok.

## Gerçek uygulama bileşenleri
`AppShell`, `SideNav`, `TopBar`, `SearchField`, `Breadcrumbs`, `MetricCard`, `StatusPill`, `EmptyState`, `ErrorState`, `LoadingState`, `DataGrid`, `Pagination`, `DocumentTile`, `SourceCard`, `CitationBadge`, `SourceHighlight`, `PdfPageCanvas`, `ModelStatusCard`, `ProgressJobRow`, `SettingsField`, `Toast`, `ConfirmDialog`.

## Etkileşim & erişilebilirlik
Tab odak sırası, `Enter` varsayılan eylem, `Esc` modal kapama, `Ctrl+F` arama, `Ctrl+O` belge ekleme, `Ctrl+L` kaynak listesi, `Ctrl+K` yerel hızlı arama (çakışma yoksa). Odak görünür. Durum yalnız renkle anlatılmaz. Liste büyükse sayfalama veya sanallaştırma; text ellipsis ile tooltip/ayrıntı; gereksiz animasyon yok. Windows OS pencere düğmeleri gerçek sistemde kalır.

## Hata metinleri
- `SOURCE_MISMATCH`: “Kaynak dosya değişmiş. Bu alıntı doğrulanamadı; yeniden indeksleyin.”
- `FTS_UNAVAILABLE`: “Yerel arama modülü kullanılabilir değil. SQLite FTS5 kurulumu doğrulanmalı.”
- `OCR_REQUIRED`: “Bu PDF taranmış olabilir. Metin aranamaz; isteğe bağlı OCR modülü gereklidir.”
- `MODEL_NOT_INSTALLED`: “Yerel AI modeli kurulmadı. Belge araması çalışmaya devam ediyor.”
- `UNSUPPORTED_VERSION`: “Bu veritabanı sürümü desteklenmiyor; veri değiştirilmedi.”
