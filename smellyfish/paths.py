"""Where things live, both when run from source and as the packaged app (Smellyfish.exe / Smellyfish.app)."""

import os
import sys

FROZEN = getattr(sys, "frozen", False)
IS_MAC = sys.platform == "darwin"
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
if IS_MAC:
    _DATA = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
else:
    _DATA = os.environ.get("APPDATA") or os.path.expanduser("~")
HOME_DIR = os.environ.get("SMELLYFISH_HOME") or os.path.join(_DATA, "Smellyfish")
RELAY_DIR = os.path.join(HOME_DIR, "relay")
RELAY_EXE = os.path.join(RELAY_DIR, "smellyfish-relay" if IS_MAC else "smellyfish-relay.exe")
RELAY_PY = os.path.join(APP_DIR, "integrations", "hook_relay.py")


def app_bundle():
    """/Applications/Smellyfish.app when running as the packaged macOS app, else None."""
    if not (FROZEN and IS_MAC):
        return None
    path = os.path.abspath(sys.executable)
    while path and path != os.path.dirname(path):
        if path.endswith(".app"):
            return path
        path = os.path.dirname(path)
    return None


def relay_command():
    """(executable, args) for the hook relay."""
    if FROZEN:
        return RELAY_EXE, []
    return sys.executable, [RELAY_PY]


def pet_command():
    """Command line that starts the pet (for autostart)."""
    if FROZEN:
        return f'"{sys.executable}"'
    exe = sys.executable
    alt = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return f'"{alt if os.path.exists(alt) else exe}" "{os.path.join(APP_DIR, "__main__.py")}"'


def ensure_relay():
    """In the packaged app, unpack the small relay next to the settings (once per version).

    A relay that is still running (a hook waiting for an answer, the statusline) keeps its files locked on
    Windows, so a failure here is logged and retried on the next start instead of stopping the app."""
    if not FROZEN:
        return
    try:
        _unpack_relay()
    except Exception:
        import logging

        logging.getLogger("smellyfish").exception("could not unpack the hook relay")


def _unpack_relay():
    import shutil
    import zipfile

    src = os.path.join(BUNDLE_DIR, "relay.zip")
    stamp = os.path.join(RELAY_DIR, "version")
    size = str(os.path.getsize(src)) if os.path.exists(src) else ""
    _remove_stale(RELAY_DIR)
    if os.path.exists(RELAY_EXE) and os.path.exists(stamp):
        with open(stamp) as f:
            if f.read() == size:
                return
    new = RELAY_DIR + ".new"
    shutil.rmtree(new, ignore_errors=True)
    os.makedirs(new)
    try:
        with zipfile.ZipFile(src) as z:
            z.extractall(new)
            if not sys.platform.startswith("win"):
                for info in z.infolist():
                    mode = (info.external_attr >> 16) & 0o777
                    if mode:
                        os.chmod(os.path.join(new, info.filename), mode)
        if os.path.exists(stamp):
            os.remove(stamp)
        for root, _dirs, files in os.walk(new):
            dest_dir = os.path.join(RELAY_DIR, os.path.relpath(root, new))
            os.makedirs(dest_dir, exist_ok=True)
            for name in files:
                _replace(os.path.join(root, name), os.path.join(dest_dir, name))
    finally:
        shutil.rmtree(new, ignore_errors=True)
    with open(stamp, "w") as f:
        f.write(size)


def _replace(src, dest):
    """Move src over dest. A running exe or DLL cannot be overwritten on Windows, but it can be renamed."""
    try:
        os.replace(src, dest)
        return
    except PermissionError:
        if not os.path.exists(dest):
            raise
    os.replace(dest, f"{dest}.{os.getpid()}.stale")
    os.replace(src, dest)


def _remove_stale(folder):
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name.endswith(".stale"):
                try:
                    os.remove(os.path.join(root, name))
                except OSError:
                    pass
