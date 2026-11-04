"""Top edges of visible desktop windows the pet can sit on (Windows only).

Rectangles come from Win32 in physical pixels and are converted to Qt's logical
coordinates per monitor. An edge counts only where no window above it in z-order
covers it.
"""
import ctypes
import sys
from ctypes import wintypes

from PySide6.QtGui import QGuiApplication

IS_WIN = sys.platform == "win32"
if IS_WIN:
    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x80
WS_EX_TRANSPARENT = 0x20
WS_EX_NOACTIVATE = 0x08000000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
MONITOR_DEFAULTTONEAREST = 2
SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"}


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


class Surface:
    __slots__ = ("hwnd", "x0", "x1", "y", "covers", "bottom")

    def __init__(self, hwnd, x0, x1, y):
        self.hwnd, self.x0, self.x1, self.y = hwnd, x0, x1, y
        self.covers = []
        self.bottom = y

    def side_visible(self, x, y_from, y_to, step=12):
        """The window's vertical edge at x is not covered by windows in front between y_from and y_to."""
        y = y_from
        while y <= y_to:
            if any(c[0] <= x <= c[2] and c[1] <= y <= c[3] for c in self.covers):
                return False
            y += step
        return True

    def visible_at(self, x):
        return self.x0 <= x <= self.x1 and not any(c[0] <= x <= c[2] and c[1] <= self.y + 1 <= c[3]
                                                    for c in self.covers)

    def visible_span(self, xa, xb, step=4):
        """The whole stretch [xa, xb] of the top edge is on the window and not covered by another one."""
        if xa < self.x0 or xb > self.x1:
            return False
        x = xa
        while x < xb:
            if not self.visible_at(x):
                return False
            x += step
        return self.visible_at(xb)

    def __repr__(self):
        return f"Surface({self.hwnd}, {self.x0}..{self.x1} @ {self.y})"


def _rect(hwnd):
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def _to_logical(r):
    """Physical RECT -> logical (x0, y0, x1, y1) using the monitor the rect is on."""
    mon = user32.MonitorFromRect(ctypes.byref(r), MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFOEXW()
    mi.cbSize = ctypes.sizeof(mi)
    user32.GetMonitorInfoW(mon, ctypes.byref(mi))
    ox, oy = mi.rcMonitor.left, mi.rcMonitor.top
    screen = min(QGuiApplication.screens(),
                 key=lambda s: abs(s.geometry().x() - ox) + abs(s.geometry().y() - oy))
    dpr = screen.devicePixelRatio()
    g = screen.geometry()
    return (g.x() + (r.left - ox) / dpr, g.y() + (r.top - oy) / dpr,
            g.x() + (r.right - ox) / dpr, g.y() + (r.bottom - oy) / dpr)


def _class(hwnd):
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buf, 64)
    return buf.value


def _cloaked(hwnd):
    v = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v))
    return v.value != 0


def window_rects(exclude=()):
    """Visible top-level windows in z-order (front first) as (hwnd, logical rect)."""
    if not IS_WIN:
        return []
    out = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if hwnd in exclude or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & (WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT) or _class(hwnd) in SKIP_CLASSES or _cloaked(hwnd):
            return True
        r = _rect(hwnd)
        if r.right - r.left < 120 or r.bottom - r.top < 60:
            return True
        out.append((hwnd, _to_logical(r)))
        return True

    user32.EnumWindows(cb, 0)
    return out


def surfaces(exclude=(), min_room=0):
    """Top edges of windows, each knowing which windows in front of it cover parts of it."""
    rects = window_rects(exclude)
    out = []
    for i, (hwnd, (x0, y0, x1, y1)) in enumerate(rects):
        screen = QGuiApplication.screenAt(_qpoint((x0 + x1) / 2, y0 + 2))
        if screen is None or y0 - min_room < screen.availableGeometry().top():
            continue
        s = Surface(hwnd, x0, x1, y0)
        s.bottom = y1
        s.covers = [r for _, r in rects[:i]]
        out.append(s)
    return out


def window_top(hwnd):
    """Current logical top edge (x0, x1, y) of a window, or None if it is gone or hidden."""
    if not IS_WIN or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) \
            or _cloaked(hwnd):
        return None
    x0, y0, x1, _ = _to_logical(_rect(hwnd))
    return x0, x1, y0


def _qpoint(x, y):
    from PySide6.QtCore import QPoint
    return QPoint(round(x), round(y))
