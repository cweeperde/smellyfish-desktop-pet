"""Claude Code hook command: forwards the event JSON to the Smellyfish app.

Stays silent (exit 0, no output) when the app is not running, so Claude Code
behaves exactly as without hooks.
"""

import json
import os
import sys
import urllib.request

PORT = int(os.environ.get("SMELLYFISH_PORT", "47811"))


def statusline():
    try:
        raw = sys.stdin.buffer.read()
        payload = json.loads(raw or b"{}")
    except Exception:
        return
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/status", data=raw, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=0.5).read()
    except Exception:
        pass
    parts = [((payload.get("model") or {}).get("display_name") or "Claude")]
    rl = payload.get("rate_limits") or {}
    for key, label in (("five_hour", "5h"), ("seven_day", "week")):
        pct = (rl.get(key) or {}).get("used_percentage")
        if pct is not None:
            parts.append(f"{label} {float(pct):.0f}%")
    sys.stdout.write(" | ".join(parts))


OTHERS = ("gemini", "cursor", "copilot", "antigravity", "deepseek")
DEEPSEEK_STDIN = ("message_submit", "turn_end", "waiting_for_user")


def read_payload(source, event):
    """The hook JSON from stdin; DeepSeek passes most of its context as environment variables instead."""
    if source != "deepseek":
        raw = sys.stdin.buffer.read()
        return raw, json.loads(raw or b"{}")
    payload = {}
    if event in DEEPSEEK_STDIN:
        try:
            payload = json.loads(sys.stdin.buffer.read() or b"{}")
        except Exception:
            payload = {}
    env = os.environ.get
    payload.setdefault("session_id", env("DEEPSEEK_SESSION_ID", ""))
    payload.setdefault("tool_name", env("DEEPSEEK_TOOL_NAME", ""))
    payload.setdefault("message", env("DEEPSEEK_MESSAGE", "") or env("DEEPSEEK_ERROR", ""))
    payload.setdefault("cwd", env("DEEPSEEK_WORKSPACE", ""))
    return json.dumps(payload).encode(), payload


def shell(action, path):
    """Finder Quick Action: hand a right-clicked file or folder to the running pet."""
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


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "statusline":
        return statusline()
    if len(sys.argv) > 3 and sys.argv[1] == "shell":
        return shell(sys.argv[2], sys.argv[3])
    try:
        raw, payload = read_payload(
            sys.argv[1] if len(sys.argv) > 1 else "claude", sys.argv[2] if len(sys.argv) > 2 else ""
        )
    except Exception:
        return
    event = payload.get("hook_event_name")
    waits = event == "PermissionRequest" or (event == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion")
    source = sys.argv[1] if len(sys.argv) > 1 else "claude"
    other = source in OTHERS
    query = f"source={source}"
    if other and len(sys.argv) > 2:
        query += f"&event={sys.argv[2]}"
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/hook?{query}", data=raw, headers={"Content-Type": "application/json"}, method="POST"
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=590 if waits else 2) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
    except Exception:
        body = ""
    if body and body != "{}":
        sys.stdout.write(body)
    elif other:
        if source == "cursor":
            sys.stdout.write('{"continue": true}')
        elif source == "antigravity" and len(sys.argv) > 2 and sys.argv[2] == "Stop":
            sys.stdout.write('{"decision": "stop"}')
        else:
            sys.stdout.write("{}")


if __name__ == "__main__":
    main()
