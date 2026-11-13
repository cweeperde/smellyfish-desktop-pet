"""Adds (or removes) the Smellyfish hooks for Claude Code, Codex, Gemini CLI, Antigravity, Cursor,
GitHub Copilot and DeepSeek-TUI.

  python -m smellyfish.integrations.install_hooks                      print the Claude Code hooks JSON only
  python -m smellyfish.integrations.install_hooks --install user       ~/.claude/settings.json
  python -m smellyfish.integrations.install_hooks --install project    ./.claude/settings.json
  python -m smellyfish.integrations.install_hooks --install local      ./.claude/settings.local.json
  python -m smellyfish.integrations.install_hooks --install codex      ~/.codex/hooks.json
  python -m smellyfish.integrations.install_hooks --install gemini     ~/.gemini/settings.json
  python -m smellyfish.integrations.install_hooks --install cursor     ~/.cursor/hooks.json
  python -m smellyfish.integrations.install_hooks --install copilot    ~/.copilot/hooks/smellyfish.json
  python -m smellyfish.integrations.install_hooks --install antigravity ~/.gemini/config/hooks.json
  python -m smellyfish.integrations.install_hooks --install deepseek   ~/.codewhale/config.toml
  python -m smellyfish.integrations.install_hooks --remove <scope>     remove them again

The file is backed up before every change (*.bak: before the first one, *.bak.last: before the latest).
Codex asks you to trust new hooks once (/hooks).
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
    "PreCompact": (None, 5),
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
GEMINI_EVENTS = {"BeforeAgent": 10, "BeforeTool": 10, "AfterAgent": 10, "SessionEnd": 5, "Notification": 10}
CURSOR_EVENTS = {"beforeSubmitPrompt": 10, "postToolUse": 10, "stop": 10, "sessionEnd": 5}
COPILOT_EVENTS = {"userPromptSubmitted": 10, "postToolUse": 10, "agentStop": 10, "sessionEnd": 5, "notification": 10}
ANTIGRAVITY_EVENTS = {"PreInvocation": 10, "PostToolUse": 10, "Stop": 10}
DEEPSEEK_EVENTS = {
    "message_submit": 10,
    "tool_call_after": 10,
    "turn_end": 10,
    "session_end": 5,
    "waiting_for_user": 10,
}
OTHERS = {
    "gemini": GEMINI_EVENTS,
    "cursor": CURSOR_EVENTS,
    "copilot": COPILOT_EVENTS,
    "antigravity": ANTIGRAVITY_EVENTS,
    "deepseek": DEEPSEEK_EVENTS,
}
TOML_BEGIN, TOML_END = "# smellyfish hooks begin", "# smellyfish hooks end"
MARKERS = ("hook_relay.py", "smellyfish-relay")


def claude_entry(matcher, timeout):
    exe, args = relay_command()
    if os.name != "nt" and " " in exe:
        import shlex

        exe = shlex.quote(exe)
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


def other_command(source, event):
    exe, args = relay_command()
    if os.name == "nt":
        return " ".join([_bare(exe)] + [_bare(a) for a in args] + [source, event])
    return " ".join(f'"{p}"' for p in [exe] + args + [source, event])


def other_entry(source, event, timeout):
    cmd = other_command(source, event)
    if source == "gemini":
        return {"hooks": [{"type": "command", "command": cmd, "name": "smellyfish", "timeout": timeout * 1000}]}
    if source == "cursor":
        return {"command": cmd, "timeout": timeout}
    if source == "antigravity":
        h = {"type": "command", "command": cmd, "timeout": timeout}
        return {"matcher": "*", "hooks": [h]} if event == "PostToolUse" else h
    return {"type": "command", "command": cmd, "timeoutSec": timeout}


def antigravity_hooks():
    return {ev: [other_entry("antigravity", ev, t)] for ev, t in ANTIGRAVITY_EVENTS.items()}


def deepseek_block():
    lines = [TOML_BEGIN]
    for ev, t in DEEPSEEK_EVENTS.items():
        lines += [
            "[[hooks.hooks]]",
            f'event = "{ev}"',
            f"command = {json.dumps(other_command('deepseek', ev))}",
            'name = "smellyfish"',
            f"timeout_secs = {t}",
            "",
        ]
    lines.append(TOML_END)
    return "\n".join(lines) + "\n"


def _deepseek_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _split_block(text):
    a, b = text.find(TOML_BEGIN), text.find(TOML_END)
    if a < 0 or b < a:
        return text, None
    end = b + len(TOML_END)
    return text[:a] + text[end:].lstrip("\n"), text[a:end] + "\n"


def ours(e):
    text = json.dumps(e).replace("\\\\", "/").lower()
    return any(m in text for m in MARKERS)


def target(scope):
    home = os.path.expanduser("~")
    if scope == "codex":
        return os.path.join(home, ".codex", "hooks.json")
    if scope == "gemini":
        return os.path.join(home, ".gemini", "settings.json")
    if scope == "cursor":
        return os.path.join(home, ".cursor", "hooks.json")
    if scope == "antigravity":
        return os.path.join(home, ".gemini", "config", "hooks.json")
    if scope == "deepseek":
        return os.path.join(home, ".codewhale", "config.toml")
    if scope == "copilot":
        base = os.environ.get("COPILOT_HOME") or os.path.join(home, ".copilot")
        return os.path.join(base, "hooks", "smellyfish.json")
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    name = "settings.json" if scope == "project" else "settings.local.json"
    return os.path.join(os.getcwd(), ".claude", name)


class ConfigError(Exception):
    """The tool's settings file exists but is not a JSON object; it is never touched in that state."""


def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ConfigError(f"{path}: {e.__class__.__name__}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: not a JSON object")
    return data


def _backup(path):
    """*.bak keeps the file as it was before Smellyfish first changed it, *.bak.last the state before this change."""
    if os.path.exists(path):
        first = path + ".bak"
        shutil.copy2(path, first + ".last" if os.path.exists(first) else first)


def _write(path, data=None, text=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if text is None:
            json.dump(data, f, indent=2)
        else:
            f.write(text)
    os.replace(tmp, path)


def is_installed(scope="user"):
    try:
        return _is_installed(scope)
    except ConfigError:
        return False


def _is_installed(scope):
    if scope == "deepseek":
        return _split_block(_deepseek_text(target(scope)))[1] is not None
    if scope == "antigravity":
        return ours(load(target(scope)).get("smellyfish") or {})
    data = load(target(scope))
    return any(ours(e) for entries in data.get("hooks", {}).values() for e in entries)


def wanted_for(scope):
    if scope == "codex":
        return {ev: codex_entry(t) for ev, t in CODEX_EVENTS.items()}
    if scope in OTHERS:
        return {ev: other_entry(scope, ev, t) for ev, t in OTHERS[scope].items()}
    return {ev: claude_entry(m, t) for ev, (m, t) in CLAUDE_EVENTS.items()}


def needs_update(scope):
    try:
        return _needs_update(scope)
    except ConfigError:
        return False


def _needs_update(scope):
    if scope == "deepseek":
        return _split_block(_deepseek_text(target(scope)))[1] != deepseek_block()
    if scope == "antigravity":
        return load(target(scope)).get("smellyfish") != antigravity_hooks()
    data = load(target(scope)).get("hooks", {})
    wanted = wanted_for(scope)
    installed = any(ours(e) for entries in data.values() for e in entries)
    for ev, entry in wanted.items():
        mine = [e for e in data.get(ev, []) if ours(e)]
        if installed and mine != [entry]:
            return True
    return False


def _apply_special(scope, install):
    path = target(scope)
    if scope == "deepseek":
        rest, _ = _split_block(_deepseek_text(path))
        text = (rest.rstrip("\n") + ("\n\n" if rest.strip() else "") + deepseek_block()) if install else rest
        data = None
    else:
        data = load(path)
        if install:
            data["smellyfish"] = antigravity_hooks()
        else:
            data.pop("smellyfish", None)
    _backup(path)
    _write(path, data, text if data is None else None)
    return path


def apply(scope, install=True):
    if scope in ("deepseek", "antigravity"):
        return _apply_special(scope, install)
    path = target(scope)
    data = load(path)
    current = data.setdefault("hooks", {})
    if not isinstance(current, dict):
        raise ConfigError(f"{path}: hooks is not an object")
    wanted = wanted_for(scope)
    if scope == "cursor":
        data.setdefault("version", 1)
    for ev in set(current) | set(wanted):
        current[ev] = [e for e in current.get(ev) or [] if not ours(e)]
        if install and ev in wanted:
            current[ev].append(wanted[ev])
        if not current[ev]:
            del current[ev]
    if not current:
        del data["hooks"]
    if scope == "copilot":
        if not install:
            if os.path.exists(path):
                os.remove(path)
            return path
        data["version"] = 1
    if not install and not os.path.exists(path):
        return path
    _backup(path)
    _write(path, data)
    return path


def statusline_command():
    exe, args = relay_command()
    return " ".join(f'"{p}"' for p in [exe] + args + ["statusline"])


def _statusline():
    try:
        return load(target("user")).get("statusLine")
    except ConfigError:
        return None


def statusline_state():
    """None, "ours" or "other" (someone else's status line, which we never replace)."""
    sl = _statusline()
    return ("ours" if ours(sl) else "other") if sl else None


def statusline_stale():
    sl = _statusline()
    return bool(sl) and ours(sl) and sl.get("command") != statusline_command()


def apply_statusline(install=True):
    path = target("user")
    try:
        data = load(path)
    except ConfigError:
        return False
    current = data.get("statusLine")
    if current and not ours(current):
        return False
    if not install and not current:
        return True
    _backup(path)
    if install:
        data["statusLine"] = {"type": "command", "command": statusline_command(), "padding": 0}
    else:
        data.pop("statusLine", None)
    _write(path, data)
    return True


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    scopes = ["user", "project", "local", "codex", "gemini", "cursor", "copilot", "antigravity", "deepseek"]
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
