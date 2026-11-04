"""Release check: python tools/smoke_test.py [--exe dist/Smellyfish.exe]

1. imports every module and renders every animation frame,
2. checks that settings saves merge and that the updater refuses unverified downloads,
3. with --exe: starts the packaged app in a throwaway profile and sends it a hook event.
Exits non-zero on the first failure.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="smellyfish-smoke-")
os.environ["SMELLYFISH_HOME"] = HOME
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, ROOT)


def step(name):
    print(f"- {name}", flush=True)


def check_sources():
    step("import all modules")
    import importlib
    import pkgutil
    import smellyfish
    for mod in pkgutil.walk_packages(smellyfish.__path__, "smellyfish."):
        if mod.name != "smellyfish.__main__":
            importlib.import_module(mod.name)
    step("render every animation frame")
    from smellyfish.art import sprite
    for name, anim in sprite.build_all().items():
        for pose, ms in sprite.full(anim):
            assert ms > 0, name
            sprite.render(pose, 1)


def check_settings():
    step("settings keep changes from two instances")
    from smellyfish import settings
    a, b = settings.Settings(), settings.Settings()
    a.set("volume", 11)
    b.set("notify_volume", 22)
    with open(settings.PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert (data["volume"], data["notify_volume"]) == (11, 22), data


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def check_updater():
    step("updater installs only downloads with a matching sha256 digest")
    from PySide6.QtCore import QCoreApplication, QObject
    QCoreApplication.instance() or QCoreApplication([])
    from smellyfish import updater

    def attempt(payload, digest):
        d = tempfile.mkdtemp(dir=HOME)
        exe = os.path.join(d, "Smellyfish.exe")
        with open(exe, "wb") as f:
            f.write(b"old")
        asset = {"name": "Smellyfish.exe", "url": "https://x/asset", "size": len(payload)}
        if digest:
            asset["digest"] = digest
        rel = {"tag_name": "v999.0.0", "assets": [asset]}
        u = updater.Updater.__new__(updater.Updater)
        QObject.__init__(u)
        u.cfg, u.installed, u._busy = {}, None, True
        fake = lambda url, accept=None: _Resp(json.dumps(rel).encode() if url == updater.API else payload)
        with mock.patch.object(updater, "_get", fake), mock.patch.object(sys, "executable", exe):
            u._run(manual=False)
        with open(exe, "rb") as f:
            return f.read()

    assert attempt(b"new", None) == b"old", "accepted an update without digest"
    assert attempt(b"xyz", "sha256:" + hashlib.sha256(b"abc").hexdigest()) == b"old", "accepted a bad download"
    assert attempt(b"new", "sha256:" + hashlib.sha256(b"new").hexdigest()) == b"new", "refused a good update"


def check_exe(exe):
    step(f"start {exe}")
    port = "47977"
    env = dict(os.environ, SMELLYFISH_HOME=HOME, SMELLYFISH_PORT=port, SMELLYFISH_DEBUG="1")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def post(path, payload):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        return json.loads(opener.open(req, timeout=5).read())

    app = subprocess.Popen([os.path.abspath(exe)], env=env)
    try:
        for _ in range(240):
            try:
                opener.open(f"http://127.0.0.1:{port}/health", timeout=1).read()
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise AssertionError("the app did not start")
        step("hook relay reaches the app")
        relay = os.path.join(HOME, "relay", "smellyfish-relay.exe")
        event = {"hook_event_name": "UserPromptSubmit", "session_id": "smoke", "prompt": "hi"}
        r = subprocess.run([relay], input=json.dumps(event).encode(), env=env, capture_output=True, timeout=30)
        assert r.returncode == 0, r
        for _ in range(40):
            if post("/debug/state", {}).get("base") == "thinking":
                break
            time.sleep(0.25)
        else:
            raise AssertionError("the hook event did not reach the app")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(app.pid)], capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe")
    args = ap.parse_args()
    try:
        check_sources()
        check_settings()
        check_updater()
        if args.exe:
            check_exe(args.exe)
    finally:
        shutil.rmtree(HOME, ignore_errors=True)
    print("smoke test passed")


if __name__ == "__main__":
    main()
