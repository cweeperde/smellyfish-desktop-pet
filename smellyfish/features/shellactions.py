"""What the Explorer / Finder right-click entries do: file details in a bubble, or a CLI agent in that folder."""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading

from smellyfish.features import fileinfo
from smellyfish.system import shellmenu


def on_shell(app, req):
    action, path = req["action"], req["path"]
    if action.startswith("agent:"):
        return app.shell_agent(action[6:], path)
    name = os.path.basename(path.rstrip("\\/")) or path
    app.notice({"kind": "wait", "chip": "Details", "right": "Sniffing...", "text": name}, seconds=0)

    def work():
        try:
            info = fileinfo.describe(path)
        except OSError as e:
            info = {"title": name, "kind": "", "text": f"I could not read this ({e.__class__.__name__}).", "hash": ""}
        info["path"] = path
        app.bridge.fileinfo.emit(info)

    threading.Thread(target=work, daemon=True).start()


def on_fileinfo(app, info):
    buttons = []
    if info.get("hash"):
        buttons.append(("Copy hash", ("shell_copy", info["hash"]), True))
    buttons += [
        ("Copy path", ("shell_copy", info["path"]), not buttons),
        ("Show in folder", ("shell_show", info["path"]), False),
        ("OK", "ok", False),
    ]
    app.notice(
        {
            "kind": "wait",
            "chip": "Details",
            "right": info["kind"],
            "text": info["title"] + "\n" + info["text"],
            "buttons": buttons,
        },
        seconds=0,
    )


def shell_agent(app, cmd, path):
    label = dict(shellmenu.AGENTS).get(cmd)
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    found = shutil.which(cmd, path=shellmenu._fresh_path()) if sys.platform == "darwin" else shutil.which(cmd)
    if not label or not found:
        return app.notice({"kind": "wait", "chip": "Agent", "text": f"{label or cmd} is not installed."}, seconds=6)
    wt = shutil.which("wt")
    try:
        if sys.platform == "darwin":
            _mac_terminal(folder, found)
        elif wt:
            subprocess.Popen([wt, "-d", folder.replace(";", "\\;"), "cmd", "/k", cmd])
        else:
            subprocess.Popen(["cmd", "/k", cmd], cwd=folder, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except OSError:
        return app.notice(
            {"kind": "wait", "chip": "Agent", "text": f"I could not open a terminal for {label}."}, seconds=6
        )
    app.notice({"kind": "wait", "chip": "Agent", "right": label, "text": f"Starting {label} in {folder}"}, seconds=5)
    if not app.player.busy:
        app.player.once("happy")


def _mac_terminal(folder, cmd):
    """A .command file opens in the default terminal app without asking for Automation access."""
    fd, script = tempfile.mkstemp(prefix="smellyfish-", suffix=".command")
    with os.fdopen(fd, "w") as f:
        f.write(
            f"#!/bin/zsh -l\nrm -f {shlex.quote(script)}\ncd {shlex.quote(folder)} || exit 1\nexec {shlex.quote(cmd)}\n"
        )
    os.chmod(script, 0o700)
    subprocess.Popen(["/usr/bin/open", script])
