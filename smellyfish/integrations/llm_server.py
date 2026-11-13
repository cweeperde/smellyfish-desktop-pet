"""Starts and stops the model server (Ollama or llama.cpp) quietly in the background, only when it is needed."""

import glob
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

CREATE_NO_WINDOW = 0x08000000
START_WAIT = {"ollama": 20, "llamacpp": 180}
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def binary_for(backend, configured=""):
    """Path of ollama.exe / llama-server.exe: the configured one, then PATH, then the usual places."""
    if configured and os.path.isfile(configured):
        return configured
    exe = ".exe" if sys.platform == "win32" else ""
    if backend == "ollama":
        guesses = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
            "/Applications/Ollama.app/Contents/Resources/ollama",
            "/opt/homebrew/bin/ollama",
            "/usr/local/bin/ollama",
        ]
        names = ["ollama"]
    else:
        guesses = glob.glob(
            os.path.join(os.path.expanduser("~"), "llama.cpp", "**", "llama-server" + exe), recursive=True
        ) + ["/opt/homebrew/bin/llama-server", "/usr/local/bin/llama-server"]
        names = ["llama-server"]
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return next((g for g in guesses if os.path.isfile(g)), "")


def list_gguf(folder):
    """Model files (.gguf) in a folder, newest first; split models only list their first part."""
    if not folder or not os.path.isdir(folder):
        return []
    files = glob.glob(os.path.join(folder, "**", "*.gguf"), recursive=True)
    files = [f for f in files if "-of-" not in os.path.basename(f) or "-00001-of-" in os.path.basename(f)]
    files.sort(key=os.path.getmtime, reverse=True)
    return [os.path.relpath(f, folder) for f in files]


def is_up(base, backend):
    path = "/api/tags" if backend == "ollama" else "/health"
    try:
        with urllib.request.urlopen(base + path, timeout=1.5) as r:
            return r.status == 200
    except OSError:
        return False
    except ValueError:
        return False


def is_local(base):
    return (urlparse(base).hostname or "") in LOCAL_HOSTS


class ServerProcess:
    """Owns the server process when Smellyfish had to start it. A server that was already running is left alone."""

    def __init__(self):
        self.proc = None
        self.model = None

    def owned(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure(self, backend, base, model, binary="", models_dir="", extra=""):
        """Makes sure a server answers at base. Returns an error text, or "" when it is ready."""
        running = is_up(base, backend)
        if running and not self.owned():
            return ""
        if backend == "llamacpp" and running and self.owned() and self.model == model:
            return ""
        if backend == "ollama" and running:
            return ""
        if not is_local(base):
            return "The server at that address is not running"
        if self.owned():
            self.stop()
        exe = binary_for(backend, binary)
        if not exe:
            return (
                "Could not find "
                + ("ollama" if backend == "ollama" else "llama-server")
                + " (set its path in the settings)"
            )
        port = urlparse(base).port or (11434 if backend == "ollama" else 8080)
        if backend == "ollama":
            cmd = [exe, "serve"]
            env = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{port}")
        else:
            gguf = os.path.join(models_dir, model) if models_dir and model else model
            if not gguf or not os.path.isfile(gguf):
                return "Pick a .gguf model file in the settings"
            cmd = [exe, "-m", gguf, "--host", "127.0.0.1", "--port", str(port)] + (extra.split() if extra else [])
            env = dict(os.environ)
        try:
            self.proc = subprocess.Popen(
                cmd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except OSError as e:
            return f"Could not start the model server ({e.strerror or e})"
        self.model = model
        deadline = time.time() + START_WAIT[backend]
        while time.time() < deadline:
            if self.proc.poll() is not None:
                self.proc = None
                return "The model server stopped right after starting"
            if is_up(base, backend):
                return ""
            time.sleep(0.4)
        self.stop()
        return "The model server took too long to start"

    def stop(self):
        proc, self.proc, self.model = self.proc, None, None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=4)
        except (OSError, subprocess.TimeoutExpired):
            try:
                proc.kill()
            except OSError:
                pass
