"""Persistent user settings and Windows autostart."""
import contextlib
import json
import logging
import os
import sys
import time

from smellyfish.paths import HOME_DIR as DIR, pet_command

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
    "trips_home": True,
    "show_house": True,
    "plant_watered_at": 0,
    "codex_hooks": False,
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
    "auto_water": True,
    "focus_min": 25,
    "break_min": 5,
    "hotkeys": {"toggle": "Ctrl+Alt+F9", "home": "Ctrl+Alt+F10", "dnd": "Ctrl+Alt+F11", "history": "Ctrl+Alt+F12",
                "focus": "Ctrl+Alt+F8", "chase": "Ctrl+Alt+F7", "mini": "Ctrl+Alt+F6"},
    "skin": "lavender",
    "skin_color": "#c492ec",
    "weather": False,
    "weather_place": "",
    "weather_loc": None,
    "react_clipboard": True,
    "mini": False,
    "mini_side": "right",
    "monitor": "primary",
    "task_timer": True,
    "talk_blips": True,
    "reminders": [],
    "stats": {},
    "achievements": {},
}


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
                dict.update(self, {k: v for k, v in data.items() if k in DEFAULTS})
                self._backup()
                log.info("loaded settings (house %s, %d achievements)", self.get("show_house"),
                         len(self.get("achievements") or {}))
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
                dict.update(self, {k: v for k, v in data.items() if k in DEFAULTS})
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
            merged = dict(DEFAULTS, **{k: v for k, v in disk.items() if k in DEFAULTS})
            merged.update({k: self[k] for k in self._dirty})
            tmp = PATH + f".{os.getpid()}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2)
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


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
        return True
    except OSError:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass
