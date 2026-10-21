"""Memory and CPU facts used to size the render pool. Pure stdlib (psutil is used when installed)."""
import os
import subprocess
import sys

MB = 2 ** 20


def memory_mb():
    """(available, total) physical memory in MB, or (None, None) when unknown."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return vm.available / MB, vm.total / MB
    except ImportError:
        pass
    try:
        if sys.platform == 'win32':
            return _windows()
        if sys.platform.startswith('linux'):
            return _linux()
        if sys.platform == 'darwin':
            return _macos()
    except Exception:  # noqa: BLE001 - any probe failure just means "unknown"
        pass
    return None, None


def _windows():
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return None, None
    return st.ullAvailPhys / MB, st.ullTotalPhys / MB


def _linux():
    info = {}
    with open('/proc/meminfo', encoding='ascii') as fh:
        for line in fh:
            k, v = line.split(':', 1)
            info[k] = int(v.split()[0]) * 1024
    avail = info.get('MemAvailable', info.get('MemFree', 0) + info.get('Cached', 0))
    return avail / MB, info['MemTotal'] / MB


def _macos():
    total = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True, check=True).stdout)
    out = subprocess.run(['vm_stat'], capture_output=True, text=True, check=True).stdout
    page = int(out.split('page size of')[1].split()[0])
    pages = {}
    for line in out.splitlines()[1:]:
        if ':' in line:
            k, v = line.split(':', 1)
            pages[k.strip()] = int(v.strip().rstrip('.'))
    free = sum(pages.get(k, 0) for k in ('Pages free', 'Pages inactive', 'Pages speculative'))
    return free * page / MB, total / MB


def limit_blas_threads():
    """One BLAS thread per process for processes started from now on (and this one, if numpy is not loaded yet).

    The renderer gains nothing from BLAS threads, but OpenBLAS commits a buffer per thread at import:
    about 500 MB per process on a 16-thread CPU, which is what made parallel renders run out of memory.
    Values the user already set are kept.
    """
    for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ.setdefault(var, '1')


def cpu_count():
    return os.cpu_count() or 2
