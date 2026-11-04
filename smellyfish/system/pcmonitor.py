"""Watches the PC: CPU load, input idle time, battery, internet, fullscreen apps, screen lock,
Spotify playback and time of day."""
import ctypes
import socket
import sys
import threading
import time
from collections import deque
from ctypes import wintypes

import psutil
from PySide6.QtCore import QObject, QTimer, Signal

IS_WIN = sys.platform == "win32"
CPU_BUSY, CPU_CALM = 50, 30


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def input_idle_seconds():
    if not IS_WIN:
        return 0.0
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return max(0.0, (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0)


def window_text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(64)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 64)
    return buf.value


def window_pid(hwnd):
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def fullscreen_app(own_pid):
    """True when the foreground window covers its whole monitor (game, video, presentation)."""
    if not IS_WIN:
        return False
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd or window_pid(hwnd) == own_pid:
        return False
    if window_class(hwnd) in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return False
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
    m = mi.rcMonitor
    return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom


def spotify_playing():
    """Spotify's main window title is 'Artist - Song' while playing and 'Spotify ...' when paused."""
    if not IS_WIN:
        return False
    pids = {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "spotify.exe"}
    if not pids:
        return False
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if ctypes.windll.user32.IsWindowVisible(hwnd) and window_pid(hwnd) in pids:
            t = window_text(hwnd)
            if t:
                found.append(t)
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return any(" - " in t and not t.lower().startswith("spotify") for t in found)


def screen_locked():
    return any((p.info["name"] or "").lower() == "logonui.exe" for p in psutil.process_iter(["name"]))


class PcMonitor(QObject):
    event = Signal(str)          # "user_back", "plugged", "online_again", "locked", "unlocked"

    def __init__(self):
        super().__init__()
        self.cpu = deque(maxlen=4)
        self.hot = False
        self.idle_s = 0.0
        self.battery_low = False
        self.plugged = None
        self.online = True
        self.fullscreen = False
        self.locked = False
        self.spotify = False
        self._fails = 0
        self._away_since = None
        self._tick = 0
        self.own_pid = psutil.Process().pid
        psutil.cpu_percent(None)
        self.timer = QTimer(self, timeout=self.poll)
        self.timer.start(2000)
        self.net_timer = QTimer(self, timeout=self.check_net)
        self.net_timer.start(20000)
        self.check_net()

    @property
    def night(self):
        h = time.localtime().tm_hour
        return h >= 23 or h < 6

    def poll(self):
        self._tick += 1
        self.cpu.append(psutil.cpu_percent(None))
        avg = sum(self.cpu) / len(self.cpu)
        if not self.hot and len(self.cpu) == self.cpu.maxlen and avg > CPU_BUSY:
            self.hot = True
        elif self.hot and avg < CPU_CALM:
            self.hot = False

        self.idle_s = input_idle_seconds()
        if self.idle_s > 300 and self._away_since is None:
            self._away_since = time.time() - self.idle_s
        elif self.idle_s < 5 and self._away_since is not None:
            self._away_since = None
            self.event.emit("user_back")

        try:
            b = psutil.sensors_battery()
        except Exception:
            b = None
        if b is not None:
            if self.plugged is False and b.power_plugged:
                self.event.emit("plugged")
            self.plugged = b.power_plugged
            self.battery_low = b.percent <= 20 and not b.power_plugged

        try:
            self.fullscreen = fullscreen_app(self.own_pid)
        except Exception:
            self.fullscreen = False
        if self._tick % 2 == 0:
            try:
                locked = screen_locked()
                if locked != self.locked:
                    self.locked = locked
                    self.event.emit("locked" if locked else "unlocked")
                self.spotify = spotify_playing()
            except Exception:
                pass

    def check_net(self):
        def probe():
            ok = False
            for host in (("1.1.1.1", 53), ("8.8.8.8", 53)):
                try:
                    socket.create_connection(host, timeout=2).close()
                    ok = True
                    break
                except OSError:
                    pass
            self._fails = 0 if ok else self._fails + 1
            was = self.online
            self.online = ok or self._fails < 2
            if self.online and not was:
                self.event.emit("online_again")

        threading.Thread(target=probe, daemon=True).start()
