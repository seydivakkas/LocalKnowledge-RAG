# ADR-G08-01 — Windows PDF görüntüleyici askıda süreç başlatma

**Status:** Implemented candidate, Windows acceptance **HOLD**.

## Problem

G07 `Popen` sonrasında Job Object atıyordu. İşçi, atama öncesinde yerel PDF'yi açmaya başlayabileceği için bir yarış vardı. Python `subprocess.Popen` tarafında birincil thread handle'ı bulunmadığından `ResumeThread(Popen._handle)` doğru değildir.

## Decision

Windows'ta Win32 `CreateProcessW(..., CREATE_SUSPENDED | CREATE_NO_WINDOW)`; `CreateJobObjectW`; `SetInformationJobObject(JobObjectExtendedLimitInformation, KILL_ON_JOB_CLOSE | PROCESS_MEMORY | ACTIVE_PROCESS)`; `AssignProcessToJobObject`; **yalnız başarıdan sonra** `ResumeThread(hThread)`. `WaitForSingleObject` timeout, `GetExitCodeProcess`, `CloseHandle`; hata halinde askıdaki süreç `TerminateProcess` ve Job handle kapanışı. Shell/komut yorumlayıcısı yok, `subprocess.list2cmdline` doğru quoting; executable yolu ayrı argüman. Linux mevcut süreç grubu + worker RLIMIT yapısı korunur.

## Rejected

- `Popen` ile çalışır durumda başlatıp sonradan Job atamak: güvenlik yarışı.
- İşçiyi Tk event loop içinde native PDF parse etmek: uygulama crash alanını genişletir.
- PDF/arama için bulut API: çevrimdışı kullanıcı sözleşmesine aykırı.

## Windows acceptance still required

- Windows 10/11 farklı SDK/bitness, sistem Python ve frozen PyInstaller, düşük bellek ve timeout.
- Var olan bir Windows Job altında (GitHub runner / kurumsal masaüstü) nested-job başarısızlığında fail-closed davranışı.
- Çok sayıda PDF, uygulama kapatma, child process denemesi, bellek/CPU/virüs analizi ve GUI donmama.
- Bu Win32 job mekanizması **tam sandbox veya network isolation değildir**.

## Authoritative API references

- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs
- https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject
- https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
- https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread

Runtime/REDIST approval is independent from process security design.
