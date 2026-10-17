# G09 — Kaynak Kabulü ve Windows Dağıtım Sertleştirmesi (son kullanıcı kabulü değil)

1. **G09-00:** G08 kaynak ve bağımlılık haritasını koru. Kurulu runtime ile test-only bağımlılıkları ayır; PyMuPDF test-only kalsın.
2. **G09-01:** Native Windows worker `CreateProcessW suspended → Job → resume` kodunu izole Windows CI'da test et; başarısız Job assignment/timeout/min RAM; tüm job handle'larının kapandığını doğrula. **Temiz müşteri Windows kabulü en son**.
3. **G09-02:** Package frozen worker entrypoint: `sys.executable -m` varsayımını gerçek PyInstaller EXE'de doğrula; `--onedir`, SHA manifest, license notices.
4. **G09-03:** Yedek şifreleme/ACL/race/idempotency tehditlerini değerlendir; tarihî sürüm/FTS restore regresyonlarını bağımsız makinede tekrarla.
5. **G09-04:** Gerçek izinli 20+ sayfalı tarama+PDF korpusu, CropBox/rotation/text-offset negatifler, yanlış sarı highlight sıfır şartı.
6. **G09-05:** Klavye/DPI/erişilebilirlik regresyonları ve UI referans piksel karşılaştırması.
7. **G09-06:** PDFium/Pillow/lxml/Tcl-Tk/CPython native notices + attestation + commercial REDIST; sözleşme onayı bekler, dağıtım **HOLD**.

Her iş için: kod + otomatik test + CI kanıtı + screen/ADR + doğrulanmış çıktıya göre PASS/PARTIAL/HOLD kararı. Gerçek Windows kullanıcı kabulü ve gerçek müşteri PDF kabulü en sonda.
