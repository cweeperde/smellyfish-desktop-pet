"""Top edges of visible desktop windows the pet can sit on.

On Windows, rectangles come from Win32 in physical pixels and are converted to Qt's logical
coordinates per monitor. An edge counts only where no window above it in z-order
covers it. On macOS, Quartz reports bounds already in Qt's coordinates.

Desktop icons count as small surfaces too (see icons.py). Only icons with free desktop
above them qualify, so the pet never covers another icon.
"""

import ctypes
import sys

from PySide6.QtGui import QGuiApplication

from smellyfish.system import icons as desk_icons
from smellyfish.system import mac
from smellyfish.system.wincompat import wintypes

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
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
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class Surface:
    __slots__ = ("hwnd", "x0", "x1", "y", "covers", "bottom", "icon")

    def __init__(self, hwnd, x0, x1, y):
        self.hwnd, self.x0, self.x1, self.y = hwnd, x0, x1, y
        self.covers = []
        self.bottom = y
        self.icon = None

    def side_visible(self, x, y_from, y_to, step=12):
        """The window's vertical edge at x is not covered by windows in front between y_from and y_to."""
        y = y_from
        while y <= y_to:
            if any(c[0] <= x <= c[2] and c[1] <= y <= c[3] for c in self.covers):
                return False
            y += step
        return True

    def visible_at(self, x):
        return self.x0 <= x <= self.x1 and not any(
            c[0] <= x <= c[2] and c[1] <= self.y + 1 <= c[3] for c in self.covers
        )

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
    screen = min(QGuiApplication.screens(), key=lambda s: abs(s.geometry().x() - ox) + abs(s.geometry().y() - oy))
    dpr = screen.devicePixelRatio()
    g = screen.geometry()
    return (
        g.x() + (r.left - ox) / dpr,
        g.y() + (r.top - oy) / dpr,
        g.x() + (r.right - ox) / dpr,
        g.y() + (r.bottom - oy) / dpr,
    )


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
    if IS_MAC:
        return _mac_rects()
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
        box = _to_logical(r)
        if any(all(abs(box[i] - o[1][i]) < 2 for i in range(4)) for o in out):
            return True
        out.append((hwnd, box))
        return True

    user32.EnumWindows(cb, 0)
    return out


def surfaces(exclude=(), min_room=0, windows=True, icons=None):
    """Top edges of windows, each knowing which windows in front of it cover parts of it.
    icons=(width, height) of the pet also adds the desktop icons that have that much free room above them."""
    rects = window_rects(exclude)
    out = []
    if icons:
        covers = [r for _, r in rects]
        for s in icon_surfaces(icons[0], icons[1], min_room):
            s.covers = covers
            out.append(s)
    if not windows:
        return out
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
    """Current logical top edge (x0, x1, y) of a window (or desktop icon), or None if it is gone or hidden."""
    if isinstance(hwnd, tuple):
        found = _find_icon(hwnd)
        return (found[0][0], found[0][2], found[1][1]) if found else None
    if IS_MAC:
        r = mac.window_rect(hwnd)
        return (r[0], r[2], r[1]) if r else None
    if (
        not IS_WIN
        or not user32.IsWindow(hwnd)
        or not user32.IsWindowVisible(hwnd)
        or user32.IsIconic(hwnd)
        or _cloaked(hwnd)
    ):
        return None
    x0, y0, x1, _ = _to_logical(_rect(hwnd))
    return x0, x1, y0


def window_bottom(hwnd):
    """Current logical (x0, x1, bottom y) of a window, or None if it is gone or hidden."""
    if IS_MAC and not isinstance(hwnd, tuple):
        r = mac.window_rect(hwnd)
        return (r[0], r[2], r[3]) if r else None
    if (
        not IS_WIN
        or isinstance(hwnd, tuple)
        or not user32.IsWindow(hwnd)
        or not user32.IsWindowVisible(hwnd)
        or user32.IsIconic(hwnd)
        or _cloaked(hwnd)
    ):
        return None
    x0, _y0, x1, y1 = _to_logical(_rect(hwnd))
    return x0, x1, y1


def _qpoint(x, y):
    from PySide6.QtCore import QPoint

    return QPoint(round(x), round(y))


def _icons():
    if IS_MAC:
        return mac.desktop_icons()
    return desk_icons.desktop_icons(lambda r: _to_logical(r))


def _mac_rects():
    out = []
    for wid, pid, box in mac.window_list():
        if pid == mac.OWN_PID or box[2] - box[0] < 120 or box[3] - box[1] < 60:
            continue
        if any(all(abs(box[i] - o[1][i]) < 2 for i in range(4)) for o in out):
            continue
        out.append((wid, box))
    return out


def _find_icon(key):
    best, best_d = None, 5
    for bounds, glyph in _icons():
        d = max(abs(bounds[0] - key[1]), abs(glyph[1] - key[2]))
        if d < best_d:
            best, best_d = (bounds, glyph), d
    return best


def icon_bounds(key):
    found = _find_icon(key)
    return found[0] if found else None


def icon_surfaces(foot_w, foot_h, min_room):
    """Every desktop item (icons, shortcuts, files, folders) is a place to sit. The surface is at least as wide as
    the pet, centred on the item."""
    icons = _icons()
    out = []
    for b, g in icons:
        x0, x1, top = b[0], b[2], g[1]
        if x1 - x0 < foot_w * 1.7:
            mid = (x0 + x1) / 2
            x0, x1 = mid - foot_w * 0.85, mid + foot_w * 0.85
        screen = QGuiApplication.screenAt(_qpoint((x0 + x1) / 2, top + 2))
        if screen is None or top - min_room < screen.availableGeometry().top():
            continue
        s = Surface(("icon", round(b[0]), round(top)), x0, x1, top)
        s.bottom, s.icon = b[3], b
        out.append(s)
    return out
