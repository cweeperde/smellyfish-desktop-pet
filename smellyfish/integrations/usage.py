"""Usage limits of Claude Code (via the optional status line relay) and Codex (session files)."""

import glob
import json
import os
import time

from PySide6.QtCore import QObject, QTimer, Signal

CRITICAL = 95
WINDOWS = {"five_hour": "5-hour", "seven_day": "weekly", "primary": "5-hour", "secondary": "weekly"}


def codex_limits():
    root = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
    files = glob.glob(os.path.join(root, "*", "*", "*", "rollout-*.jsonl"))
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    if time.time() - os.path.getmtime(newest) > 7 * 86400:
        return None
    with open(newest, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 256 * 1024))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        if '"rate_limits"' not in line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        rl = _find(obj, "rate_limits")
        if isinstance(rl, dict):
            out = {}
            for key in ("primary", "secondary"):
                w = rl.get(key) or {}
                if w.get("used_percent") is not None:
                    out[key] = (float(w["used_percent"]), w.get("resets_at"))
            return out or None
    return None


def claude_limits(payload):
    rl = payload.get("rate_limits") or {}
    out = {}
    for key in ("five_hour", "seven_day"):
        w = rl.get(key) or {}
        pct = w.get("used_percentage", w.get("used_percent"))
        if pct is not None:
            out[key] = (float(pct), w.get("resets_at"))
    return out


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find(v, key)
            if r is not None:
                return r
    return None


class UsageWatch(QObject):
    warn = Signal(str, str, float, object, bool)  # source, window label, percent, resets_at, critical

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.latest = {}
        self.timer = QTimer(self, timeout=self.poll_codex)
        self.timer.start(60 * 1000)
        QTimer.singleShot(8000, self.poll_codex)

    def poll_codex(self):
        if not self.cfg.get("usage_warn") and not self.cfg.get("usage_critical"):
            return
        try:
            limits = codex_limits()
        except Exception:
            limits = None
        if limits:
            self.check("Codex", limits)

    def claude_status(self, payload):
        limits = claude_limits(payload)
        if limits:
            self.check("Claude", limits)

    def check(self, source, limits):
        self.latest[source] = limits
        level = int(self.cfg.get("usage_warn") or 0)
        critical = CRITICAL if self.cfg.get("usage_critical", True) else 0
        steps = sorted({s for s in (level, critical) if s})
        if not steps:
            return
        warned = dict(self.cfg.get("usage_warned") or {})
        now = time.time()
        warned = {k: v for k, v in warned.items() if now - v < 8 * 86400}
        changed = False
        for key, (pct, resets) in limits.items():
            reached = [s for s in steps if pct >= s]
            if not reached:
                continue
            window = resets or int(now // 86400)
            tags = [f"{source}:{key}:{s}:{window}" for s in reached]
            if all(t in warned for t in tags):
                continue
            for t in tags:
                warned[t] = now
            changed = True
            self.warn.emit(source, WINDOWS.get(key, key), pct, resets, bool(critical and pct >= critical))
        if changed:
            self.cfg.set("usage_warned", warned)

    def summary(self):
        parts = []
        for source, limits in self.latest.items():
            for key, (pct, _r) in limits.items():
                parts.append(f"{source} {WINDOWS.get(key, key)}: {pct:.0f} %")
        return ", ".join(parts)
