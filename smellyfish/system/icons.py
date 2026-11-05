"""Desktop icon positions (Windows). Reads geometry only (no names) from the desktop list view.

Icons the pet may sit on must have free desktop above them, so it never covers another icon.
"""
import ctypes
import sys
import time
from ctypes import wintypes

IS_WIN = sys.platform == "win32"

LVM_GETITEMCOUNT = 0x1004
LVM_GETITEMRECT = 0x100E
PROCESS_VM_ACCESS = 0x8 | 0x10 | 0x20
MEM_COMMIT_RESERVE = 0x3000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04
SMTO_ABORTIFHUNG = 0x2
MAX_ICONS = 400

_cache = (0.0, [])
_api = None


def _winapi():
    global _api
    if _api is None:
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        H, P = wintypes.HWND, ctypes.c_void_p
        u.FindWindowW.argtypes, u.FindWindowW.restype = [wintypes.LPCWSTR, wintypes.LPCWSTR], H
        u.FindWindowExW.argtypes = [H, H, wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowExW.restype = H
        u.IsWindowVisible.argtypes = [H]
        u.ClientToScreen.argtypes = [H, ctypes.POINTER(wintypes.POINT)]
        u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
        u.SendMessageTimeoutW.argtypes = [H, wintypes.UINT, ctypes.c_size_t, ctypes.c_size_t, wintypes.UINT,
                                          wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
        k.OpenProcess.argtypes, k.OpenProcess.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
        k.VirtualAllocEx.argtypes = [wintypes.HANDLE, P, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        k.VirtualAllocEx.restype = P
        k.VirtualFreeEx.argtypes = [wintypes.HANDLE, P, ctypes.c_size_t, wintypes.DWORD]
        k.ReadProcessMemory.argtypes = [wintypes.HANDLE, P, P, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        k.WriteProcessMemory.argtypes = [wintypes.HANDLE, P, P, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        _api = (u, k)
    return _api


def _desktop_listview(u):
    shell = u.FindWindowW("Progman", None)
    view = u.FindWindowExW(shell, None, "SHELLDLL_DefView", None) if shell else None
    worker = None
    while not view:
        worker = u.FindWindowExW(None, worker, "WorkerW", None)
        if not worker:
            return None
        view = u.FindWindowExW(worker, None, "SHELLDLL_DefView", None)
    return u.FindWindowExW(view, None, "SysListView32", None)


def _read(to_logical):
    u, k = _winapi()
    lv = _desktop_listview(u)
    if not lv or not u.IsWindowVisible(lv):
        return []
    res = ctypes.c_size_t(0)

    def send(msg, w, lp):
        return u.SendMessageTimeoutW(lv, msg, w, lp, SMTO_ABORTIFHUNG, 80, ctypes.byref(res))

    if not send(LVM_GETITEMCOUNT, 0, 0) or not 0 < res.value <= MAX_ICONS:
        return []
    count = res.value
    pid = wintypes.DWORD(0)
    u.GetWindowThreadProcessId(lv, ctypes.byref(pid))
    proc = k.OpenProcess(PROCESS_VM_ACCESS, False, pid.value)
    if not proc:
        return []
    out = []
    try:
        remote = k.VirtualAllocEx(proc, None, ctypes.sizeof(wintypes.RECT), MEM_COMMIT_RESERVE, PAGE_READWRITE)
        if not remote:
            return []
        try:
            origin = wintypes.POINT(0, 0)
            u.ClientToScreen(lv, ctypes.byref(origin))
            for i in range(count):
                pair = []
                for code in (0, 1):                      # LVIR_BOUNDS, LVIR_ICON
                    r = wintypes.RECT(code, 0, 0, 0)
                    k.WriteProcessMemory(proc, remote, ctypes.byref(r), ctypes.sizeof(r), None)
                    if not send(LVM_GETITEMRECT, i, remote) or not res.value:
                        return out
                    k.ReadProcessMemory(proc, remote, ctypes.byref(r), ctypes.sizeof(r), None)
                    pair.append(to_logical(wintypes.RECT(r.left + origin.x, r.top + origin.y,
                                                         r.right + origin.x, r.bottom + origin.y)))
                out.append((pair[0], pair[1]))
        finally:
            k.VirtualFreeEx(proc, remote, 0, MEM_RELEASE)
    finally:
        k.CloseHandle(proc)
    return out


def desktop_icons(to_logical, max_age=1.5):
    """Cached [(bounds, glyph)] logical rects (x0, y0, x1, y1) of the visible desktop icons; never raises."""
    global _cache
    if not IS_WIN:
        return []
    now = time.time()
    if now - _cache[0] > max_age:
        try:
            items = _read(to_logical)
        except Exception:
            items = []
        _cache = (now, items)
    return _cache[1]
