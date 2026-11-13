"""Persistent user settings and autostart (Windows registry, macOS LaunchAgent)."""

import base64
import contextlib
import ctypes
import json
import logging
import os
import sys
import time

from smellyfish.paths import HOME_DIR as DIR
from smellyfish.paths import pet_command

log = logging.getLogger("smellyfish.settings")

PATH = os.path.join(DIR, "settings.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Smellyfish"

DEFAULTS = {
    "scale": 4,
    "opacity": 1.0,
    "on_top": True,
    "gravity": True,
    "sit_on_windows": True,
    "sit_on_icons": True,
    "wander": True,
    "eyes_follow": True,
    "ask_in_bubble": True,
    "perm_in_bubble": True,
    "done_bubble": True,
    "dnd": False,
    "sleep_after_min": 3,
    "position": None,
    "home": None,
    "react_cpu": True,
    "react_battery": True,
    "react_network": True,
    "react_greet": True,
    "react_night": True,
    "react_hover": True,
    "react_music": True,
    "beat_sync": True,
    "game_mode": True,
    "react_lock": True,
    "fidgets": True,
    "window_hop": True,
    "ceiling_hang": True,
    "dark_ui": True,
    "lan_name": "",
    "lan_visits": True,
    "lan_letters": True,
    "llm_enabled": False,
    "llm_persona": True,
    "llm_max_tokens": 260,
    "llm_think": "off",
    "llm_ctx": 0,
    "llm_temp": 0.7,
    "llm_history": 6,
    "llm_autostart": True,
    "llm_binary": "",
    "llm_models_dir": "",
    "llm_backend": "ollama",
    "llm_url": "",
    "llm_model": "",
    "llm_prompt": "",
    "llm_reply": "bubble",
    "llm_autoload": True,
    "llm_idle_min": 5,
    "llm_unload_on_quit": True,
    "trips_home": True,
    "show_house": False,
    "plant_watered_at": 0,
    "codex_hooks": False,
    "gemini_hooks": False,
    "cursor_hooks": False,
    "copilot_hooks": False,
    "antigravity_hooks": False,
    "shell_menu": False,
    "deepseek_hooks": False,
    "usage_warn": 80,
    "usage_critical": True,
    "usage_warned": {},
    "trash_watch": True,
    "trash_gb": 2,
    "trash_days": 7,
    "trash_since": None,
    "trash_reported_at": 0,
    "discord": True,
    "discord_messages": True,
    "discord_presence": True,
    "discord_client_id": "",
    "discord_client_secret": "",
    "discord_redirect": "http://localhost",
    "discord_token": None,
    "mute_all": False,
    "sound_done": True,
    "sfx": True,
    "volume": 60,
    "notify_volume": 70,
    "auto_update": True,
    "clicker": False,
    "break_nudge": True,
    "temp_unit": "C",
    "seasonal": True,
    "hat": "auto",
    "accessory": "auto",
    "auto_water": True,
    "focus_min": 25,
    "break_min": 5,
    "hotkeys": {
        "toggle": "Ctrl+Alt+F9",
        "home": "Ctrl+Alt+F10",
        "dnd": "Ctrl+Alt+F11",
        "history": "Ctrl+Alt+F12",
        "focus": "Ctrl+Alt+F8",
        "chase": "Ctrl+Alt+F7",
        "mini": "Ctrl+Alt+F6",
        "todo": "Ctrl+Alt+F5",
    },
    "skin": "lavender",
    "skin_color": "#c492ec",
    "weather": False,
    "weather_place": "",
    "weather_auto": False,
    "weather_ip": False,
    "weather_loc": None,
    "react_clipboard": True,
    "mini": False,
    "mini_side": "right",
    "mini_lift": 0,
    "monitor": "primary",
    "task_timer": True,
    "talk_blips": True,
    "reminders": [],
    "todos": [],
    "seen_version": "",
    "todo_greet": True,
    "onboarded": False,
    "calendars": [],
    "calendar_view": "month",
    "calendar_sidebar": False,
    "calendar_show_todos": True,
    "calendar_remind_min": 10,
    "calendar_notified": {},
    "media": True,
    "media_note": "playing",
    "media_exclude": [],
    "mac_media_ok": False,
    "tentacle_sim": True,
    "stats": {},
    "achievements": {},
}


if sys.platform == "darwin":
    # these need a macOS permission, so they start off and ask when switched on
    DEFAULTS.update(beat_sync=False, sit_on_icons=False, trash_watch=False)

SECRETS = ("discord_client_secret", "discord_token")
SEALED = ("_dpapi", "_kc")
KEYCHAIN_SERVICE = "Smellyfish"
_KEY = {}


class _Blob(ctypes.Structure):
    _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_char))]


def _dpapi(raw, protect):
    src = _Blob(len(raw), ctypes.cast(ctypes.create_string_buffer(raw, len(raw)), ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    crypt = ctypes.windll.crypt32
    fn = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(out)):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.data, out.size)
    finally:
        ctypes.windll.kernel32.LocalFree(out.data)


def _keychain_account():
    import hashlib

    if os.environ.get("SMELLYFISH_HOME"):
        return "settings-key-" + hashlib.sha256(DIR.encode()).hexdigest()[:10]
    return "settings-key"


def _mac_key():
    """A random key kept in the login Keychain; the secrets in settings.json are encrypted with it."""
    if "key" in _KEY:
        return _KEY["key"]
    import subprocess

    account = _keychain_account()
    r = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    hexkey = r.stdout.strip()
    if r.returncode == 0 and len(hexkey) == 64:
        key = bytes.fromhex(hexkey)
    elif r.returncode == 44:  # not found: first use
        key = os.urandom(32)
        # through stdin, so the key never shows up in a process list
        cmd = f"add-generic-password -U -s {KEYCHAIN_SERVICE} -a {account} -l Smellyfish -w {key.hex()}" + chr(10)
        subprocess.run(["/usr/bin/security", "-i"], input=cmd, capture_output=True, text=True, timeout=15)
        _KEY.pop("key", None)
        check = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if check.stdout.strip() != key.hex():
            raise OSError("Keychain refused the key")
    else:
        raise OSError(f"Keychain not readable ({r.returncode})")
    _KEY["key"] = key
    return key


def _mac_crypt(raw, protect):
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

    box = ChaCha20Poly1305(_mac_key())
    if protect:
        nonce = os.urandom(12)
        return nonce + box.encrypt(nonce, raw, b"smellyfish")
    return box.decrypt(raw[:12], raw[12:], b"smellyfish")


def seal(value):
    """Secrets are stored encrypted for this user (Windows: DPAPI, macOS: a key in the Keychain), so a copied
    settings file does not reveal them."""
    if not value or sys.platform not in ("win32", "darwin"):
        return value
    try:
        raw = json.dumps(value).encode()
        if sys.platform == "darwin":
            return {"_kc": base64.b64encode(_mac_crypt(raw, True)).decode()}
        return {"_dpapi": base64.b64encode(_dpapi(raw, True)).decode()}
    except Exception:
        return value


def unseal(value):
    if not (isinstance(value, dict) and any(k in value for k in SEALED)):
        return value
    try:
        if "_kc" in value:
            return json.loads(_mac_crypt(base64.b64decode(value["_kc"]), False))
        return json.loads(_dpapi(base64.b64decode(value["_dpapi"]), False))
    except Exception:
        return None


def _plain(data):
    """The known keys of a settings file, with secrets readable; unreadable secrets fall back to the default."""
    out = {k: v for k, v in data.items() if k in DEFAULTS}
    for k in SECRETS:
        if k in out:
            v = unseal(out[k])
            out[k] = DEFAULTS[k] if v is None else v
    return out


def _unsealed(data):
    return any(data.get(k) and not (isinstance(data[k], dict) and any(s in data[k] for s in SEALED)) for k in SECRETS)


class Settings(dict):
    """Settings dict that never loses data:
    - an unreadable file is kept aside (settings.broken-*.json) instead of being overwritten
    - every start keeps rotating backups (settings.json.bak1..3)
    - saving merges only this process's changes into what is on disk, so a second
      instance (or an old version) cannot wipe values it never touched."""

    def __init__(self):
        super().__init__(DEFAULTS)
        self._dirty = set()
        self.readonly = False
        self.on_error = None
        self.fresh = not os.path.exists(PATH)
        if os.path.exists(PATH):
            data, error = None, None
            for _ in range(40):
                try:
                    with open(PATH, encoding="utf-8") as f:
                        data = json.load(f)
                    break
                except OSError as e:
                    error = e
                    time.sleep(0.05)
                except ValueError as e:
                    error = e
                    break
            if data is not None:
                dict.update(self, _plain(data))
                if "onboarded" not in data:
                    self["onboarded"] = True
                self._backup()
                if sys.platform in ("win32", "darwin") and _unsealed(data):
                    self._dirty.update(k for k in SECRETS if data.get(k))
                    if self.save():
                        self._seal_backups()
                log.info(
                    "loaded settings (house %s, %d achievements)",
                    self.get("show_house"),
                    len(self.get("achievements") or {}),
                )
            elif isinstance(error, ValueError):
                log.warning("settings.json is damaged (%s), restoring from a backup", error)
                self._recover()
            else:
                log.error("settings.json could not be read (%s); using a backup, file left untouched", error)
                self._load_backup()

    def _backup(self):
        for i in (3, 2):
            older, newer = f"{PATH}.bak{i}", f"{PATH}.bak{i - 1}"
            if os.path.exists(newer):
                os.replace(newer, older)
        try:
            import shutil

            shutil.copy2(PATH, f"{PATH}.bak1")
        except OSError:
            pass

    def _seal_backups(self):
        for i in (1, 2, 3):
            path = f"{PATH}.bak{i}"
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if not _unsealed(data):
                    continue
                data.update({k: seal(data[k]) for k in SECRETS if data.get(k)})
                with open(path + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(path + ".tmp", path)
            except (OSError, ValueError):
                continue

    def _recover(self):
        """The file could not be read: keep it, then try the newest readable backup."""
        import time

        try:
            os.replace(PATH, os.path.join(DIR, f"settings.broken-{int(time.time())}.json"))
        except OSError:
            self.readonly = True
        if self._load_backup():
            self._dirty = {k for k in DEFAULTS if k in self}

    def _load_backup(self):
        for i in (1, 2, 3):
            try:
                with open(f"{PATH}.bak{i}", encoding="utf-8") as f:
                    data = json.load(f)
                dict.update(self, _plain(data))
                return True
            except (OSError, ValueError):
                continue
        return False

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._dirty.add(key)

    def save(self):
        """Merge only the keys changed here into the file, under a lock shared by all processes.
        Returns True on success; on failure the changes stay pending and are retried by the next save."""
        if self.readonly:
            return False
        try:
            self._save()
            return True
        except Exception as e:
            log.exception("saving settings failed")
            if self.on_error:
                self.on_error(e)
            return False

    def _save(self):
        os.makedirs(DIR, exist_ok=True)
        with _file_lock(PATH + ".lock"):
            disk = {}
            try:
                with open(PATH, encoding="utf-8") as f:
                    disk = json.load(f)
            except (OSError, ValueError):
                disk = {}
            merged = dict(DEFAULTS, **_plain(disk))
            merged.update({k: self[k] for k in self._dirty})
            if "stats" in self._dirty:
                merged["stats"] = merge_stats(disk.get("stats"), self["stats"])
            if "achievements" in self._dirty:
                merged["achievements"] = merge_unlocked(disk.get("achievements"), self["achievements"])
            tmp = PATH + f".{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(merged, **{k: seal(merged[k]) for k in SECRETS}), f, indent=2)
            for _ in range(50):
                try:
                    os.replace(tmp, PATH)
                    break
                except PermissionError:
                    time.sleep(0.02)
            else:
                os.replace(tmp, PATH)
            log.info("saved %s (pid %s)", ", ".join(sorted(self._dirty)) or "-", os.getpid())
            self._dirty.clear()
            for k, v in merged.items():
                dict.__setitem__(self, k, v)

    def set(self, key, value):
        self[key] = value
        self.save()


def merge_stats(disk, mine):
    """Counters only grow, so a stale copy (an old backup, a second process) can never lower them."""
    disk, mine = dict(disk or {}) if isinstance(disk, dict) else {}, dict(mine or {})
    out = dict(disk)
    for k, v in mine.items():
        old = out.get(k)
        if isinstance(v, (int, float)) and isinstance(old, (int, float)) and not isinstance(v, bool):
            out[k] = max(old, v)
        elif isinstance(v, str) and isinstance(old, str):
            out[k] = max(old, v)
        else:
            out[k] = v
    return out


def merge_unlocked(disk, mine):
    out = dict(disk or {}) if isinstance(disk, dict) else {}
    for k, t in (mine or {}).items():
        out[k] = min(out[k], t) if isinstance(out.get(k), (int, float)) else t
    return out


@contextlib.contextmanager
def _file_lock(path, timeout=5.0):
    """Exclusive lock on a small lock file (Windows: msvcrt, elsewhere: fcntl)."""
    f = open(path, "a+b")
    locked = False
    try:
        deadline = time.time() + timeout
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.time() > deadline:
                    raise TimeoutError(f"settings are locked: {path}")
                time.sleep(0.01)
        yield
    finally:
        if locked:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        f.close()


def autostart_command():
    return pet_command()


LAUNCH_AGENT = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", "io.github.cweeperde.smellyfish.plist")


def _launch_args():
    from smellyfish import paths

    bundle = paths.app_bundle()
    if bundle:
        return ["/usr/bin/open", "-a", bundle]
    return [sys.executable, "-m", "smellyfish"]


def autostart_enabled():
    if sys.platform == "darwin":
        return os.path.exists(LAUNCH_AGENT)
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on):
    if sys.platform == "darwin":
        import plistlib

        if not on:
            with contextlib.suppress(FileNotFoundError):
                os.remove(LAUNCH_AGENT)
            return
        from smellyfish import paths

        os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
        job = {
            "Label": "io.github.cweeperde.smellyfish",
            "ProgramArguments": _launch_args(),
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }
        if not paths.app_bundle():
            job["WorkingDirectory"] = os.path.dirname(paths.APP_DIR)
        with open(LAUNCH_AGENT, "wb") as f:
            plistlib.dump(job, f)
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass
