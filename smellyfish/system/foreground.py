"""The foreground window: notices hectic window switching and a window being dragged around."""
import ctypes
import sys
import time
from collections import deque
from ctypes import wintypes


def _foreground():
    if sys.platform != "win32":
        return None, None
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return hwnd, None
    return hwnd, (r.left, r.top, r.right, r.bottom)


class Foreground:
    def __init__(self):
        self.switches = deque(maxlen=12)
        self.last = (None, None)
        self.moving_since = None
        self.moved = 0.0

    def poll(self, own):
        """Returns 'hectic' after many quick window switches, ('dragged', centre x, top y) while a window is being
        moved, else None."""
        hwnd, rect = _foreground()
        now = time.time()
        if hwnd is None or hwnd in own:
            return None
        prev_hwnd, prev_rect = self.last
        self.last = (hwnd, rect)
        if hwnd != prev_hwnd:
            self.switches.append(now)
            self.moving_since, self.moved = None, 0.0
            recent = [t for t in self.switches if now - t < 3.0]
            if len(recent) >= 6:
                self.switches.clear()
                return "hectic"
            return None
        if rect and prev_rect and rect != prev_rect:
            same_size = (rect[2] - rect[0], rect[3] - rect[1]) == (prev_rect[2] - prev_rect[0], prev_rect[3] - prev_rect[1])
            if same_size:
                self.moved += abs(rect[0] - prev_rect[0]) + abs(rect[1] - prev_rect[1])
                self.moving_since = self.moving_since or now
                if self.moved > 250 and now - self.moving_since > 0.4:
                    self.moving_since, self.moved = None, 0.0
                    return ("dragged", (rect[0] + rect[2]) / 2, rect[1])
        elif rect == prev_rect and self.moving_since and now - self.moving_since > 1.5:
            self.moving_since, self.moved = None, 0.0
        return None
