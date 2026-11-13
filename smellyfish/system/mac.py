"""macOS side of the system layer: windows, input, permissions, Finder and the Dock.

Window bounds and owners come from Quartz and need no permission (window titles would need Screen Recording,
so they are never read). Everything else that needs a permission only runs once the matching feature is on.
"""

import ctypes
import logging
import os
import subprocess
import sys
import threading
import time

log = logging.getLogger("smellyfish.mac")

IS_MAC = sys.platform == "darwin"
OWN_PID = os.getpid()
_cache = {}


def _q():
    import Quartz

    return Quartz


def _appkit():
    import AppKit

    return AppKit


# ------------------------------------------------------------------ windows
def window_list():
    """Visible normal windows, front first: [(window id, pid, (x0, y0, x1, y1))] in Qt's global coordinates."""
    if not IS_MAC:
        return []
    Q = _q()
    infos = Q.CGWindowListCopyWindowInfo(
        Q.kCGWindowListOptionOnScreenOnly | Q.kCGWindowListExcludeDesktopElements, Q.kCGNullWindowID
    )
    out = []
    for w in infos or []:
        if w.get(Q.kCGWindowLayer, 0) != 0 or w.get(Q.kCGWindowAlpha, 1.0) < 0.05:
            continue
        b = w.get(Q.kCGWindowBounds) or {}
        x, y = float(b.get("X", 0)), float(b.get("Y", 0))
        out.append(
            (
                int(w[Q.kCGWindowNumber]),
                int(w.get(Q.kCGWindowOwnerPID, 0)),
                (x, y, x + float(b.get("Width", 0)), y + float(b.get("Height", 0))),
            )
        )
    return out


def window_rect(wid):
    """(x0, y0, x1, y1) of one window while it is on screen, else None."""
    if not IS_MAC:
        return None
    Q = _q()
    infos = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionIncludingWindow, int(wid)) or []
    for w in infos:
        if int(w[Q.kCGWindowNumber]) != int(wid) or not w.get(Q.kCGWindowIsOnscreen):
            continue
        b = w.get(Q.kCGWindowBounds) or {}
        x, y = float(b.get("X", 0)), float(b.get("Y", 0))
        return x, y, x + float(b.get("Width", 0)), y + float(b.get("Height", 0))
    return None


def windows_of(names):
    """On-screen windows whose owning app is called one of names (lower case): [(window id, rect)]."""
    if not IS_MAC:
        return []
    Q = _q()
    infos = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly, Q.kCGNullWindowID) or []
    out = []
    for w in infos:
        if str(w.get(Q.kCGWindowOwnerName) or "").lower() in names and w.get(Q.kCGWindowLayer, 0) == 0:
            b = w.get(Q.kCGWindowBounds) or {}
            if float(b.get("Width", 0)) > 50 and float(b.get("Height", 0)) > 50:
                out.append((int(w[Q.kCGWindowNumber]), b))
    return out


def frontmost_pid():
    if not IS_MAC:
        return None
    app = _appkit().NSWorkspace.sharedWorkspace().frontmostApplication()
    return int(app.processIdentifier()) if app is not None else None


def front_window():
    """(window id, rect) of the front window of the active app, or (None, None)."""
    pid = frontmost_pid()
    if pid is None or pid == OWN_PID:
        return None, None
    for wid, owner, rect in window_list():
        if owner == pid:
            return wid, rect
    return None, None


def fullscreen_app():
    """The active app has a window covering a whole screen (game, video, presentation)."""
    from PySide6.QtGui import QGuiApplication

    wid, rect = front_window()
    if wid is None:
        return False
    for s in QGuiApplication.screens():
        g = s.geometry()
        if rect[0] <= g.left() + 1 and rect[1] <= g.top() + 1 and rect[2] >= g.right() and rect[3] >= g.bottom():
            return True
    return False


def float_window(widget):
    """Keep one of our windows above normal windows, on every Space and next to fullscreen apps."""
    if not IS_MAC or widget.property("sf_floating"):
        return
    try:
        import objc

        AppKit = _appkit()
        view = objc.objc_object(c_void_p=int(widget.winId()))
        win = view.window()
        if win is None:
            return
        win.setLevel_(AppKit.NSFloatingWindowLevel)
        win.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            | AppKit.NSWindowCollectionBehaviorIgnoresCycle
        )
        win.setHidesOnDeactivate_(False)
        widget.setProperty("sf_floating", True)
    except Exception as e:
        log.info("float_window failed: %s", e)


def bring_to_front():
    """A menu bar app is never the active app by itself; its normal windows (settings, calendar) need this."""
    if not IS_MAC:
        return
    try:
        _appkit().NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


def accessory_app():
    """No Dock icon and no app menu, the menu bar icon is enough (the packaged app sets LSUIElement too)."""
    if not IS_MAC:
        return
    try:
        AppKit = _appkit()
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


# ------------------------------------------------------------------ session state
def idle_seconds():
    if not IS_MAC:
        return 0.0
    Q = _q()
    return float(
        Q.CGEventSourceSecondsSinceLastEventType(Q.kCGEventSourceStateCombinedSessionState, Q.kCGAnyInputEventType)
    )


def screen_locked():
    if not IS_MAC:
        return False
    d = _q().CGSessionCopyCurrentDictionary()
    return bool(d and d.get("CGSSessionScreenIsLocked"))


def has_route():
    """A default network route exists (what macOS itself knows; nothing is sent). True when unsure."""
    try:
        r = subprocess.run(["/sbin/route", "-n", "get", "default"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


class _Addr(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32), ("element", ctypes.c_uint32)]


def _fourcc(s):
    return int.from_bytes(s.encode("ascii"), "big")


def mic_in_use():
    """Some app is recording from the default microphone right now (CoreAudio; no permission needed)."""
    if not IS_MAC:
        return False
    try:
        ca = _cache.get("coreaudio")
        if ca is None:
            ca = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
            ca.AudioObjectGetPropertyData.argtypes = [
                ctypes.c_uint32,
                ctypes.POINTER(_Addr),
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_void_p,
            ]
            ca.AudioObjectGetPropertyData.restype = ctypes.c_int32
            _cache["coreaudio"] = ca
        get = ca.AudioObjectGetPropertyData
        dev, size = ctypes.c_uint32(0), ctypes.c_uint32(4)
        addr = _Addr(_fourcc("dIn "), _fourcc("glob"), 0)
        if get(1, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(dev)) or not dev.value:
            return False
        running, size = ctypes.c_uint32(0), ctypes.c_uint32(4)
        addr = _Addr(_fourcc("gone"), _fourcc("glob"), 0)
        if get(dev.value, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(running)):
            return False
        return bool(running.value)
    except Exception:
        return False


def running_app(bundle_ids):
    """The first running app with one of these bundle ids, or None."""
    if not IS_MAC:
        return None
    for app in _appkit().NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() in bundle_ids:
            return app
    return None


def activate(bundle_ids):
    app = running_app(bundle_ids)
    if app is None:
        return False
    AppKit = _appkit()
    app.unhide()
    return bool(app.activateWithOptions_(AppKit.NSApplicationActivateAllWindows))


def open_path(target, reveal=False):
    """Open a file, folder or URL with its default app (reveal=True selects it in Finder)."""
    subprocess.Popen(["/usr/bin/open", "-R", target] if reveal else ["/usr/bin/open", target])


def login_path():
    """PATH as the user's login shell sets it up. Apps started from Finder only get /usr/bin:/bin:..., so CLIs from
    Homebrew, npm or ~/.local would otherwise not be found."""
    if "login_path" in _cache:
        return _cache["login_path"]
    shell = os.environ.get("SHELL") or "/bin/zsh"
    found = ""
    try:
        r = subprocess.run(
            [shell, "-ilc", 'printf "__SF__%s__SF__" "$PATH"'],
            capture_output=True,
            text=True,
            timeout=6,
            stdin=subprocess.DEVNULL,
        )
        if "__SF__" in r.stdout:
            found = r.stdout.split("__SF__")[1]
    except (OSError, subprocess.SubprocessError):
        pass
    home = os.path.expanduser("~")
    extra = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        f"{home}/.local/bin",
        f"{home}/.npm-global/bin",
        f"{home}/.bun/bin",
        f"{home}/.cargo/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    parts = []
    for p in (found or os.environ.get("PATH", "")).split(":") + extra:
        if p and p not in parts:
            parts.append(p)
    _cache["login_path"] = ":".join(parts)
    return _cache["login_path"]


# ------------------------------------------------------------------ permissions
PANES = {
    "screen": "Privacy_ScreenCapture",
    "input": "Privacy_ListenEvent",
    "accessibility": "Privacy_Accessibility",
    "automation": "Privacy_Automation",
    "location": "Privacy_LocationServices",
}


def open_privacy(kind):
    subprocess.Popen(["/usr/bin/open", f"x-apple.systempreferences:com.apple.preference.security?{PANES[kind]}"])


def screen_capture_ok(ask=False):
    if not IS_MAC:
        return False
    Q = _q()
    try:
        if Q.CGPreflightScreenCaptureAccess():
            return True
        return bool(Q.CGRequestScreenCaptureAccess()) if ask else False
    except Exception:
        return False


def input_ok(ask=False):
    if not IS_MAC:
        return False
    Q = _q()
    try:
        if Q.CGPreflightListenEventAccess():
            return True
        return bool(Q.CGRequestListenEventAccess()) if ask else False
    except Exception:
        return False


def accessibility_ok(ask=False):
    if not IS_MAC:
        return False
    try:
        import ApplicationServices as AS

        return bool(AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: bool(ask)}))
    except Exception:
        return False


def osascript(script, timeout=10):
    """(ok, output) of an AppleScript. The first call per target app makes macOS ask for Automation access."""
    try:
        r = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False, ""


def ask_finder():
    """Triggers the one-time Automation question for Finder (Trash and desktop icons)."""
    threading.Thread(target=osascript, args=('tell application "Finder" to count items of trash',), daemon=True).start()


# ------------------------------------------------------------------ Finder: Trash and desktop icons
TRASH_SCRIPT = """
tell application "Finder"
    with timeout of 20 seconds
        set n to count items of trash
        set s to 0
        repeat with i in (items of trash)
            try
                set s to s + (physical size of i)
            end try
        end repeat
    end timeout
end tell
return (n as text) & "|" & (s as text)
"""


def trash_info():
    """(bytes, items) of the Trash through Finder, or None."""
    ok, out = osascript(TRASH_SCRIPT, timeout=30)
    if not ok or "|" not in out:
        return None
    n, s = out.split("|", 1)
    try:
        return int(float(s.replace(",", "."))), int(n)
    except ValueError:
        return None


def empty_trash():
    """Finder asks first when its 'warn before emptying' option is on (the default)."""
    osascript('tell application "Finder" to empty trash', timeout=120)


def dock_trash_rect():
    """The Trash tile in the Dock (needs Accessibility; None without it)."""
    if not IS_MAC or not accessibility_ok():
        return None
    try:
        import ApplicationServices as AS

        dock = running_app({"com.apple.dock"})
        if dock is None:
            return None
        root = AS.AXUIElementCreateApplication(dock.processIdentifier())
        _err, lists = AS.AXUIElementCopyAttributeValue(root, "AXChildren", None)
        for lst in lists or []:
            _err, items = AS.AXUIElementCopyAttributeValue(lst, "AXChildren", None)
            for it in items or []:
                _err, sub = AS.AXUIElementCopyAttributeValue(it, "AXSubrole", None)
                if sub != "AXTrashDockItem":
                    continue
                _err, pos = AS.AXUIElementCopyAttributeValue(it, "AXPosition", None)
                _err, size = AS.AXUIElementCopyAttributeValue(it, "AXSize", None)
                _ok, p = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
                _ok, s = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
                return float(p.x), float(p.y), float(p.x + s.width), float(p.y + s.height)
    except Exception as e:
        log.info("dock trash lookup failed: %s", e)
    return None


ICONS_SCRIPT = """
tell application "Finder"
    set out to ""
    set s to icon size of icon view options of window of desktop
    repeat with i in (items of desktop)
        try
            set p to desktop position of i
            set out to out & (item 1 of p) & "," & (item 2 of p) & ";"
        end try
    end repeat
end tell
return (s as text) & "|" & out
"""
_icons = {"at": 0.0, "items": [], "busy": False}


def _read_icons():
    try:
        ok, out = osascript(ICONS_SCRIPT, timeout=8)
        items = []
        if ok and "|" in out:
            size, rest = out.split("|", 1)
            half = max(16.0, float(size)) / 2
            for pair in rest.split(";"):
                if "," not in pair:
                    continue
                x, y = (float(v) for v in pair.split(",")[:2])
                glyph = (x - half, y - half, x + half, y + half)
                items.append(((x - half - 8, y - half, x + half + 8, y + half + 30), glyph))
            _icons["items"] = items
        else:
            _icons["items"] = []
        _icons["at"] = time.time()
    finally:
        _icons["busy"] = False


def desktop_icons(max_age=8.0):
    """Cached [(bounds, glyph)] of the desktop icons; the Finder query runs in the background."""
    if not IS_MAC:
        return []
    if time.time() - _icons["at"] > max_age and not _icons["busy"]:
        _icons["busy"] = True
        threading.Thread(target=_read_icons, daemon=True).start()
    return _icons["items"]


# ------------------------------------------------------------------ global hotkeys (Carbon, no permission needed)
CARBON_MODS = {
    "cmd": 0x100,
    "win": 0x100,
    "meta": 0x100,
    "shift": 0x200,
    "alt": 0x800,
    "option": 0x800,
    "opt": 0x800,
    "ctrl": 0x1000,
    "control": 0x1000,
}
KEYCODES = {
    "a": 0,
    "s": 1,
    "d": 2,
    "f": 3,
    "h": 4,
    "g": 5,
    "z": 6,
    "x": 7,
    "c": 8,
    "v": 9,
    "b": 11,
    "q": 12,
    "w": 13,
    "e": 14,
    "r": 15,
    "y": 16,
    "t": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "9": 25,
    "7": 26,
    "8": 28,
    "0": 29,
    "o": 31,
    "u": 32,
    "i": 34,
    "p": 35,
    "l": 37,
    "j": 38,
    "k": 40,
    "n": 45,
    "m": 46,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    "f13": 105,
    "f14": 107,
    "f15": 113,
    "f16": 106,
    "f17": 64,
    "f18": 79,
    "f19": 80,
    "f20": 90,
    "space": 49,
    "tab": 48,
    "esc": 53,
    "escape": 53,
    "enter": 36,
    "return": 36,
    "backspace": 51,
    "delete": 117,
    "del": 117,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "pgup": 116,
    "pagedown": 121,
    "pgdn": 121,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "insert": 114,
    "ins": 114,
}


def parse_hotkey(text):
    """'Ctrl+Alt+F9' -> (carbon modifiers, key code) or None."""
    if not text:
        return None
    mods, code = 0, None
    for part in text.replace(" ", "").split("+"):
        p = part.lower()
        if p in CARBON_MODS:
            mods |= CARBON_MODS[p]
        elif p in KEYCODES:
            code = KEYCODES[p]
        else:
            return None
    return (mods, code) if code is not None else None


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _HotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


class CarbonHotkeys:
    def __init__(self, on_action):
        self.on_action = on_action
        self.refs = {}
        self.ids = {}
        self._lib = None
        self._handler = None

    def _setup(self):
        if self._lib is not None:
            return self._lib
        lib = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        lib.GetApplicationEventTarget.restype = ctypes.c_void_p
        lib.InstallEventHandler.argtypes = [
            ctypes.c_void_p,
            _HANDLER,
            ctypes.c_uint32,
            ctypes.POINTER(_EventTypeSpec),
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.RegisterEventHotKey.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            _HotKeyID,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        lib.GetEventParameter.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]

        def handle(_call, event, _data):
            hk = _HotKeyID()
            if (
                lib.GetEventParameter(
                    event, _fourcc("----"), _fourcc("hkid"), None, ctypes.sizeof(hk), None, ctypes.byref(hk)
                )
                == 0
            ):
                action = self.ids.get(hk.id)
                if action:
                    try:
                        self.on_action(action)
                    except Exception:
                        log.exception("hotkey action failed")
            return 0

        self._handler = _HANDLER(handle)
        spec = _EventTypeSpec(_fourcc("keyb"), 5)
        lib.InstallEventHandler(lib.GetApplicationEventTarget(), self._handler, 1, ctypes.byref(spec), None, None)
        self._lib = lib
        return lib

    def register(self, mapping, actions):
        """mapping: {action: 'Ctrl+Alt+F9'}. Returns the actions whose key is taken."""
        self.unregister()
        failed = []
        try:
            lib = self._setup()
        except OSError:
            return []
        for i, action in enumerate(actions, start=1):
            key = parse_hotkey(mapping.get(action, ""))
            if not key:
                continue
            ref = ctypes.c_void_p()
            if (
                lib.RegisterEventHotKey(
                    key[1], key[0], _HotKeyID(_fourcc("SmFi"), i), lib.GetApplicationEventTarget(), 0, ctypes.byref(ref)
                )
                == 0
            ):
                self.refs[i], self.ids[i] = ref, action
            else:
                failed.append(action)
        return failed

    def unregister(self):
        if self._lib is not None:
            for ref in self.refs.values():
                self._lib.UnregisterEventHotKey(ref)
        self.refs, self.ids = {}, {}


# ------------------------------------------------------------------ click and key counter (Input Monitoring)
class InputTap:
    """Counts presses through a listen-only event tap. Only the event type is looked at: no keys, no positions."""

    def __init__(self, on_press):
        self.on_press = on_press
        self.tap = None
        self.source = None
        self._cb = None

    def start(self):
        if self.tap is not None:
            return True
        if not input_ok():
            return False
        Q = _q()
        import CoreFoundation as CF

        mouse = (Q.kCGEventLeftMouseDown, Q.kCGEventRightMouseDown, Q.kCGEventOtherMouseDown)
        mask = Q.CGEventMaskBit(Q.kCGEventKeyDown)
        for t in mouse:
            mask |= Q.CGEventMaskBit(t)

        def callback(_proxy, kind, event, _refcon):
            if kind in (Q.kCGEventTapDisabledByTimeout, Q.kCGEventTapDisabledByUserInput):
                if self.tap is not None:
                    Q.CGEventTapEnable(self.tap, True)
            elif kind == Q.kCGEventKeyDown:
                if not Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventAutorepeat):
                    self.on_press("key", 1)
            elif kind in mouse:
                self.on_press("mouse", 1)
            return event

        self._cb = callback
        tap = Q.CGEventTapCreate(
            Q.kCGSessionEventTap, Q.kCGHeadInsertEventTap, Q.kCGEventTapOptionListenOnly, mask, callback, None
        )
        if tap is None:
            return False
        self.tap = tap
        self.source = CF.CFMachPortCreateRunLoopSource(None, tap, 0)
        CF.CFRunLoopAddSource(CF.CFRunLoopGetMain(), self.source, CF.kCFRunLoopCommonModes)
        Q.CGEventTapEnable(tap, True)
        return True

    def stop(self):
        if self.tap is None:
            return
        import CoreFoundation as CF

        Q = _q()
        Q.CGEventTapEnable(self.tap, False)
        CF.CFRunLoopRemoveSource(CF.CFRunLoopGetMain(), self.source, CF.kCFRunLoopCommonModes)
        CF.CFMachPortInvalidate(self.tap)
        self.tap = self.source = self._cb = None
