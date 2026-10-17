# G01–G02 — Gerçek kodlama devri ve kabul kanıtı

**Yazılım sürümü:** `0.1.0.dev0` · **Kapsam:** G00/G01/G02 · **Şimdiki ticari karar:** HOLD

## G01 gerçek kod

`pyproject.toml`, `src/localknowledge/__init__.py`, `__main__.py`, `cli.py`, `config.py`, `application.py`, `domain/models.py`, `domain/errors.py`:

- `python -m localknowledge --version` çalışır; Tk/SQLite DB açılmaz.
- `--smoke` standart SQLite `fts5` kabiliyetini ölçer, JSON'da `index_ready=false`, `data_connected=false`, `status=shell-only` açık yazar. Bu test **gerçek indeks testi değildir**.
- Tiplendirilmiş immutable `DocumentRef`, `VersionRef`, PDF için `PageRef`, yalnız DOCX/TXT için `SpanRef`, `SearchHit`, `CitationRef`. Gerçek chunk/kanıt doğrulaması daha sonraki görevlerindir.
- `DashboardService.summary()` veri katmanı bağlı değilken `available=False` ve `None` sayaçlar döndürür; sahte `0` veya demo dosya eklemez.
- Dış bağımlılık yok; stdlib Tk/SQLite kullanılır. Python ile dağıtım hakları ayrı bir kapıdır.

## G02 gerçek kod

`ui/theme.py` kaynak tasarımın `nav=#132238`, `primary=#246BDA`, `canvas=#F4F7FB` değerlerini, Windows Segoe UI fontunu; `ui/components.py` navigasyon, metrik, kart, boş durum ve action row; `ui/routes.py` 16 benzersiz rotayı; `ui/state.py` saf router/ViewStatus; `ui/app.py` gerçek Tk penceresini sağlar.

- 1100×720 minimum; başlangıç 1440×900; OS native window control.
- Ctrl+1 → Ana Panel, Ctrl+L → Kütüphane, Ctrl+O → İçe Alma, Ctrl+F/K → Arama. G02'de planlı rotalar yalnız dürüst bilgilendirme sayfası açar.
- 16 rotadan yalnız Ana Panel ve Hakkında **gerçek G02 içerik**. 9 P0 ekranı bilgi amaçlı placeholder'dır; 5 ileri/öneri ekran disable'dır.
- Main thread'e blocking ingest/index/OCR eklemek yasaktır. İleride UI→Controller→ApplicationService→Repository yönü izlenir.
- `assets/reference/UI_01_Ana_Panel.png` 1600×960 tasarım referansıdır; `docs/screenshots/` gerçek Linux sanal display Tk ekran görüntüsüdür. Bunlar Windows kabul kanıtı değildir.

## Reproduction / current results

```bash
PYTHONPATH=src python -m localknowledge --smoke
PYTHONPATH=src python -m unittest discover -s tests -v
xvfb-run -a -s '-screen 0 1600x1000x24' env PYTHONPATH=src python -m unittest discover -s tests -v
```

- Yerel işletim sistemi: Linux; Python 3.13.5; Tk 8.6; SQLite 3.46.1.
- Headless: 15 unit tests PASS, 6 GUI testin `setUpClass` bölümü display olmadığı için SKIP (toplam 15 başarı, 1 atlanan test grubu).
- Sanal display: **21/21 tests PASS**, `docs/screenshots/g02_home_linux_virtual_1440x900.png` ve 1100×720 çıktılarını görüntüleyip minimum boyutu karşılaştır.
- 125/150/200% fiziksel Windows DPI ve ekran okuyucu erişilebilirliği: `NOT_RUN`, doğru kodlanmış görünüm garantisi değil.

## G03 API bağlama sözleşmesi

`DashboardService` arayüzünü koruyarak gelecekte `SqliteDashboardService.summary()` yaz. `DashboardSnapshot.available=True` yalnız DB açık ve indeks durumu doğrulandığında; `None` metrikleri uydurma `0` yapma. `AppServices` içine `document`, `ingest`, `search`, `jobs` eklenecek; Tk kodu doğrudan SQLite/FTS veya filesystem'e dokunmayacak.

İlk G03 PR kabulü: DB migration, gerçek belge CRUD, tekrar yüklemede SHA idempotency, sayfa/anchor kaydı, sembolik ve gerçek korpus testleri, UI-02/UI-03 bağları; Windows gerçek kullanıcı kabulü yine en son.
