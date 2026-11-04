"""Where things live, both when run from source and as the packaged Smellyfish.exe."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
HOME_DIR = os.environ.get("SMELLYFISH_HOME") or os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                                                            "Smellyfish")
RELAY_DIR = os.path.join(HOME_DIR, "relay")
RELAY_EXE = os.path.join(RELAY_DIR, "smellyfish-relay.exe")
RELAY_PY = os.path.join(APP_DIR, "integrations", "hook_relay.py")


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
    with open(stamp, "w") as f:
        f.write(size)
