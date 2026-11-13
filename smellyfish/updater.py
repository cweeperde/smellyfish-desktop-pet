"""Self-update for the packaged app from the project's GitHub releases.

The download is only used when its SHA-256 matches the digest GitHub publishes for the release asset (no digest,
no update). Windows: the new exe is swapped in next to the running one. macOS: the new Smellyfish.app is copied
out of the disk image and replaces the old bundle. Either way it runs on the next start.
"""

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QTimer, Signal

from smellyfish import REPO, __version__, paths

API = f"https://api.github.com/repos/{REPO}/releases/latest"
IS_MAC = sys.platform == "darwin"
ASSET = "Smellyfish.dmg" if IS_MAC else "Smellyfish.exe"
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


class Blocked(Exception):
    """The update cannot be installed where the app is (shown to the user as is)."""


def _target():
    if IS_MAC:
        return paths.app_bundle() or sys.executable
    return sys.executable


def cleanup():
    if paths.FROZEN:
        for suffix in (".old", ".new"):
            path = _target() + suffix
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except OSError:
                pass


def download_path():
    if IS_MAC:
        return os.path.join(paths.HOME_DIR, "update.dmg")
    return sys.executable + ".new"


def install(new):
    """Put the verified download in place of the running app."""
    if IS_MAC:
        return _install_mac(new)
    old = sys.executable + ".old"
    if os.path.exists(old):
        os.remove(old)
    os.replace(sys.executable, old)
    try:
        os.replace(new, sys.executable)
    except OSError:
        os.replace(old, sys.executable)
        raise


def _install_mac(dmg):
    bundle = paths.app_bundle()
    if not bundle or "/AppTranslocation/" in bundle or bundle.startswith("/Volumes/"):
        raise Blocked("Move Smellyfish to the Applications folder and start it from there to get updates.")
    if not os.access(os.path.dirname(bundle), os.W_OK):
        raise Blocked("I am not allowed to replace myself in this folder. Install the new version by hand.")
    mount = tempfile.mkdtemp(prefix="smellyfish-update-")
    new = bundle + ".new"
    try:
        subprocess.run(
            ["/usr/bin/hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", mount, dmg],
            check=True,
            capture_output=True,
            timeout=180,
        )
        try:
            shutil.rmtree(new, ignore_errors=True)
            subprocess.run(
                ["/usr/bin/ditto", os.path.join(mount, "Smellyfish.app"), new],
                check=True,
                capture_output=True,
                timeout=300,
            )
        finally:
            subprocess.run(["/usr/bin/hdiutil", "detach", mount, "-force"], capture_output=True, timeout=60)
        old = bundle + ".old"
        shutil.rmtree(old, ignore_errors=True)
        os.rename(bundle, old)
        try:
            os.rename(new, bundle)
        except OSError:
            os.rename(old, bundle)
            raise
    finally:
        shutil.rmtree(new, ignore_errors=True)
        try:
            os.rmdir(mount)
        except OSError:
            pass
        try:
            os.remove(dmg)
        except OSError:
            pass


class Updater(QObject):
    ready = Signal(str)  # version installed, takes effect on restart
    status = Signal(str)
    busy = Signal(bool)  # a manual check or download is running

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
            if manual:
                if self._busy:
                    self.status.emit("Already checking for updates...")
                elif self.installed:
                    self.status.emit(f"Version {self.installed} is installed. Restart to use it.")
                else:
                    self.status.emit("Updates only work in the packaged app.")
            return
        if not manual and not self.cfg.get("auto_update"):
            return
        self._busy = True
        if manual:
            self.busy.emit(True)
            self.status.emit("Checking for updates...")
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
            digest = ((asset or {}).get("digest") or "").lower()
            if asset is None or not digest.startswith("sha256:") or len(digest) != 71:
                if manual:
                    self.status.emit("The new version has no verifiable download yet, I'll try again later.")
                return
            new = download_path()
            sha = hashlib.sha256()
            size = int(asset.get("size") or 0)
            got = shown = 0
            if manual:
                self.status.emit(f"Found version {tag.lstrip('vV')}. Downloading...")
            with _get(asset["url"], "application/octet-stream") as r, open(new, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    sha.update(chunk)
                    f.write(chunk)
                    got += len(chunk)
                    if manual and size and got * 100 // size >= shown + 10:
                        shown = got * 100 // size
                        self.status.emit(f"Downloading version {tag.lstrip('vV')}... {shown}%")
            if not hmac.compare_digest(digest[7:], sha.hexdigest()):
                os.remove(new)
                self.status.emit("The update download was damaged, I'll try again later.")
                return
            install(new)
            self.installed = tag.lstrip("vV")
            self.ready.emit(self.installed)
        except Blocked as e:
            self.status.emit(str(e))
        except urllib.error.HTTPError as e:
            if manual:
                self.status.emit(
                    "No published release found yet."
                    if e.code == 404
                    else f"Could not check for updates (HTTP {e.code})."
                )
        except Exception as e:
            if manual:
                self.status.emit(f"Could not check for updates ({e.__class__.__name__}).")
        finally:
            self._busy = False
            if manual:
                self.busy.emit(False)


def restart():
    import subprocess

    # The new exe must start as a fresh app, not as a child of the old one (the bootloader refuses that)
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "_MEIPASS2"}
    env.update(SMELLYFISH_RESTART="1", PYINSTALLER_RESET_ENVIRONMENT="1")
    if IS_MAC:
        subprocess.Popen([sys.executable], env=env, close_fds=True, start_new_session=True)
        return
    subprocess.Popen(
        [sys.executable], env=env, close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
    )
