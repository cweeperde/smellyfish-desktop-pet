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
    """In the packaged app, unpack the small relay next to the settings (once per version)."""
    if not FROZEN:
        return
    import shutil
    import zipfile

    src = os.path.join(BUNDLE_DIR, "relay.zip")
    stamp = os.path.join(RELAY_DIR, "version")
    size = str(os.path.getsize(src)) if os.path.exists(src) else ""
    if os.path.exists(RELAY_EXE) and os.path.exists(stamp) and open(stamp).read() == size:
        return
    shutil.rmtree(RELAY_DIR, ignore_errors=True)
    os.makedirs(RELAY_DIR, exist_ok=True)
    with zipfile.ZipFile(src) as z:
        z.extractall(RELAY_DIR)
        if not sys.platform.startswith("win"):
            for info in z.infolist():
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    os.chmod(os.path.join(RELAY_DIR, info.filename), mode)
    with open(stamp, "w") as f:
        f.write(size)
