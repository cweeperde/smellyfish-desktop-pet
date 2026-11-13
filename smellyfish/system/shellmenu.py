"""Explorer right-click entry for files and folders (per-user registry keys, no admin rights).

The entry only starts Smellyfish.exe with --shell <action> <path>; that call hands the request to the running
pet over 127.0.0.1 and exits. On Windows 11 the entry shows under "Show more options".
On macOS the same entries are Finder Quick Actions (see finder_actions.py).
"""

import json
import os
import shutil
import sys
import urllib.request

from smellyfish import __version__, paths

try:
    import winreg
except ImportError:
    winreg = None

NAME = "Smellyfish"
BASE = os.environ.get("SMELLYFISH_SHELL_BASE") or "Software\\Classes"
AGENTS = [
    ("claude", "Claude Code"),
    ("codex", "Codex"),
    ("gemini", "Gemini CLI"),
    ("agy", "Antigravity"),
    ("copilot", "GitHub Copilot"),
    ("cursor-agent", "Cursor"),
]
ROOTS = [("*", "%1", True), ("Directory", "%1", True), ("Directory\\Background", "%V", False)]


def _fresh_path():
    """PATH as Windows has it now, so a CLI installed after Smellyfish started is still found."""
    if sys.platform == "darwin":
        from smellyfish.system import mac

        return mac.login_path()
    parts = [os.environ.get("PATH", "")]
    if winreg is not None:
        for root, sub in (
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, "Environment"),
        ):
            try:
                with winreg.OpenKey(root, sub) as k:
                    parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
            except OSError:
                pass
    return os.pathsep.join(parts)


def installed_agents():
    path = _fresh_path()
    return [(cmd, label) for cmd, label in AGENTS if shutil.which(cmd, path=path)]


def signature():
    """Changes whenever the entries would look different (exe moved or updated, CLI added or removed)."""
    return "|".join([paths.pet_command(), __version__] + [cmd for cmd, _ in installed_agents()])


def refresh():
    """Rewrites the entries when they are out of date; does nothing when they are off or current."""
    if sys.platform == "darwin":
        from smellyfish.system import finder_actions

        return finder_actions.refresh()
    if winreg is None or not is_installed():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{BASE}\\*\\shell\\{NAME}") as k:
            if winreg.QueryValueEx(k, "Signature")[0] == signature():
                return False
    except OSError:
        pass
    return apply(True)


def command(action, arg):
    return f'{paths.pet_command()} --shell {action} "{arg}"'


def _delete_tree(root, sub):
    try:
        key = winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_WRITE)
    except OSError:
        return
    with key:
        while True:
            try:
                child = winreg.EnumKey(key, 0)
            except OSError:
                break
            _delete_tree(root, sub + "\\" + child)
    try:
        winreg.DeleteKey(root, sub)
    except OSError:
        pass


def _set(path, verb=None, command_line=None, icon=None, subcommands=False):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as k:
        if verb:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, verb)
        if icon:
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
        if subcommands:
            winreg.SetValueEx(k, "SubCommands", 0, winreg.REG_SZ, "")
        if command_line:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command_line)


def is_installed():
    if sys.platform == "darwin":
        from smellyfish.system import finder_actions

        return finder_actions.is_installed()
    if winreg is None:
        return False
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{BASE}\\*\\shell\\{NAME}"))
        return True
    except OSError:
        return False


def apply(install=True):
    if sys.platform == "darwin":
        from smellyfish.system import finder_actions

        return finder_actions.apply(install)
    if winreg is None:
        return False
    for root, arg, details in ROOTS:
        top = f"{BASE}\\{root}\\shell\\{NAME}"
        _delete_tree(winreg.HKEY_CURRENT_USER, top)
        if not install:
            continue
        _set(top, verb="Smellyfish", icon=f'"{sys.executable}",0' if paths.FROZEN else None, subcommands=True)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, top) as k:
            winreg.SetValueEx(k, "Signature", 0, winreg.REG_SZ, signature())
        n = 0
        if details:
            n += 1
            sub = f"{top}\\shell\\{n:02d}details"
            _set(sub, verb="Details")
            _set(sub + "\\command", command_line=command("details", arg))
        for cmd, label in installed_agents():
            n += 1
            sub = f"{top}\\shell\\{n:02d}{cmd}"
            _set(sub, verb=f"Start {label} CLI here")
            _set(sub + "\\command", command_line=command("agent:" + cmd, arg))
    return True


def forward(action, path):
    """Called by the short-lived --shell process: hand the request to the running pet."""
    from smellyfish.integrations.server import PORT

    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/shell",
        method="POST",
        data=json.dumps({"action": action, "path": path}).encode(),
        headers={"Content-Type": "application/json", "X-Smellyfish": "1"},
    )
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=2).read()
    except Exception:
        pass
