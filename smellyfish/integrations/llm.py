"""Optional local text model (Ollama or a llama.cpp server). Only talks to this PC or a private network."""
import ipaddress
import json
import socket
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QTimer, Signal

from smellyfish.integrations import llm_server

BACKENDS = {
    "ollama": {"label": "Ollama", "url": "http://127.0.0.1:11434"},
    "llamacpp": {"label": "llama.cpp server", "url": "http://127.0.0.1:8080"},
}

PERSONA = (
    "You are Smellyfish, a tiny pixel-art jellyfish who lives on the user's desktop. "
    "Answer in the language the user writes in. Be short: one to three sentences, under 50 words unless the user "
    "asks for more. Be warm, cute and a little playful (a rare 'blub' or a bubble is fine), but always put the "
    "useful answer first and keep it correct. Plain text only: no markdown headings, no long lists, no emoji walls. "
    "If you do not know something, say so instead of guessing."
)
TIMEOUT = 120


def system_prompt(extra="", persona=True):
    """The text that tells the model who it is (see PERSONA above). Extra instructions come from the settings."""
    extra = " ".join((extra or "").split())[:600]
    base = PERSONA if persona else ""
    return (base + (" " + extra if extra else "")).strip()


def guide(error, model=""):
    """A short how-to for the most common problems, shown in the chat window."""
    e = (error or "").lower()
    name = model or "<model>"
    if "404" in e or "not found" in e:
        return (f"The server does not have this model yet.\n1. Open a terminal and run:  ollama pull {name}\n"
                "2. Come back to Settings > Local AI chat, press Find models and pick it.")
    if "find ollama" in e or "find llama" in e or "set its path" in e:
        return ("Smellyfish could not find the model program.\n1. Install Ollama from ollama.com (or download "
                "llama.cpp).\n2. In Settings > Local AI chat, type the path of ollama.exe or llama-server.exe "
                "under Program.")
    if "gguf" in e:
        return ("llama.cpp needs a model file.\n1. Put a .gguf model in a folder.\n2. Enter that folder under "
                "Models folder, press Find models and pick the file.")
    if "took too long" in e or "stopped right after" in e:
        return ("The model server did not come up in time.\n1. A big model can need a minute on its first start "
                "- try asking again.\n2. If it keeps failing, start the server yourself once "
                "(ollama serve) and check that the model runs there.")
    if "reach" in e or "not running" in e or "private network" in e:
        return ("Smellyfish cannot reach the model server.\n1. Start Ollama (or llama-server), or switch on "
                "'Start the model server quietly' in Settings > Local AI chat.\n2. Check the address under "
                "Local model (empty = this PC).")
    return ("Something went wrong with the local model.\n1. Check that the server is running and the model is "
            "installed.\n2. Try another model under Settings > Local AI chat > Find models.")


def safe_base(url, backend):
    """Normalised base URL, or None when the host is not this PC or a private network address."""
    url = (url or "").strip().rstrip("/") or BACKENDS.get(backend, BACKENDS["ollama"])["url"]
    if "://" not in url:
        url = "http://" + url
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return None
    host = p.hostname
    if host != "localhost" and not host.endswith(".local"):
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            try:
                ip = ipaddress.ip_address(socket.gethostbyname(host))
            except (OSError, ValueError):
                return None
        if not (ip.is_loopback or ip.is_private or ip.is_link_local):
            return None
    return f"{p.scheme}://{p.netloc}"


def _request(base, path, body=None, timeout=5):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def list_models(backend, url):
    base = safe_base(url, backend)
    if base is None:
        raise ValueError("Only this PC or a private network address is allowed")
    if backend == "ollama":
        with _request(base, "/api/tags") as r:
            return sorted(m["name"] for m in json.load(r).get("models", []))
    with _request(base, "/v1/models") as r:
        return sorted(m["id"] for m in json.load(r).get("data", []))


class LLM(QObject):
    models_ready = Signal(list, str)       # models, error
    chunk = Signal(int, str)               # request id, text so far
    finished = Signal(int, str, str)      # request id, text, error
    phase = Signal(int, str)               # request id, "starting" | "loading" | "answering"

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.history = []
        self.rid = 0
        self.loaded = False
        self.busy = False
        self.idle = QTimer(self, singleShot=True, timeout=self.unload)
        self.server = llm_server.ServerProcess()

    def enabled(self):
        return bool(self.cfg.get("llm_enabled") and self.cfg.get("llm_model"))

    def base(self):
        return safe_base(self.cfg.get("llm_url"), self.cfg.get("llm_backend"))

    def turns(self):
        return max(0, min(20, int(self.cfg.get("llm_history") or 0)))

    def keep_alive(self):
        return int(self.cfg.get("llm_idle_min") or 5)

    def model_loaded(self, base, backend, model):
        """Ollama can tell which models sit in memory; for other servers a running server counts as loaded."""
        if backend != "ollama":
            return not self.server.owned() or self.loaded
        try:
            with _request(base, "/api/ps", timeout=2) as r:
                return any(m.get("name") == model or m.get("model") == model
                           for m in json.load(r).get("models", []))
        except (OSError, ValueError):
            return False

    def start_server(self):
        """Starts the model server in the background if it is not running. Returns an error text or ""."""
        if not self.cfg.get("llm_autostart"):
            return ""
        base = self.base()
        if base is None:
            return "Only this PC or a private network address is allowed"
        return self.server.ensure(self.cfg.get("llm_backend"), base, self.cfg.get("llm_model"),
                                  self.cfg.get("llm_binary") or "", self.cfg.get("llm_models_dir") or "")

    def refresh_models(self):
        backend, url = self.cfg.get("llm_backend"), self.cfg.get("llm_url")
        folder = self.cfg.get("llm_models_dir") or ""

        def work():
            try:
                if backend == "llamacpp" and folder:
                    found = llm_server.list_gguf(folder)
                    if not found:
                        raise ValueError("No .gguf files in that folder")
                    return self.models_ready.emit(found, "")
                if self.cfg.get("llm_autostart") and backend == "ollama" and self.base() \
                        and not llm_server.is_up(self.base(), backend):
                    error = self.server.ensure(backend, self.base(), "", self.cfg.get("llm_binary") or "")
                    if error:
                        raise ValueError(error)
                self.models_ready.emit(list_models(backend, url), "")
            except (OSError, ValueError, KeyError) as e:
                self.models_ready.emit([], str(getattr(e, "reason", e)))

        threading.Thread(target=work, daemon=True).start()

    def preload(self):
        """Loads the model in the background so the first answer is quick."""
        if not self.enabled() or self.loaded or not self.cfg.get("llm_autoload"):
            return
        base, model, backend = self.base(), self.cfg["llm_model"], self.cfg.get("llm_backend")
        if base is None:
            return
        self.loaded = True
        self.arm_idle()

        def work():
            try:
                if self.start_server():
                    return
                if backend == "ollama":
                    _request(base, "/api/generate", {"model": model, "keep_alive": f"{self.keep_alive()}m"},
                             timeout=TIMEOUT).close()
                else:
                    _request(base, "/models/load", {"model": model}, timeout=TIMEOUT).close()
            except (OSError, ValueError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def arm_idle(self):
        self.idle.start(self.keep_alive() * 60000)

    def unload_now(self):
        """The Unload button: frees the model (and stops a server Smellyfish started) right away."""
        if self.busy:
            return False
        self.idle.stop()
        self.unload()
        return True

    def unload(self):
        """Frees the model's memory after it was not used for a while."""
        if self.busy:
            return self.arm_idle()
        if not self.loaded:
            return
        self.loaded = False
        base, model, backend = self.base(), self.cfg.get("llm_model"), self.cfg.get("llm_backend")
        if base is None or not model:
            return

        def work():
            try:
                if backend == "ollama" and llm_server.is_up(base, backend):
                    _request(base, "/api/generate", {"model": model, "keep_alive": 0}).close()
                elif backend != "ollama" and not self.server.owned():
                    _request(base, "/models/unload", {"model": model}).close()
            except (OSError, ValueError):
                pass
            self.server.stop()

        threading.Thread(target=work, daemon=True).start()

    def reset(self):
        self.history = []

    def ask(self, text):
        """Sends a message; the answer arrives through chunk / finished. Returns the request id."""
        self.rid += 1
        rid = self.rid
        base = self.base()
        if not self.enabled() or base is None:
            QTimer.singleShot(0, lambda: self.finished.emit(rid, "", "Local model is not set up"))
            return rid
        self.history = (self.history + [{"role": "user", "content": text}])[-max(1, self.turns() * 2):]
        prompt = system_prompt(self.cfg.get("llm_prompt"), self.cfg.get("llm_persona") is not False)
        messages = ([{"role": "system", "content": prompt}] if prompt else []) + self.history
        limit = max(32, int(self.cfg.get("llm_max_tokens") or 260))
        temp = float(self.cfg.get("llm_temp") or 0.7)
        think = self.cfg.get("llm_think") or "off"
        ctx = int(self.cfg.get("llm_ctx") or 0)
        backend, model = self.cfg.get("llm_backend"), self.cfg["llm_model"]
        keep = f"{self.keep_alive()}m"
        self.busy, self.loaded = True, True
        self.idle.stop()

        def work():
            out, error = "", ""
            try:
                if not llm_server.is_up(base, backend):
                    self.phase.emit(rid, "starting")
                problem = self.start_server()
                if problem:
                    self.finished.emit(rid, "", problem)
                    return
                if not self.model_loaded(base, backend, model):
                    self.phase.emit(rid, "loading")
                if backend == "ollama":
                    options = {"temperature": temp, "num_predict": limit}
                    if ctx:
                        options["num_ctx"] = ctx
                    body = {"model": model, "messages": messages, "stream": True, "keep_alive": keep,
                            "options": options}
                    if think != "auto":
                        body["think"] = think == "on"
                    path = "/api/chat"
                else:
                    body = {"model": model, "messages": messages, "stream": True, "temperature": temp,
                            "max_tokens": limit}
                    if think != "auto":
                        body["chat_template_kwargs"] = {"enable_thinking": think == "on"}
                    path = "/v1/chat/completions"
                try:
                    stream = _request(base, path, body, timeout=TIMEOUT)
                except urllib.error.HTTPError as e:
                    if e.code != 400 or backend != "ollama":
                        raise
                    body.pop("think", None)
                    stream = _request(base, path, body, timeout=TIMEOUT)
                first = True
                with stream as r:
                    for raw in r:
                        if first:
                            first = False
                            self.phase.emit(rid, "answering")
                        line = raw.decode("utf-8", "replace").strip()
                        if backend != "ollama":
                            if not line.startswith("data:"):
                                continue
                            line = line[5:].strip()
                            if line == "[DONE]":
                                break
                        if not line:
                            continue
                        obj = json.loads(line)
                        if backend == "ollama":
                            piece = (obj.get("message") or {}).get("content", "")
                            last = obj.get("done")
                        else:
                            choice = (obj.get("choices") or [{}])[0]
                            piece = (choice.get("delta") or {}).get("content") or ""
                            last = choice.get("finish_reason")
                        if piece:
                            out += piece
                            if rid == self.rid:
                                self.chunk.emit(rid, out)
                        if last:
                            break
            except urllib.error.HTTPError as e:
                error = f"The model server answered {e.code}" + (" (model not found)" if e.code == 404 else "")
            except (OSError, ValueError) as e:
                error = "Could not reach the model server" if not out else ""
            out = out.strip()
            if not out and not error:
                error = "The model did not answer. Try another model or ask again."
            if out:
                self.history = (self.history + [{"role": "assistant", "content": out}])[-max(1, self.turns() * 2):]
            self.finished.emit(rid, out, error if not out else "")

        threading.Thread(target=work, daemon=True).start()
        return rid

    def done(self):
        self.busy = False
        self.arm_idle()

    def shutdown(self):
        """Quit: unload right away so the model does not keep memory after Smellyfish is closed."""
        self.idle.stop()
        base, model, backend = self.base(), self.cfg.get("llm_model"), self.cfg.get("llm_backend")
        if self.server.owned():
            return self.server.stop()
        if self.loaded and self.cfg.get("llm_unload_on_quit") and base and model:
            try:
                if backend == "ollama":
                    _request(base, "/api/generate", {"model": model, "keep_alive": 0}, timeout=2).close()
                else:
                    _request(base, "/models/unload", {"model": model}, timeout=2).close()
            except (OSError, ValueError):
                pass
