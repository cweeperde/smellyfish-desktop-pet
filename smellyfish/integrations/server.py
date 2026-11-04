"""Local HTTP server that receives Claude Code hook events (via hook_relay.py).

Most events are answered immediately with {}. Events the pet can answer with a bubble
(PermissionRequest, single-select AskUserQuestion) wait until the user clicks or the
wait expires; every failure path answers {} so Claude Code falls back to the terminal.
"""
import itertools
import logging
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QObject, Signal

log = logging.getLogger("smellyfish.hooks")

HOST = "127.0.0.1"
PORT = int(os.environ.get("SMELLYFISH_PORT", "47811"))
WAIT_S = float(os.environ.get("SMELLYFISH_WAIT", "570"))


def is_answerable(payload):
    event = payload.get("hook_event_name")
    if event == "PermissionRequest":
        return payload.get("tool_name") != "AskUserQuestion"
    if event == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
        qs = (payload.get("tool_input") or {}).get("questions") or []
        return 0 < len(qs) <= 4 and all(q.get("options") for q in qs)
    return False


class Pending:
    def __init__(self, rid, payload):
        self.rid = rid
        self.payload = payload
        self.done = threading.Event()
        self.result = {}


class HookServer(QObject):
    event = Signal(object)          # payload dict, non-blocking
    ask = Signal(object)            # Pending, needs an answer
    expired = Signal(str)           # rid whose wait ran out
    debug_cmd = Signal(object)
    status = Signal(object)         # Claude Code status line JSON

    def __init__(self, policy=None):
        super().__init__()
        self.policy = policy or (lambda payload: True)
        self._ids = itertools.count(1)
        self._pending = {}
        self._lock = threading.Lock()
        self.debug = {}
        self.httpd = None

    def start(self):
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _reply(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._reply({"ok": True, "app": "smellyfish"} if self.path == "/health" else {}, 200)

            def do_POST(self):
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    payload = json.loads(self.rfile.read(n) or b"{}")
                except Exception:
                    return self._reply({})
                if self.path.startswith("/debug/") and os.environ.get("SMELLYFISH_DEBUG"):
                    fn = hub.debug.get(self.path[7:])
                    return self._reply(fn(payload) if fn else {"error": "unknown"})
                route, _, query = self.path.partition("?")
                if route == "/status" and isinstance(payload, dict):
                    hub.status.emit(payload)
                    return self._reply({})
                if route != "/hook" or not isinstance(payload, dict):
                    return self._reply({})
                payload["_source"] = "codex" if "source=codex" in query else "claude"
                try:
                    self._reply(hub.handle(payload))
                except Exception:
                    self._reply({})

        self.httpd = ThreadingHTTPServer((HOST, PORT), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def handle(self, payload):
        answerable = is_answerable(payload)
        allowed = answerable and self.policy(payload)
        log.info("hook %s %s from %s: %s", payload.get("hook_event_name"), payload.get("tool_name") or "",
                 payload.get("_source"), "bubble" if allowed else "answerable but off" if answerable else "info")
        if not allowed:
            self.event.emit(payload)
            return {}
        p = Pending(str(next(self._ids)), payload)
        with self._lock:
            self._pending[p.rid] = p
        self.ask.emit(p)
        answered = p.done.wait(WAIT_S)
        with self._lock:
            self._pending.pop(p.rid, None)
        if not answered:
            self.expired.emit(p.rid)
            return {}
        return p.result

    def resolve(self, rid, result):
        with self._lock:
            p = self._pending.get(rid)
        if p and not p.done.is_set():
            p.result = result or {}
            p.done.set()

    def resolve_all(self):
        with self._lock:
            items = list(self._pending.values())
        for p in items:
            if not p.done.is_set():
                p.result = {}
                p.done.set()

    def stop(self):
        self.resolve_all()
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


def ask_answer(payload, answers):
    tool_input = dict(payload.get("tool_input") or {})
    tool_input["answers"] = answers
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "updatedInput": tool_input}}


def permission_answer(payload, choice):
    if choice == "deny":
        decision = {"behavior": "deny", "message": "Denied by the user in Smellyfish."}
    else:
        decision = {"behavior": "allow"}
        suggestions = payload.get("permission_suggestions") or []
        if choice == "always" and suggestions:
            decision["updatedPermissions"] = [suggestions[0]]
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}
