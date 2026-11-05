"""Global hotkeys via RegisterHotKey (Windows). Hotkey strings look like "Ctrl+Alt+F9"."""
import ctypes
import sys

WM_HOTKEY = 0x0312
MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8, "meta": 0x8}
MOD_NOREPEAT = 0x4000
NAMED = {"space": 0x20, "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "home": 0x24, "end": 0x23, "ins": 0x2D,
         "insert": 0x2D, "del": 0x2E, "delete": 0x2E, "pgup": 0x21, "pgdown": 0x22, "left": 0x25, "up": 0x26,
         "right": 0x27, "down": 0x28, "pause": 0x13}

ACTIONS = [
    ("toggle", "Hide / show"),
    ("home", "Go home"),
    ("dnd", "Do not disturb"),
    ("history", "Missed bubbles"),
    ("focus", "Focus timer start / stop"),
    ("chase", "Chase the cursor"),
    ("mini", "Mini mode"),
    ("todo", "To-do list"),
]
DEFAULTS = {"toggle": "Ctrl+Alt+F9", "home": "Ctrl+Alt+F10", "dnd": "Ctrl+Alt+F11", "history": "Ctrl+Alt+F12",
            "focus": "Ctrl+Alt+F8", "chase": "Ctrl+Alt+F7", "mini": "Ctrl+Alt+F6", "todo": "Ctrl+Alt+F5"}


def parse(text):
    """'Ctrl+Alt+F9' -> (modifiers, virtual key) or None."""
    if not text:
        return None
    mods, vk = 0, None
    for part in text.replace(" ", "").split("+"):
        p = part.lower()
        if p in MODS:
            mods |= MODS[p]
        elif p.startswith("f") and p[1:].isdigit() and 1 <= int(p[1:]) <= 24:
            vk = 0x6F + int(p[1:])
        elif len(p) == 1 and p.isalnum():
            vk = ord(p.upper())
        elif p in NAMED:
            vk = NAMED[p]
        else:
            return None
    return (mods, vk) if vk else None


class Hotkeys:
    def __init__(self):
        self.hwnd = None
        self.ids = {}
        self.failed = []

    def register(self, hwnd, mapping):
        """mapping: {action: 'Ctrl+Alt+F9'}. Returns actions whose key is taken by another app."""
        self.unregister()
        self.hwnd = hwnd
        self.failed = []
        if sys.platform != "win32":
            return []
        user32 = ctypes.windll.user32
        for i, (action, _) in enumerate(ACTIONS, start=1):
            key = parse(mapping.get(action, ""))
            if not key:
                continue
            if user32.RegisterHotKey(hwnd, i, key[0] | MOD_NOREPEAT, key[1]):
                self.ids[i] = action
            else:
                self.failed.append(action)
        return self.failed

    def unregister(self):
        if sys.platform == "win32" and self.hwnd:
            for i in self.ids:
                ctypes.windll.user32.UnregisterHotKey(self.hwnd, i)
        self.ids = {}

    def action_for(self, message_address):
        from ctypes import wintypes
        msg = wintypes.MSG.from_address(int(message_address))
        if msg.message == WM_HOTKEY:
            return self.ids.get(int(msg.wParam))
        return None
