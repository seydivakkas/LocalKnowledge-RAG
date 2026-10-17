# G08 — Python/native PDF bağımlılık lisans ve SBOM kapısı

**RELEASE STATUS: HOLD.** Bu belge hak onayı değildir; mevcut geliştirici ortamının paket metadata gözlemi ve yapılacaklar listesidir.

| Bileşen | Kaynak planda sürüm | Bu ortamda gözlenen metadata | Risk ve yapılacak iş |
|---|---|---|---|
| `pdfplumber` | 0.11.9 | LICENSE.txt | Python kaynak MIT/bağımlılık transitive izinleri ve pinned wheel SHA |
| `pdfminer.six` | transitif | PDF text native/crypto bağımlılık matrisi | transitif sürüm, ticari notices ve hash envanteri |
| `pypdfium2` / PDFium | 5.8.0 | BSD-3-Clause / Apache-2.0 ve Linux native `BUILD_LICENSES/` | **Windows wheel ve PDFium native** için tek tek build dependency notices, binary provenance/REDIST hakları, kaynak eşleştirme |
| `Pillow` | 12.3.0 | MIT-CMU | codec-native dağıtım notices ve Windows wheel envanteri |
| `python-docx` / `lxml` | 1.2.0/transitif | MIT metadata | lxml/libxml2/libxslt notices, Windows wheel sahipliği |
| `pypdf`, ReportLab, PyMuPDF | **test-only** | pypdf BSD; ReportLab BSD; PyMuPDF AGPL/commercial | **PyMuPDF'yi runtime veya ticari EXE içine yanlışlıkla paketleme**. Test/CI'de ayrı lisans ve dağıtım denetimi |
| `tkinter` / Tcl/Tk / CPython | OS / Python dağıtımı | runtime paketine bağımlı | Python, Tcl/Tk, OpenSSL, UCRT/VCRUNTIME native lisans ve Windows binary attestations |

- Doğru Windows sürümünde SBOM/CycloneDX ve tüm SHA-256 wheel + native DLL/PYD listesi üretilmeden **GO yok**.
- Bu Linux sanal ortamında görülen notices, **Windows EXE** veya ticari müşteriye yeniden dağıtım hakkı değildir.
- Proje sahibinin birinci taraf `LICENSE` kararı verilmedi; varsayılan **tüm haklar saklı** yaklaşımı sürer.
- Müşteri belge verileri ve PDF dosyaları bu pakete eklenmez; yalnız sentetik fixtures bulunur.
- Zorunlu ücretli API / bulut / abonelik yok.
