# G09-08 — SHA-256 kilitli Windows runtime wheelhouse ve NOTICE zinciri

**Mühendislik aşaması:** G09. **Ticari dağıtım: HOLD.**

## Amaç

Önceki G09 kanıtı, Windows EXE içindeki DLL/PYD dosyalarını sonradan
indirilmiş aynı sürümlü wheel adaylarıyla karşılaştırıyordu.
Yeni sürüm, CI içinde çalışan uygulama runtime'ını bu wheel baytlarına
bağlayarak o belirsizliği azaltır.

## Uygulama sırası

1. wheel_evidence.py plan: kurulu runtime bağımlılık kapanışını exact-version dosyasına yaz.
2. pip download --only-binary --no-deps: Windows wheelhouse hazırla.
3. wheelhouse_stage.py lock: sürüm/platform, archive güvenliği ve eksiksizlik denetimiyle wheel SHA-256 kilidi hazırla.
4. pip install --require-hashes --no-index --no-deps --force-reinstall: uygulamanın runtime paketlerini yalnız kilitli wheelhouse'dan yeniden kur.
5. Kaynak regresyonları, PyInstaller EXE derlemesi ve worker/arama/yedekleme testlerini çalıştır.
6. wheelhouse_stage.py notices: lisans metinlerini güvenli, boyut sınırlı bir staging işleminde dist/LocalKnowledge/THIRD_PARTY_NOTICES konumuna kopyala.
7. runtime_notice_manifest.json: wheel ve notice dosyalarının SHA-256 kanıtını üret.
8. release_inventory.py ve wheel_evidence.py audit: native EXE/DLL/PYD dosyalarını eşleştir, karşılanmamış yükümlülükleri açık tut.

## Sınırlar

- Hash listesi **her CI çalışmasında üretilir**; önceden onaylanmış kalıcı
  hash kilidi veya bağımsız kaynak imzası yerine geçmez.
- Wheel notice'ları, Microsoft UCRT/VCRUNTIME ve Visual C++ REDIST haklarını
  kanıtlamaz. Aynı ayrım CPython/Tcl-Tk, PDFium, Pillow codec ve lxml'in
  statik olarak bağlı native bileşenleri için de geçerlidir.
- Yeni kanıtlar ticari hak onayı üretmez: legal_clearance=false,
  commercial_release=HOLD.
- Gerçek Windows 10/11 offline son kullanıcı kabulü ve ticari sözleşme en sondadır.

## Zorunlu takip

1. Native kaynak-binary attestation ve Microsoft Visual C++ REDIST listesi.
2. PDFium/Pillow/lxml içerdiği codec/kütüphane lisanslarının bağımsız doğrulanması.
3. Önceden doğrulanmış ve değişmez wheel SHA lock'u oluşturulması.
4. Gerçek, izinli PDF/DOCX korpusuyla kaynak ve performans doğrulaması.
5. En son temiz Windows GUI ve ticari dağıtım kararı.

## Kabul kayıtları

| Kapı | Sonuç |
|---|---|
| Runtime kurulumu wheelhouse ile SHA kilitleme | CI sonucuna göre |
| NOTICE staging ve bütünlük manifesti | CI sonucuna göre |
| Native aday SHA byte eşleştirme | CI sonucuna göre |
| Birinci/üçüncü taraf ticari hakları | HOLD |
| Son kullanıcı Windows 10/11 kabulü | AÇIK — EN SON |
| Ticari release | HOLD |
