"""G08 process sandbox: POSIX process group; Windows CREATE_SUSPENDED then Job assignment.

No shells or network protocols. NOT a Windows AppContainer/network sandbox.
Windows real machine acceptance and native redistribution rights remain HOLD.
"""
from __future__ import annotations
from dataclasses import dataclass
import os
import signal
import subprocess


@dataclass(frozen=True)
class WorkerStatus:
    ok: bool
    code: str
    message: str


def _windows_suspended_job_worker(command:list[str], *, timeout:float, memory_bytes:int, cwd, output_path) -> WorkerStatus:
    """Win32 API: a new process cannot execute before Job Object assignment.

    Important: subprocess.Popen + CREATE_SUSPENDED does NOT expose the primary
    thread handle, so do not try to ResumeThread on Popen._handle (process).
    """
    import ctypes
    from ctypes import wintypes

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [('cb',wintypes.DWORD),('lpReserved',wintypes.LPWSTR),('lpDesktop',wintypes.LPWSTR),
                    ('lpTitle',wintypes.LPWSTR),('dwX',wintypes.DWORD),('dwY',wintypes.DWORD),
                    ('dwXSize',wintypes.DWORD),('dwYSize',wintypes.DWORD),
                    ('dwXCountChars',wintypes.DWORD),('dwYCountChars',wintypes.DWORD),
                    ('dwFillAttribute',wintypes.DWORD),('dwFlags',wintypes.DWORD),
                    ('wShowWindow',wintypes.WORD),('cbReserved2',wintypes.WORD),
                    ('lpReserved2',ctypes.POINTER(ctypes.c_byte)),
                    ('hStdInput',wintypes.HANDLE),('hStdOutput',wintypes.HANDLE),('hStdError',wintypes.HANDLE)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_=[('hProcess',wintypes.HANDLE),('hThread',wintypes.HANDLE),
                  ('dwProcessId',wintypes.DWORD),('dwThreadId',wintypes.DWORD)]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),
                  ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),
                  ('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),
                  ('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]

    class IO_COUNTERS(ctypes.Structure):
        _fields_=[(n,ctypes.c_uint64) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount',
                                                 'ReadTransferCount','WriteTransferCount','OtherTransferCount')]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_=[('BasicLimitInformation',JOBOBJECT_BASIC_LIMIT_INFORMATION),('IoInfo',IO_COUNTERS),
                  ('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),
                  ('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]

    k = ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p,wintypes.LPCWSTR]
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    k.SetInformationJobObject.restype=wintypes.BOOL
    k.CreateProcessW.argtypes=[wintypes.LPCWSTR,wintypes.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,
                               wintypes.BOOL,wintypes.DWORD,ctypes.c_void_p,wintypes.LPCWSTR,
                               ctypes.POINTER(STARTUPINFOW),ctypes.POINTER(PROCESS_INFORMATION)]
    k.CreateProcessW.restype=wintypes.BOOL
    k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    k.AssignProcessToJobObject.restype=wintypes.BOOL
    k.ResumeThread.argtypes=[wintypes.HANDLE]
    k.ResumeThread.restype=wintypes.DWORD
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    k.WaitForSingleObject.restype=wintypes.DWORD
    k.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    k.GetExitCodeProcess.restype=wintypes.BOOL
    k.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    k.TerminateProcess.restype=wintypes.BOOL
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    k.CloseHandle.restype=wintypes.BOOL

    job = k.CreateJobObjectW(None,None)
    if not job:
        return WorkerStatus(False,'PDF_WORKER_START_FAILED','Windows güvenlik işi oluşturulamadı.')
    pi=PROCESS_INFORMATION()
    started=False
    try:
        limits=JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        # Kill on job-close, single process only, memory cap: 0x2000 | 0x8 | 0x100
        limits.BasicLimitInformation.LimitFlags=0x2000 | 0x8 | 0x100
        limits.BasicLimitInformation.ActiveProcessLimit=1
        limits.ProcessMemoryLimit=memory_bytes
        if not k.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            return WorkerStatus(False,'PDF_WORKER_START_FAILED','Windows iş sınırları ayarlanamadı.')
        si=STARTUPINFOW();si.cb=ctypes.sizeof(si)
        cmdline=ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        # CREATE_SUSPENDED(0x4) + CREATE_NO_WINDOW(0x08000000).
        if not k.CreateProcessW(str(command[0]),cmdline,None,None,False,0x4|0x08000000,
                                None,str(cwd),ctypes.byref(si),ctypes.byref(pi)):
            return WorkerStatus(False,'PDF_WORKER_START_FAILED','Windows korumalı süreç başlatılamadı.')
        started=True
        if not k.AssignProcessToJobObject(job,pi.hProcess):
            return WorkerStatus(False,'PDF_WORKER_START_FAILED','İşçi güvenlik sınırına bağlanamadı.')
        if k.ResumeThread(pi.hThread)==0xFFFFFFFF:
            return WorkerStatus(False,'PDF_WORKER_START_FAILED','Korumalı işçi devam ettirilemedi.')
        waited=k.WaitForSingleObject(pi.hProcess,int(timeout*1000))
        if waited==0x102:
            return WorkerStatus(False,'PDF_WORKER_TIMEOUT','PDF görüntüleme süresi aşıldı.')
        if waited!=0:
            return WorkerStatus(False,'PDF_WORKER_FAILED','Windows işçisi tamamlanamadı.')
        code=wintypes.DWORD(999)
        if not k.GetExitCodeProcess(pi.hProcess,ctypes.byref(code)) or code.value!=0 or not output_path.is_file():
            return WorkerStatus(False,'PDF_WORKER_FAILED','PDF güvenli alt süreçte işlenemedi.')
        return WorkerStatus(True,'OK','')
    except (OSError,ValueError,TypeError):
        return WorkerStatus(False,'PDF_WORKER_START_FAILED','Korumalı Windows süreç hazırlığı başarısız.')
    finally:
        # Closing the job kills every attached descendant before returning.
        if started:
            # TerminateProcess is asynchronous on Windows. Wait for complete
            # handle release before temporary directories can be removed.
            k.TerminateProcess(pi.hProcess,1)
            k.WaitForSingleObject(pi.hProcess,5000)
            k.CloseHandle(pi.hThread)
            k.CloseHandle(pi.hProcess)
        k.CloseHandle(job)


def bounded_worker(command:list[str],*,timeout:float,memory_bytes:int,cwd,output_path)->WorkerStatus:
    if not isinstance(command,list) or not command or not all(isinstance(x,str) and x for x in command):
        raise ValueError('Invalid worker command')
    if not 1 <= timeout <= 60 or not 128*1024**2<=memory_bytes<=2*1024**3:
        raise ValueError('Invalid worker limits')
    if os.name=='nt':
        # Process is SUSPENDED before any untrusted PDF parsing, assigned to a
        # bounded Job, then RESUMED. Real Windows validation is still required.
        return _windows_suspended_job_worker(command,timeout=timeout,memory_bytes=memory_bytes,
                                             cwd=cwd,output_path=output_path)
    proc=None
    try:
        proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,cwd=str(cwd),start_new_session=True)
        try:proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_tree(proc)
            return WorkerStatus(False,'PDF_WORKER_TIMEOUT','PDF görüntüleme süresi aşıldı.')
        if proc.returncode!=0 or not output_path.is_file():
            return WorkerStatus(False,'PDF_WORKER_FAILED','PDF güvenli alt süreçte işlenemedi.')
        return WorkerStatus(True,'OK','')
    except (OSError,RuntimeError,ValueError,TypeError):
        if proc is not None:_terminate_tree(proc)
        return WorkerStatus(False,'PDF_WORKER_START_FAILED','Korumalı PDF işçisi başlatılamadı.')
    finally:
        if proc is not None and proc.poll() is None:_terminate_tree(proc)


def _terminate_tree(proc):
    try:
        if os.name=='posix':os.killpg(proc.pid,signal.SIGKILL)
        else:proc.kill()
    except (OSError,ProcessLookupError):pass
    try:proc.wait(timeout=2)
    except (OSError,subprocess.TimeoutExpired):pass
