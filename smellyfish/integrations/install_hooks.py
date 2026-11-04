"""Adds (or removes) the Smellyfish hooks for Claude Code and Codex.

  python -m smellyfish.integrations.install_hooks                      print the Claude Code hooks JSON only
  python -m smellyfish.integrations.install_hooks --install user       ~/.claude/settings.json
  python -m smellyfish.integrations.install_hooks --install project    ./.claude/settings.json
  python -m smellyfish.integrations.install_hooks --install local      ./.claude/settings.local.json
  python -m smellyfish.integrations.install_hooks --install codex      ~/.codex/hooks.json
  python -m smellyfish.integrations.install_hooks --remove user|codex  remove them again

A backup (*.bak) is written before every change. Codex asks you to trust new hooks once (/hooks).
"""
import argparse
import json
import os
import shutil

from smellyfish.paths import relay_command

CLAUDE_EVENTS = {
    "UserPromptSubmit": (None, 10),
    "PreToolUse": ("*", 600),
    "PostToolUse": ("*", 10),
    "PostToolUseFailure": ("*", 10),
    "PermissionRequest": ("*", 600),
    "Notification": (None, 10),
    "Stop": (None, 10),
    "StopFailure": (None, 10),
    "SessionEnd": (None, 5),
}
CODEX_EVENTS = {
    "UserPromptSubmit": 10,
    "PreToolUse": 10,
    "PostToolUse": 10,
    "PermissionRequest": 600,
    "Stop": 10,
    "Interrupt": 2,
    "SessionEnd": 2,
}
MARKERS = ("hook_relay.py", "smellyfish-relay")


def claude_entry(matcher, timeout):
    exe, args = relay_command()
    e = {"hooks": [{"type": "command", "command": exe, "args": args, "timeout": timeout}]}
    if matcher:
        e["matcher"] = matcher
    return e


def _bare(path):
    """A path that needs no quotes, so the same command works in PowerShell and cmd."""
    if " " not in path or os.name != "nt":
        return path
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(path, buf, 1024):
        return buf.value
    return path


def codex_entry(timeout):
    exe, args = relay_command()
    cmd = " ".join(f'"{p}"' for p in [exe] + args + ["codex"])
    win = " ".join([_bare(exe)] + [_bare(a) for a in args] + ["codex"])
    return {"hooks": [{"type": "command", "command": cmd, "commandWindows": win, "timeout": min(timeout, 600)}]}


def ours(e):
    text = json.dumps(e).replace("\\\\", "/").lower()
    return any(m in text for m in MARKERS)


def target(scope):
    if scope == "codex":
        return os.path.join(os.path.expanduser("~"), ".codex", "hooks.json")
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    name = "settings.json" if scope == "project" else "settings.local.json"
    return os.path.join(os.getcwd(), ".claude", name)


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def is_installed(scope="user"):
    data = load(target(scope))
    return any(ours(e) for entries in data.get("hooks", {}).values() for e in entries)


def needs_update(scope):
    data = load(target(scope)).get("hooks", {})
    if scope == "codex":
        wanted = {ev: codex_entry(t) for ev, t in CODEX_EVENTS.items()}
    else:
        wanted = {ev: claude_entry(m, t) for ev, (m, t) in CLAUDE_EVENTS.items()}
    for ev, entry in wanted.items():
        mine = [e for e in data.get(ev, []) if ours(e)]
        if mine and mine != [entry]:
            return True
    return False


def apply(scope, install=True):
    path = target(scope)
    data = load(path)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    current = data.setdefault("hooks", {})
    if scope == "codex":
        wanted = {ev: codex_entry(t) for ev, t in CODEX_EVENTS.items()}
    else:
        wanted = {ev: claude_entry(m, t) for ev, (m, t) in CLAUDE_EVENTS.items()}
    for ev in set(current) | set(wanted):
        current[ev] = [e for e in current.get(ev, []) if not ours(e)]
        if install and ev in wanted:
            current[ev].append(wanted[ev])
        if not current[ev]:
            del current[ev]
    if not current:
        del data["hooks"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def statusline_command():
    exe, args = relay_command()
    return " ".join(f'"{p}"' for p in [exe] + args + ["statusline"])


def statusline_state():
    """None, "ours" or "other" (someone else's status line, which we never replace)."""
    sl = load(target("user")).get("statusLine")
    return ("ours" if ours(sl) else "other") if sl else None


def statusline_stale():
    sl = load(target("user")).get("statusLine")
    return bool(sl) and ours(sl) and sl.get("command") != statusline_command()


def apply_statusline(install=True):
    path = target("user")
    data = load(path)
    current = data.get("statusLine")
    if current and not ours(current):
        return False
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    if install:
        data["statusLine"] = {"type": "command", "command": statusline_command(), "padding": 0}
    else:
        data.pop("statusLine", None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    scopes = ["user", "project", "local", "codex"]
    g.add_argument("--install", choices=scopes)
    g.add_argument("--remove", choices=scopes)
    a = ap.parse_args()
    if not (a.install or a.remove):
        print(json.dumps({"hooks": {ev: [claude_entry(m, t)] for ev, (m, t) in CLAUDE_EVENTS.items()}}, indent=2))
        return
    path = apply(a.install or a.remove, install=bool(a.install))
    print(("Installed into " if a.install else "Removed from ") + path)


if __name__ == "__main__":
    main()
