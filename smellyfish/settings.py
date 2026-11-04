"""Persistent user settings and Windows autostart."""
import json
import os
import sys

from smellyfish.paths import HOME_DIR as DIR, pet_command

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
    "sound_done": True,
    "sfx": True,
    "volume": 60,
    "notify_volume": 70,
    "auto_update": True,
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
    "mood": None,
    "mood_at": None,
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
        if os.path.exists(PATH):
            try:
                with open(PATH, encoding="utf-8") as f:
                    data = json.load(f)
                dict.update(self, {k: v for k, v in data.items() if k in DEFAULTS})
                self._backup()
            except (OSError, ValueError):
                self._recover()

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
        for i in (1, 2, 3):
            try:
                with open(f"{PATH}.bak{i}", encoding="utf-8") as f:
                    data = json.load(f)
                dict.update(self, {k: v for k, v in data.items() if k in DEFAULTS})
                self._dirty = set(data) & set(DEFAULTS)
                return
            except (OSError, ValueError):
                continue

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._dirty.add(key)

    def save(self):
        if self.readonly:
            return
        os.makedirs(DIR, exist_ok=True)
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
        os.replace(tmp, PATH)

    def set(self, key, value):
        self[key] = value
        self.save()


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
