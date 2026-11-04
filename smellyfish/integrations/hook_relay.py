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
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/status", data=raw,
                                 headers={"Content-Type": "application/json"}, method="POST")
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


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "statusline":
        return statusline()
    try:
        raw = sys.stdin.buffer.read()
        payload = json.loads(raw or b"{}")
    except Exception:
        return
    event = payload.get("hook_event_name")
    waits = event == "PermissionRequest" or (event == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion")
    source = sys.argv[1] if len(sys.argv) > 1 else "claude"
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/hook?source={source}", data=raw,
                                 headers={"Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=590 if waits else 2) as resp:
            body = resp.read().decode("utf-8", "replace").strip()
    except Exception:
        return
    if body and body != "{}":
        sys.stdout.write(body)


if __name__ == "__main__":
    main()
