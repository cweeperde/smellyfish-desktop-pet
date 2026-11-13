"""Recycle bin size and where its desktop icon is (Windows), or the Trash through Finder and the Dock (macOS)."""

import ctypes
import sys
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from smellyfish.system.wincompat import wintypes

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
CLSID = "{645FF040-5081-101B-9F08-00AA002F954E}"
LVM_GETITEMCOUNT, LVM_GETITEMRECT, LVM_GETITEMTEXTW = 0x1004, 0x100E, 0x1073
LVIR_ICON = 1
PROCESS_ACCESS = 0x0008 | 0x0010 | 0x0020 | 0x0400
MEM_COMMIT, MEM_RELEASE, PAGE_READWRITE = 0x1000, 0x8000, 0x04


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", ctypes.c_int),
        ("iSubItem", ctypes.c_int),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", ctypes.c_void_p),
        ("cchTextMax", ctypes.c_int),
        ("iImage", ctypes.c_int),
        ("lParam", ctypes.c_void_p),
        ("iIndent", ctypes.c_int),
        ("iGroupId", ctypes.c_int),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.c_void_p),
        ("piColFmt", ctypes.c_void_p),
        ("iGroup", ctypes.c_int),
    ]


def query():
    """(bytes, items) or None."""
    if IS_MAC:
        from smellyfish.system import mac

        return mac.trash_info()
    if not IS_WIN:
        return None
    info = SHQUERYRBINFO()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return None
    return info.i64Size, info.i64NumItems


def empty(hwnd=None):
    """Asks with the normal Windows (or Finder) confirmation dialog."""
    if IS_MAC:
        from smellyfish.system import mac

        return mac.empty_trash()
    if IS_WIN:
        ctypes.windll.shell32.SHEmptyRecycleBinW(hwnd, None, 0)


def names():
    out = {"Recycle Bin", "Papierkorb"}
    if not IS_WIN:
        return out
    import winreg

    for root, key, value in (
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Windows\CurrentVersion\Explorer\CLSID\{CLSID}", ""),
        (winreg.HKEY_CLASSES_ROOT, rf"CLSID\{CLSID}", "LocalizedString"),
    ):
        try:
            with winreg.OpenKey(root, key) as k:
                text = winreg.QueryValueEx(k, value)[0]
        except OSError:
            continue
        if text.startswith("@"):
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shlwapi.SHLoadIndirectString(text, buf, 260, None) == 0:
                text = buf.value
            else:
                continue
        if text:
            out.add(text)
    return out


def _desktop_list():
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if view:
            lv = user32.FindWindowExW(view, None, "SysListView32", None)
            if lv:
                found.append(lv)
                return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def icon_rect():
    """Logical (x0, y0, x1, y1) of the recycle bin icon on the desktop, or None. On macOS the Trash sits in the
    Dock, so this is the free spot right above its tile."""
    if IS_MAC:
        from smellyfish.system import mac

        r = mac.dock_trash_rect()
        if not r:
            return None
        h = r[3] - r[1]
        return (r[0], r[1] - h - 2, r[2], r[1] - 2) if r[1] > 200 else None
    if not IS_WIN:
        return None
    from smellyfish.system import surfaces

    user32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.VirtualAllocEx.restype = ctypes.c_void_p
    k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    k32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
    ]
    k32.WriteProcessMemory.argtypes = k32.ReadProcessMemory.argtypes
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    lv = _desktop_list()
    if not lv or not user32.IsWindowVisible(lv):
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(lv, ctypes.byref(pid))
    proc = k32.OpenProcess(PROCESS_ACCESS, False, pid.value)
    if not proc:
        return None
    mem = k32.VirtualAllocEx(proc, None, 4096, MEM_COMMIT, PAGE_READWRITE)
    try:
        if not mem:
            return None
        wanted = {n.lower() for n in names()}
        count = user32.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)
        text_at = mem + 1024
        for i in range(min(count, 500)):
            item = LVITEMW(iSubItem=0, pszText=text_at, cchTextMax=260)
            k32.WriteProcessMemory(proc, mem, ctypes.byref(item), ctypes.sizeof(item), None)
            n = user32.SendMessageW(lv, LVM_GETITEMTEXTW, i, mem)
            if n <= 0:
                continue
            buf = ctypes.create_unicode_buffer(261)
            k32.ReadProcessMemory(proc, text_at, buf, 520, None)
            if buf.value.lower() not in wanted:
                continue
            rc = wintypes.RECT(LVIR_ICON, 0, 0, 0)
            k32.WriteProcessMemory(proc, mem, ctypes.byref(rc), ctypes.sizeof(rc), None)
            if not user32.SendMessageW(lv, LVM_GETITEMRECT, i, mem):
                return None
            k32.ReadProcessMemory(proc, mem, ctypes.byref(rc), ctypes.sizeof(rc), None)
            pts = (wintypes.POINT * 2)(wintypes.POINT(rc.left, rc.top), wintypes.POINT(rc.right, rc.bottom))
            user32.MapWindowPoints(lv, None, pts, 2)
            return surfaces._to_logical(wintypes.RECT(pts[0].x, pts[0].y, pts[1].x, pts[1].y))
        return None
    finally:
        if mem:
            k32.VirtualFreeEx(proc, mem, 0, MEM_RELEASE)
        k32.CloseHandle(proc)


def icon_visible(rect, exclude=()):
    if IS_MAC:
        return True
    from smellyfish.system import surfaces

    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    return not any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for _h, r in surfaces.window_rects(exclude))


class RecycleWatch(QObject):
    changed = Signal(object, object)  # (bytes, items) old, new
    poll_soon = Signal()

    def __init__(self):
        super().__init__()
        self.state = None
        self._busy = False
        self.enabled = lambda: True
        self.timer = QTimer(self, timeout=self.poll)
        self.timer.start((5 if IS_MAC else 1) * 60 * 1000)
        QTimer.singleShot(5000, self.poll)

    def poll(self):
        if self._busy or not self.enabled():
            return
        self._busy = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            new = query()
        except Exception:
            new = None
        self._busy = False
        if new is not None:
            old, self.state = self.state, new
            self.changed.emit(old, new)
