"""About window: who made Smellyfish, where to find it and who helped."""
import json
import threading
import urllib.request

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from smellyfish import REPO, __version__
from smellyfish.art import sprite
from smellyfish.ui import theme

CREATOR = "cweeper"
OWNER = REPO.split("/")[0]
PROFILE = f"https://github.com/{OWNER}"
PROJECT = f"https://github.com/{REPO}"
_cache = {"names": None}


class _Loader(QObject):
    done = Signal(list, str)


def fetch_contributors():
    """Names of the people who contributed to the GitHub project (one request to the GitHub API)."""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/contributors?per_page=50",
                                 headers={"User-Agent": "Smellyfish desktop pet", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return [str(c.get("login")) for c in data if c.get("login") and c.get("type") != "Bot"]


class AboutWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("About Smellyfish")
        theme.apply(self, app)
        self.resize(440, 560)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        root.addWidget(theme.banner("Smellyfish", f"Version {__version__}",
                                    sprite.Pose(eyes="happy", blush=True, arm_f=("rest_l", "up_r"))))
        body = QVBoxLayout()
        body.setContentsMargins(16, 4, 16, 0)
        body.setSpacing(8)
        root.addLayout(body, 1)

        blurb = QLabel("A tiny pixel-art jellyfish that lives on your desktop and keeps an eye on your PC and "
                       "your coding agents.")
        blurb.setWordWrap(True)
        body.addWidget(blurb)

        self.made = QLabel()
        self.made.setTextFormat(Qt.RichText)
        self.made.setOpenExternalLinks(True)
        self.retint()
        theme.listen(self.retint)
        body.addWidget(self.made)

        title = QLabel("Contributors")
        title.setObjectName("title")
        body.addWidget(title)
        self.people = QListWidget()
        self.people.setSelectionMode(QListWidget.NoSelection)
        body.addWidget(self.people, 1)
        self.note = QLabel("")
        self.note.setObjectName("hint")
        body.addWidget(self.note)

        legal = QLabel("Copyright (c) 2026 cweeper. All rights reserved. Not affiliated with Anthropic, OpenAI "
                       "or Discord.")
        legal.setObjectName("hint")
        legal.setWordWrap(True)
        body.addWidget(legal)

        row = QHBoxLayout()
        row.setContentsMargins(16, 0, 16, 0)
        for text, fn in (("GitHub project", lambda: QDesktopServices.openUrl(QUrl(PROJECT))),
                         ("Profile", lambda: QDesktopServices.openUrl(QUrl(PROFILE))),
                         ("Check for updates", lambda: app.updater.check(manual=True))):
            b = QPushButton(text)
            b.setObjectName("secondary")
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(close)
        root.addLayout(row)

        self.loader = _Loader()
        self.loader.done.connect(self.show_names)

    def retint(self):
        self.made.setText(f'Created by <b style="color:{theme.HEAD}">{CREATOR}</b><br>'
                          f'<a style="color:{theme.HEAD}" href="{PROFILE}">github.com/{OWNER}</a>')

    def refresh(self):
        if _cache["names"] is not None:
            return self.show_names(_cache["names"], "")
        self.people.clear()
        self.note.setText("Loading contributors from GitHub...")

        def work():
            try:
                self.loader.done.emit(fetch_contributors(), "")
            except (OSError, ValueError) as e:
                self.loader.done.emit([], f"Could not load the list ({e.__class__.__name__}). Are you offline?")

        threading.Thread(target=work, daemon=True).start()

    def show_names(self, names, error):
        self.people.clear()
        if error:
            self.note.setText(error)
            return
        _cache["names"] = names
        self.people.addItems(names or [CREATOR])
        self.note.setText("Names only, fetched once from the public GitHub project page.")
