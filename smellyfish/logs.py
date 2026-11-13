r"""Writes warnings and errors (including uncaught exceptions) to %APPDATA%\Smellyfish\smellyfish.log."""

import logging
import logging.handlers
import os
import sys
import threading

from smellyfish.paths import HOME_DIR

PATH = os.path.join(HOME_DIR, "smellyfish.log")


def setup():
    os.makedirs(HOME_DIR, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(PATH, maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    log = logging.getLogger("smellyfish")

    def hook(kind, value, tb):
        log.error("uncaught exception", exc_info=(kind, value, tb))
        if sys.__stderr__:
            sys.__excepthook__(kind, value, tb)

    sys.excepthook = hook
    threading.excepthook = lambda a: log.error(
        "uncaught exception in thread %s", a.thread, exc_info=(a.exc_type, a.exc_value, a.exc_traceback)
    )
