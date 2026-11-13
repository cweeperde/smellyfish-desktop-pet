"""What is playing on macOS: Spotify and Music announce every change as a system-wide notification, which needs no
permission to listen to. The buttons (play, next, seek) go through AppleScript, so macOS asks once for Automation
access to that player the first time one is pressed. Nothing leaves the Mac."""

import logging
import threading
import time

from smellyfish.integrations.media import PAUSED, PLAYING

log = logging.getLogger("smellyfish.media")

PLAYERS = {
    "com.spotify.client.PlaybackStateChanged": ("com.spotify.client", "Spotify", "Spotify"),
    "com.apple.Music.playerInfo": ("com.apple.Music", "Music", "Music"),
}
STATE_SCRIPT = """
tell application "{app}"
    if player state is stopped then return ""
    set t to current track
    set out to (player state as text) & tab & (name of t) & tab & (artist of t) & tab & (album of t)
    return out & tab & ((duration of t) as text) & tab & ((player position) as text)
end tell
"""
_OBSERVER = []


def _observer_class():
    if _OBSERVER:
        return _OBSERVER[0]
    from Foundation import NSObject

    class SmellyfishMediaObserver(NSObject):
        def onNote_(self, note):
            watch = _WATCH[0]
            if watch is not None:
                try:
                    watch._note(str(note.name()), dict(note.userInfo() or {}))
                except Exception:
                    log.exception("media note failed")

    _OBSERVER.append(SmellyfishMediaObserver)
    return SmellyfishMediaObserver


_WATCH = [None]


def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return default


class MacMediaWatch:
    def __init__(self, cfg, on_state):
        self.cfg = cfg
        self.on_state = on_state
        self.state = None
        self.players = {}
        self.observer = None

    def start(self):
        if self.observer is not None:
            return
        try:
            from Foundation import NSDistributedNotificationCenter

            _WATCH[0] = self
            self.observer = _observer_class().alloc().init()
            center = NSDistributedNotificationCenter.defaultCenter()
            for name in PLAYERS:
                # 4 = deliver immediately, also while Smellyfish is not the active app
                center.addObserver_selector_name_object_suspensionBehavior_(self.observer, "onNote:", name, None, 4)
        except Exception as e:
            log.info("media notifications unavailable: %s", e)
            self.observer = None
            return
        if self.cfg.get("mac_media_ok"):
            threading.Thread(target=self._read_running, daemon=True).start()

    def stop(self):
        if self.observer is not None:
            try:
                from Foundation import NSDistributedNotificationCenter

                NSDistributedNotificationCenter.defaultCenter().removeObserver_(self.observer)
            except Exception:
                pass
        self.observer = None
        _WATCH[0] = None
        self.players = {}

    @property
    def playing(self):
        return bool(self.state and self.state["status"] == PLAYING)

    def _note(self, name, info):
        bundle, label, app = PLAYERS[name]
        status = str(info.get("Player State") or "")
        if status not in ("Playing", "Paused") or not (info.get("Name") or info.get("Artist")):
            self.players.pop(bundle, None)
            return self._publish()
        dur = _num(info.get("Duration") or info.get("Total Time")) / 1000.0
        old = self.players.get(bundle)
        pos = info.get("Playback Position")
        same = old and old["title"] == str(info.get("Name") or "")
        if pos is not None:
            pos = _num(pos)
        elif same:
            pos = self._position(old)
        else:
            pos = 0.0
        self._set(
            bundle,
            label,
            app,
            status == "Playing",
            str(info.get("Name") or ""),
            str(info.get("Artist") or ""),
            str(info.get("Album") or ""),
            dur,
            pos,
        )

    def _set(self, bundle, label, app, playing, title, artist, album, dur, pos):
        self.players[bundle] = {
            "app_id": bundle,
            "app": label,
            "_script": app,
            "title": title,
            "artist": artist,
            "album": album,
            "status": PLAYING if playing else PAUSED,
            "pos": max(0.0, min(pos, dur) if dur > 0 else pos),
            "dur": max(0.0, dur),
            "at": time.time(),
            "can_seek": dur > 0,
            "can_next": True,
            "can_prev": True,
            "cover": None,
        }
        self._publish()

    @staticmethod
    def _position(s):
        return s["pos"] + (time.time() - s["at"] if s["status"] == PLAYING else 0.0)

    def _publish(self):
        skip = {s.lower() for s in (self.cfg.get("media_exclude") or [])}
        cands = [s for s in self.players.values() if s["app"].lower() not in skip]
        pick = next((s for s in cands if s["status"] == PLAYING), None)
        if pick is None and cands:
            pick = max(cands, key=lambda s: s["at"])
        state = {k: v for k, v in pick.items() if k != "_script"} if pick else None
        if state != self.state:
            self.state = state
            self.on_state(dict(state) if state else None)

    def _read_running(self):
        """The current track of players that are already running (only once Automation was allowed before)."""
        from smellyfish.system import mac

        for _name, (bundle, label, app) in PLAYERS.items():
            if mac.running_app({bundle}) is None:
                continue
            ok, out = mac.osascript(STATE_SCRIPT.format(app=app), timeout=5)
            parts = out.split("\t") if ok else []
            if len(parts) < 6:
                continue
            dur = _num(parts[4])
            if dur > 10000:
                dur /= 1000.0
            self._set(bundle, label, app, parts[0] == "playing", parts[1], parts[2], parts[3], dur, _num(parts[5]))

    def send(self, cmd):
        """cmd: 'toggle', 'next', 'prev' or ('seek', seconds) for the player shown right now."""
        if not self.state:
            return
        app = self.players.get(self.state["app_id"], {}).get("_script")
        if not app:
            return
        if cmd == "toggle":
            line = "playpause"
        elif cmd == "next":
            line = "next track"
        elif cmd == "prev":
            line = "previous track"
        elif isinstance(cmd, tuple) and cmd[0] == "seek":
            line = f"set player position to {float(cmd[1]):.1f}"
        else:
            return

        def run():
            from smellyfish.system import mac

            ok, _ = mac.osascript(f'tell application "{app}" to {line}', timeout=10)
            if ok and not self.cfg.get("mac_media_ok"):
                self.cfg.set("mac_media_ok", True)
            if ok and isinstance(cmd, tuple):
                s = self.players.get(self.state["app_id"]) if self.state else None
                if s:
                    s["pos"], s["at"] = float(cmd[1]), time.time()

        threading.Thread(target=run, daemon=True).start()
