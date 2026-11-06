"""Discord Rich Presence ("Playing Smellyfish").

Talks only to the local Discord client through its IPC pipe. Nothing is sent from
this program to the network, and only short generic status lines are shared.
"""
import os
import threading
import time

from smellyfish.integrations.discord_watch import Pipe

# Application id of the "Smellyfish" application in the Discord Developer Portal (public by design).
APP_ID = "1568222328326987776"
ASSET = "jelly"
SITE = "https://cweeperde.github.io/smellyfish-desktop-pet/"
TIP = "Smellyfish - a tiny jellyfish for your desktop"
MIN_GAP = 15.0
RETRY = 30.0

IDLE_LINES = ["Floating around", "Blowing little bubbles", "Being a tiny jellyfish", "Soaking up the sunshine"]
IDLE_STATE = "Blub blub"

WORK = {"thinking", "search", "terminal", "browse", "todo", "working", "cooking"}
WORK_LINE = ("Watching {who} work", "Bubbling along quietly")


def lines(base, who="Claude", dnd=False, walking=False, now=None):
    """(details, state) for the current mood. Only generic, non-personal lines."""
    if dnd:
        return "Taking a nap", "Zzz..."
    if base == "sleeping":
        return "Taking a nap", "Zzz..."
    if base in WORK:
        return WORK_LINE[0].format(who=who), WORK_LINE[1]
    if walking:
        return "Going for a little walk", IDLE_STATE
    slot = int((time.time() if now is None else now) // 300) % len(IDLE_LINES)
    return IDLE_LINES[slot], IDLE_STATE


def activity(details, state, started):
    return {
        "type": 0,
        "status_display_type": 0,
        "details": details,
        "state": state,
        "timestamps": {"start": int(started)},
        "assets": {"large_image": ASSET, "large_text": TIP},
        "buttons": [{"label": "Adopt your own Smellyfish", "url": SITE}],
    }


class DiscordPresence:
    def __init__(self):
        self._want = None
        self._sent = None
        self._last = 0.0
        self._next_try = 0.0
        self._stop = False
        self._thread = None
        self._lock = threading.Lock()

    def update(self, act):
        """Set the wanted activity, or None to clear it. Safe to call from any thread."""
        if not APP_ID:
            return
        with self._lock:
            self._want = act
        if act is not None and not (self._thread and self._thread.is_alive()):
            self._stop = False
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop = True
        with self._lock:
            self._want = None
        t = self._thread
        if t and t.is_alive():
            t.join(1.5)

    def _set(self, pipe, act):
        pipe.cmd("SET_ACTIVITY", {"pid": os.getpid(), "activity": act})
        pipe.recv()

    def _run(self):
        pipe = None
        try:
            while not self._stop:
                with self._lock:
                    want = self._want
                if pipe is None:
                    if want is None:
                        return
                    if time.time() < self._next_try:
                        time.sleep(1)
                        continue
                    try:
                        pipe = Pipe()
                        pipe.send(0, {"v": 1, "client_id": APP_ID})
                        op, msg = pipe.recv()
                        if msg.get("evt") != "READY":
                            raise OSError("handshake failed")
                        self._sent, self._last = None, 0.0
                    except Exception:
                        if pipe:
                            pipe.close()
                        pipe = None
                        self._next_try = time.time() + RETRY
                        continue
                if want != self._sent and time.time() - self._last >= MIN_GAP:
                    try:
                        self._set(pipe, want)
                        self._sent, self._last = want, time.time()
                    except Exception:
                        pipe.close()
                        pipe = None
                        self._next_try = time.time() + RETRY
                        continue
                    if want is None:
                        return
                time.sleep(1)
        finally:
            if pipe is not None:
                try:
                    if self._sent is not None:
                        self._set(pipe, None)
                except Exception:
                    pass
                pipe.close()
