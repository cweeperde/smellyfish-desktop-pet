"""What is playing right now, through the Windows media controls (the same source as the volume flyout).

Works with Spotify, browsers, VLC and every other player that reports to Windows. Nothing leaves the PC.
The winrt calls are async, so they run in a worker thread with its own event loop; state goes back to the Qt
thread through on_state.
"""

import asyncio
import logging
import queue
import re
import threading
import time

log = logging.getLogger("smellyfish.media")

try:
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
    from winrt.windows.storage.streams import Buffer, InputStreamOptions

    AVAILABLE = True
except Exception:
    Manager = None
    AVAILABLE = False

PLAYING, PAUSED = 4, 5
POLL_S = 1.5
KNOWN = {
    "spotify": "Spotify",
    "chrome": "Chrome",
    "msedge": "Edge",
    "firefox": "Firefox",
    "opera": "Opera",
    "brave": "Brave",
    "vivaldi": "Vivaldi",
    "vlc": "VLC",
    "zunemusic": "Media Player",
    "foobar2000": "foobar2000",
    "musicbee": "MusicBee",
    "aimp": "AIMP",
    "tidal": "TIDAL",
    "deezer": "Deezer",
    "applemusic": "Apple Music",
    "itunes": "iTunes",
    "youtube": "YouTube Music",
    "winamp": "Winamp",
    "plexamp": "Plexamp",
}


def app_name(aumid):
    """A readable name for a Windows app id like 'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify'."""
    low = (aumid or "").lower()
    for key, name in KNOWN.items():
        if key in low:
            return name
    tail = re.split(r"[!\\\\/]", aumid or "")[-1]
    tail = re.sub(r"\.exe$", "", tail, flags=re.I)
    if not tail or re.fullmatch(r"[0-9A-Fa-f]{12,}", tail):
        return "Browser or app"
    return tail[:24]


class MediaWatch:
    def __init__(self, cfg, on_state):
        self.cfg = cfg
        self.on_state = on_state
        self.state = None
        self.commands = queue.Queue()
        self._thread = None
        self._stop = False

    def start(self):
        if not AVAILABLE or (self._thread is not None and self._thread.is_alive()):
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="media")
        self._thread.start()

    def stop(self):
        self._stop = True

    def send(self, cmd):
        """cmd: 'toggle', 'next', 'prev' or ('seek', seconds) for the session shown right now."""
        self.commands.put(cmd)

    @property
    def playing(self):
        return bool(self.state and self.state["status"] == PLAYING)

    def _run(self):
        try:
            asyncio.run(self._loop())
        except Exception:
            log.exception("media watcher stopped")

    async def _loop(self):
        manager = await Manager.request_async()
        last_key, cover = None, None
        while not self._stop:
            try:
                session = self._pick(manager)
                while not self.commands.empty():
                    cmd = self.commands.get_nowait()
                    if session is not None:
                        if cmd == "toggle":
                            await session.try_toggle_play_pause_async()
                        elif cmd == "next":
                            await session.try_skip_next_async()
                        elif cmd == "prev":
                            await session.try_skip_previous_async()
                        elif isinstance(cmd, tuple) and cmd[0] == "seek":
                            tl = session.get_timeline_properties()
                            start = tl.start_time.total_seconds() if tl is not None and tl.start_time else 0.0
                            await session.try_change_playback_position_async(int((start + cmd[1]) * 10_000_000))
                        await asyncio.sleep(0.25)
                        session = self._pick(manager)
                state = await self._read(session) if session is not None else None
                if state is not None:
                    key = (state["app_id"], state["title"], state["artist"])
                    if key != last_key:
                        cover = await self._cover(state.pop("_thumb", None))
                    state.pop("_thumb", None)
                    state["cover"] = cover
                    last_key = key
                else:
                    last_key, cover = None, None
                if self._changed(self.state, state):
                    self.on_state(dict(state) if state else None)
                self.state = state
            except Exception as e:
                log.info("media poll failed: %s", e.__class__.__name__)
            await asyncio.sleep(POLL_S)

    @staticmethod
    def _changed(old, new):
        """Anything but the position moving on by itself (a seek still counts)."""
        if (old is None) != (new is None):
            return True
        if old is None:
            return False
        moving = ("pos", "at")
        same = {k: v for k, v in old.items() if k not in moving} == {k: v for k, v in new.items() if k not in moving}
        expected = old["pos"] + (new["at"] - old["at"] if old["status"] == PLAYING else 0)
        return not same or abs(new["pos"] - expected) > 2

    def _pick(self, manager):
        """The session to show: a playing one first, then the one Windows calls current."""
        skip = {s.lower() for s in (self.cfg.get("media_exclude") or [])}
        sessions = [s for s in manager.get_sessions() if app_name(s.source_app_user_model_id).lower() not in skip]
        for s in sessions:
            info = s.get_playback_info()
            if info is not None and info.playback_status == PLAYING:
                return s
        cur = manager.get_current_session()
        if cur is not None and any(cur.source_app_user_model_id == s.source_app_user_model_id for s in sessions):
            return cur
        return None

    async def _read(self, session):
        props = await session.try_get_media_properties_async()
        info = session.get_playback_info()
        if props is None or info is None or not (props.title or props.artist):
            return None
        tl = session.get_timeline_properties()
        pos = dur = 0.0
        now = time.time()
        if tl is not None:
            start = tl.start_time.total_seconds() if tl.start_time else 0.0
            dur = (tl.end_time.total_seconds() if tl.end_time else 0.0) - start
            pos = (tl.position.total_seconds() if tl.position else 0.0) - start
            if info.playback_status == PLAYING and tl.last_updated_time is not None:
                pos += max(0.0, now - tl.last_updated_time.timestamp())
            pos = max(0.0, min(pos, dur) if dur > 0 else pos)
        controls = info.controls
        return {
            "app_id": session.source_app_user_model_id,
            "app": app_name(session.source_app_user_model_id),
            "title": props.title or "",
            "artist": props.artist or props.album_artist or "",
            "album": props.album_title or "",
            "status": int(info.playback_status),
            "pos": pos,
            "dur": max(0.0, dur),
            "at": now,
            "can_seek": bool(controls and controls.is_playback_position_enabled) and dur > 0,
            "can_next": bool(controls and controls.is_next_enabled),
            "can_prev": bool(controls and controls.is_previous_enabled),
            "_thumb": props.thumbnail,
        }

    @staticmethod
    async def _cover(ref):
        """Cover art as PNG/JPEG bytes (at most 2 MB), or None."""
        if ref is None:
            return None
        try:
            stream = await ref.open_read_async()
            size = min(int(stream.size), 2 * 1024 * 1024)
            buf = Buffer(size)
            await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            return bytes(memoryview(buf))[: buf.length]
        except Exception:
            return None
