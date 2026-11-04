"""Self-update for the packaged exe from the project's GitHub releases.

The new exe is downloaded next to the running one, checked against the SHA-256 digest
GitHub publishes for release assets, and swapped in place. It runs on the next start.
"""
import hashlib
import json
import os
import sys
import threading
import urllib.request

from PySide6.QtCore import QObject, QTimer, Signal

from smellyfish import REPO, __version__, paths

API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "Smellyfish.exe"
CHECK_EVERY_MS = 6 * 3600 * 1000


def parse(v):
    out = []
    for part in str(v).lstrip("vV").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out + [0] * (3 - len(out)))


def _get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "Smellyfish-updater"})
    return urllib.request.urlopen(req, timeout=30)


def cleanup():
    if paths.FROZEN:
        for suffix in (".old", ".new"):
            try:
                os.remove(sys.executable + suffix)
            except OSError:
                pass


class Updater(QObject):
    ready = Signal(str)          # version installed, takes effect on restart
    status = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.installed = None
        self._busy = False
        cleanup()
        self.timer = QTimer(self, timeout=self.check)
        self.timer.start(CHECK_EVERY_MS)
        QTimer.singleShot(30000, self.check)

    def check(self, manual=False):
        if self._busy or self.installed or not paths.FROZEN or os.environ.get("SMELLYFISH_HOME"):
            if manual and not paths.FROZEN:
                self.status.emit("Updates only work in the packaged Smellyfish.exe.")
            return
        if not manual and not self.cfg.get("auto_update"):
            return
        self._busy = True
        threading.Thread(target=self._run, args=(manual,), daemon=True).start()

    def _run(self, manual):
        try:
            with _get(API) as r:
                rel = json.loads(r.read())
            tag = rel.get("tag_name") or ""
            if rel.get("draft") or rel.get("prerelease") or parse(tag) <= parse(__version__):
                if manual:
                    self.status.emit(f"You have the newest version ({__version__}).")
                return
            asset = next((a for a in rel.get("assets") or [] if a.get("name") == ASSET), None)
            if asset is None:
                return
            new = sys.executable + ".new"
            sha = hashlib.sha256()
            with _get(asset["url"], "application/octet-stream") as r, open(new, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    sha.update(chunk)
                    f.write(chunk)
            digest = (asset.get("digest") or "").lower()
            if (digest.startswith("sha256:") and digest[7:] != sha.hexdigest()) or os.path.getsize(new) != asset.get(
                    "size", os.path.getsize(new)):
                os.remove(new)
                self.status.emit("The update download was damaged, I'll try again later.")
                return
            old = sys.executable + ".old"
            if os.path.exists(old):
                os.remove(old)
            os.replace(sys.executable, old)
            try:
                os.replace(new, sys.executable)
            except OSError:
                os.replace(old, sys.executable)
                raise
            self.installed = tag.lstrip("vV")
            self.ready.emit(self.installed)
        except Exception as e:
            if manual:
                self.status.emit(f"Could not check for updates ({e.__class__.__name__}).")
        finally:
            self._busy = False


def restart():
    import subprocess
    env = dict(os.environ, SMELLYFISH_RESTART="1")
    subprocess.Popen([sys.executable], env=env, close_fds=True,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
