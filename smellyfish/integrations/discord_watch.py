"""Discord voice status.

Without setup: Windows records which app uses the microphone right now
(CapabilityAccessManager). Discord holding the mic means you are in a voice call.
On macOS: Discord is running and the microphone is in use (CoreAudio).

With your own Discord application (client id + secret, redirect URI added in the
Developer Portal), the local RPC pipe also reports mute / deafen.
"""

import json
import os
import struct
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid

from PySide6.QtCore import QObject, QTimer, Signal

MIC_KEY = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged"
SCOPES = ["rpc", "rpc.voice.read", "rpc.notifications.read"]


MAC_BUNDLES = {"com.hnc.Discord", "com.hnc.DiscordPTB", "com.hnc.DiscordCanary"}


def discord_mic_in_use():
    if sys.platform == "darwin":
        from smellyfish.system import mac

        return mac.running_app(MAC_BUNDLES) is not None and mac.mic_in_use()
    if sys.platform != "win32":
        return False
    import winreg

    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, MIC_KEY)
    except OSError:
        return False
    with root:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                return False
            i += 1
            if "discord" not in name.lower():
                continue
            try:
                with winreg.OpenKey(root, name) as k:
                    stop, _ = winreg.QueryValueEx(k, "LastUsedTimeStop")
                    start, _ = winreg.QueryValueEx(k, "LastUsedTimeStart")
                if stop == 0 and start > 0:
                    return True
            except OSError:
                pass


DISCORD_EXES = {"discord.exe", "discordptb.exe", "discordcanary.exe"}


def _discord_windows():
    """Top-level windows owned by a Discord process: [(hwnd, visible_on_screen)]."""
    if sys.platform != "win32":
        return []
    import ctypes

    from smellyfish.system.wincompat import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    try:
        dwm = ctypes.windll.dwmapi
    except OSError:
        dwm = None
    names, found = {}, []

    def exe_of(pid):
        if pid not in names:
            name = ""
            h = kernel32.OpenProcess(0x1000, False, pid)
            if h:
                buf = ctypes.create_unicode_buffer(520)
                size = wintypes.DWORD(len(buf))
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    name = os.path.basename(buf.value).lower()
                kernel32.CloseHandle(h)
            names[pid] = name
        return names[pid]

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if exe_of(pid.value) not in DISCORD_EXES or user32.GetWindow(hwnd, 4) or not user32.GetWindowTextLengthW(hwnd):
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        cloaked = wintypes.DWORD(0)
        if dwm is not None:
            dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        shown = (
            bool(user32.IsWindowVisible(hwnd))
            and not user32.IsIconic(hwnd)
            and not cloaked.value
            and rect.right - rect.left > 50
            and rect.bottom - rect.top > 50
        )
        found.append((hwnd, shown))
        return True

    user32.EnumWindows(each, 0)
    return found


def discord_on_screen():
    """True while a Discord window is open (not minimized, not only in the tray)."""
    if sys.platform == "darwin":
        from smellyfish.system import mac

        return bool(mac.windows_of({"discord", "discord ptb", "discord canary"}))
    try:
        return any(shown for _h, shown in _discord_windows())
    except Exception:
        return False


def message_link(info):
    """discord:// deep link to a message, or None when the ids are missing."""
    channel, message = info.get("channel_id"), info.get("message_id")
    guild = info.get("guild_id") or ("@me" if info.get("dm") else None)
    if not channel or not guild:
        return None
    return f"discord://-/channels/{guild}/{channel}" + (f"/{message}" if message else "")


def bring_forward():
    """Restore the Discord window (also from the tray). Returns False when none was found."""
    if sys.platform == "darwin":
        from smellyfish.system import mac

        return mac.activate(MAC_BUNDLES)
    if sys.platform != "win32":
        return False
    import ctypes

    wins = _discord_windows()
    if not wins:
        return False
    hwnd = next((h for h, shown in wins if shown), wins[0][0])
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
    user32.SetForegroundWindow(hwnd)
    return True


class _Socket:
    """Discord's local IPC socket on macOS, with the file-like read/write the named pipe has on Windows."""

    def __init__(self, path):
        import socket

        self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.s.connect(path)
        except OSError:
            self.s.close()
            raise

    def write(self, data):
        self.s.sendall(data)

    def read(self, n):
        out = b""
        while len(out) < n:
            part = self.s.recv(n - len(out))
            if not part:
                break
            out += part
        return out

    def close(self):
        self.s.close()


def _ipc_dirs():
    import tempfile

    dirs = [os.environ.get(k) for k in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP")] + [tempfile.gettempdir(), "/tmp"]
    out = []
    for d in dirs:
        if d and d not in out:
            out.append(d)
    return out


class Pipe:
    def __init__(self):
        self.f = None
        for n in range(10):
            if sys.platform == "win32":
                try:
                    self.f = open(rf"\\?\pipe\discord-ipc-{n}", "r+b", buffering=0)
                    break
                except OSError:
                    continue
            for d in _ipc_dirs():
                try:
                    self.f = _Socket(os.path.join(d, f"discord-ipc-{n}"))
                    break
                except OSError:
                    continue
            if self.f is not None:
                break
        if self.f is None:
            raise OSError("Discord is not running")

    def send(self, op, payload):
        data = json.dumps(payload).encode()
        self.f.write(struct.pack("<II", op, len(data)) + data)

    def recv(self):
        head = self.f.read(8)
        if len(head) < 8:
            raise OSError("pipe closed")
        op, n = struct.unpack("<II", head)
        return op, json.loads(self.f.read(n) or b"{}")

    def cmd(self, cmd, args=None, evt=None):
        msg = {"cmd": cmd, "args": args or {}, "nonce": str(uuid.uuid4())}
        if evt:
            msg["evt"] = evt
        self.send(1, msg)
        return msg["nonce"]

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass


class DiscordWatch(QObject):
    changed = Signal(object)  # {"in_call", "mute", "deaf", "rpc"}
    message = Signal(str, str, object)  # title, body, {"channel_id", "message_id", "guild_id", "dm"}
    rpc_status = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.state = {"in_call": False, "mute": False, "deaf": False, "rpc": False}
        self._rpc_call = None
        self._thread = None
        self._authorize = False
        self._stop = False
        self._fails = 0
        self._next_try = 0.0
        self._guilds = {}
        self.timer = QTimer(self, timeout=self.poll)
        self.timer.start(3000)

    def poll(self):
        if not self.cfg.get("discord"):
            return self._set(in_call=False, mute=False, deaf=False)
        in_call = self._rpc_call if self.state["rpc"] and self._rpc_call is not None else discord_mic_in_use()
        self._set(in_call=bool(in_call))
        if (
            self.cfg.get("discord_client_id")
            and self.cfg.get("discord_token")
            and not self._alive()
            and time.time() >= self._next_try
        ):
            self.start_rpc(False)

    def _set(self, **kw):
        new = dict(self.state, **kw)
        if new != self.state:
            self.state = new
            self.changed.emit(dict(new))

    def _alive(self):
        return self._thread is not None and self._thread.is_alive()

    def start_rpc(self, authorize=True):
        if self._alive():
            return
        self._stop = False
        if authorize:
            self._fails, self._next_try = 0, 0.0
        self._authorize = authorize
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def disconnect(self):
        self._stop = True
        self.cfg.set("discord_token", None)
        self._set(mute=False, deaf=False)
        self.rpc_status.emit("Disconnected")

    def _failed(self, text):
        self._fails += 1
        delay = min(120, 5 * 2 ** min(self._fails, 5))
        self._next_try = time.time() + delay
        self.rpc_status.emit(f"{text} - retrying in {delay}s" if self.cfg.get("discord_token") else text)

    # ------------------------------------------------------------ RPC thread
    def _token_request(self, data):
        body = urllib.parse.urlencode(
            dict(data, client_id=self.cfg["discord_client_id"], client_secret=self.cfg.get("discord_client_secret", ""))
        ).encode()
        req = urllib.request.Request(
            "https://discord.com/api/oauth2/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Smellyfish (desktop pet)"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            tok = json.loads(r.read())
        tok["expires_at"] = time.time() + tok.get("expires_in", 0) - 60
        self.cfg.set("discord_token", tok)
        return tok

    def _run(self):
        cid = self.cfg.get("discord_client_id")
        if not cid:
            return self.rpc_status.emit("Enter a client id first")
        try:
            pipe = Pipe()
        except OSError as e:
            return self._failed(str(e))
        try:
            pipe.send(0, {"v": 1, "client_id": cid})
            op, msg = pipe.recv()
            if msg.get("evt") != "READY":
                raise OSError(msg.get("data", {}).get("message", "handshake failed"))
            tok = self.cfg.get("discord_token") or {}
            if tok and tok.get("expires_at", 0) < time.time() and tok.get("refresh_token"):
                try:
                    tok = self._token_request({"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
                except Exception:
                    tok = {}
            if not tok.get("access_token"):
                if not self._authorize:
                    return self.rpc_status.emit("Not connected")
                self.rpc_status.emit("Approve Smellyfish in Discord...")
                pipe.cmd("AUTHORIZE", {"client_id": cid, "scopes": SCOPES})
                op, msg = pipe.recv()
                code = (msg.get("data") or {}).get("code")
                if not code:
                    raise OSError((msg.get("data") or {}).get("message", "authorization declined"))
                tok = self._token_request(
                    {
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.cfg.get("discord_redirect") or "http://localhost",
                    }
                )
            pipe.cmd("AUTHENTICATE", {"access_token": tok["access_token"]})
            op, msg = pipe.recv()
            if msg.get("evt") == "ERROR":
                self.cfg.set("discord_token", None)
                raise OSError((msg.get("data") or {}).get("message", "authentication failed"))
            self.rpc_status.emit("Connected")
            self._fails = 0
            pipe.cmd("GET_VOICE_SETTINGS")
            pipe.cmd("GET_SELECTED_VOICE_CHANNEL")
            pipe.cmd("SUBSCRIBE", evt="VOICE_SETTINGS_UPDATE")
            pipe.cmd("SUBSCRIBE", evt="VOICE_CHANNEL_SELECT")
            pipe.cmd("SUBSCRIBE", evt="NOTIFICATION_CREATE")
            self.state["rpc"] = True
            waiting = {}
            while self.cfg.get("discord") and not self._stop:
                op, msg = pipe.recv()
                data = msg.get("data") or {}
                cmd, evt = msg.get("cmd"), msg.get("evt")
                if cmd == "GET_CHANNEL" and msg.get("nonce") in waiting:
                    title, body, info = waiting.pop(msg["nonce"])
                    if evt != "ERROR":
                        info["guild_id"] = data.get("guild_id")
                        info["dm"] = data.get("type") in (1, 3)
                        self._guilds[info["channel_id"]] = (info["guild_id"], info["dm"])
                    self.message.emit(title, body, info)
                    continue
                if cmd == "GET_VOICE_SETTINGS" or evt == "VOICE_SETTINGS_UPDATE":
                    self._set(mute=bool(data.get("mute")), deaf=bool(data.get("deaf")))
                elif cmd == "GET_SELECTED_VOICE_CHANNEL":
                    self._rpc_call = bool(data and data.get("id"))
                elif evt == "VOICE_CHANNEL_SELECT":
                    self._rpc_call = bool(data.get("channel_id"))
                elif evt == "NOTIFICATION_CREATE" and self.cfg.get("discord_messages"):
                    title, body = str(data.get("title") or "Discord"), str(data.get("body") or "")
                    info = {
                        "channel_id": str(data.get("channel_id") or ""),
                        "message_id": str((data.get("message") or {}).get("id") or ""),
                    }
                    known = self._guilds.get(info["channel_id"])
                    if known or not info["channel_id"]:
                        if known:
                            info["guild_id"], info["dm"] = known
                        self.message.emit(title, body, info)
                    else:
                        waiting[pipe.cmd("GET_CHANNEL", {"channel_id": info["channel_id"]})] = (title, body, info)
        except Exception as e:
            self._failed(f"Discord: {e}")
        finally:
            self.state["rpc"] = False
            self._rpc_call = None
            pipe.close()
