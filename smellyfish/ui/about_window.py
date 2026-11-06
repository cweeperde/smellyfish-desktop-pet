"""About window: who made Smellyfish, where to find it and who helped."""
import json
import os
import threading
import urllib.parse
import urllib.request

from PIL import Image

from PySide6.QtCore import QObject, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPainter, QPainterPath, QPen, QPixmap, QColor
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from smellyfish import REPO, __version__
from smellyfish.art import sprite
from smellyfish.paths import APP_DIR, BUNDLE_DIR
from smellyfish.ui import theme

CREATOR = "cweeper"
OWNER = REPO.split("/")[0]
PROFILE = f"https://github.com/{OWNER}"
PROJECT = f"https://github.com/{REPO}"
AVATAR_HOST = "avatars.githubusercontent.com"
AVATAR = 52
_cache = {"people": None}


class _Loader(QObject):
    done = Signal(list, str)


def fetch_people():
    """Contributors with profile pictures: one request to api.github.com and one per picture to
    avatars.githubusercontent.com. Nothing is written to disk."""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/contributors?per_page=50",
                                 headers={"User-Agent": "Smellyfish desktop pet", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read(500_000))
    people = []
    for c in data:
        login = str(c.get("login") or "")
        if not login or c.get("type") == "Bot":
            continue
        pic = None
        url = str(c.get("avatar_url") or "")
        parts = urllib.parse.urlsplit(url)
        if parts.scheme == "https" and parts.hostname == AVATAR_HOST:
            try:
                sized = url + ("&" if "?" in url else "?") + "s=104"
                with urllib.request.urlopen(urllib.request.Request(sized, headers={"User-Agent": "Smellyfish desktop pet"}),
                                            timeout=10) as r:
                    pic = r.read(1_000_000)
            except OSError:
                pic = None
        people.append({"login": login, "commits": int(c.get("contributions") or 0), "pic": pic})
    people.sort(key=lambda p: (p["login"].lower() != OWNER.lower(), -p["commits"]))
    return people


def default_avatar():
    img = sprite.render(sprite.Pose(eyes="happy", blush=True), 1)
    img = img.crop(img.getbbox())
    side = max(img.size) + 6
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
    sq = sq.resize((side * 4, side * 4), Image.NEAREST)
    qi = QImage(sq.tobytes(), sq.width, sq.height, sq.width * 4, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(qi)


def round_avatar(source, ring, fill):
    """Circular picture with a lavender ring, rendered at 2x for sharp edges."""
    size = AVATAR * 2
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    ring_w = 6
    circle = QPainterPath()
    circle.addEllipse(QRectF(ring_w / 2, ring_w / 2, size - ring_w, size - ring_w))
    p.fillPath(circle, QColor(fill))
    if not source.isNull():
        p.setClipPath(circle)
        scaled = source.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        p.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
        p.setClipping(False)
    p.setPen(QPen(QColor(ring), ring_w))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(ring_w / 2, ring_w / 2, size - ring_w, size - ring_w))
    p.end()
    out.setDevicePixelRatio(2)
    return out


class PersonCard(QFrame):
    def __init__(self, person, pixmap):
        super().__init__()
        self.url = f"https://github.com/{person['login']}"
        self.setObjectName("person")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self.url)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 12, 8)
        row.setSpacing(12)
        pic = QLabel()
        pic.setFixedSize(AVATAR, AVATAR)
        pic.setPixmap(round_avatar(pixmap, theme.LAV, theme.FIELD))
        row.addWidget(pic)
        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel(person["login"])
        name.setStyleSheet(f"color: {theme.HEAD}; font-size: 14px; font-weight: bold;")
        sub = QLabel("Creator" if person["login"].lower() == OWNER.lower() else
                     f"{person['commits']} commit{'s' if person['commits'] != 1 else ''}")
        sub.setObjectName("hint")
        col.addStretch(1)
        col.addWidget(name)
        col.addWidget(sub)
        col.addStretch(1)
        row.addLayout(col, 1)
        self.setStyleSheet(f"QFrame#person {{ background: {theme.PANEL}; border: 3px solid {theme.DEEP}; "
                           f"border-top-color: {theme.LAV}; border-left-color: {theme.LAV}; }}"
                           f"QFrame#person:hover {{ background: {theme.SEC_HOVER}; }}")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(self.url))


def notices_text():
    parts = []
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.txt"):
        for base in (BUNDLE_DIR, os.path.dirname(APP_DIR), APP_DIR):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                with open(path, encoding="utf-8", errors="replace") as f:
                    parts.append(f.read())
                break
    return "\n\n".join(parts) or f"The license texts are in the project on GitHub:\n{PROJECT}"


class LicenseWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.setWindowTitle("Smellyfish - licenses")
        theme.apply(self, app)
        self.resize(640, 560)
        root = QVBoxLayout(self)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.NoWrap)
        view.setPlainText(notices_text())
        root.addWidget(view)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        root.addWidget(close, 0, Qt.AlignRight)


class AboutWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.license_win = None
        self.setWindowTitle("About Smellyfish")
        theme.apply(self, app)
        self.resize(460, 640)
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

        title = QLabel("Made with help from")
        title.setObjectName("title")
        body.addWidget(title)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        body.addWidget(self.scroll, 1)
        self.note = QLabel("")
        self.note.setObjectName("hint")
        self.note.setWordWrap(True)
        body.addWidget(self.note)

        legal = QLabel("Copyright (c) 2026 cweeper. All rights reserved. Pull requests are welcome, see the license "
                       "for how contributions work. Not affiliated with Anthropic, OpenAI or Discord.")
        legal.setObjectName("hint")
        legal.setWordWrap(True)
        body.addWidget(legal)

        row = QHBoxLayout()
        row.setContentsMargins(16, 0, 16, 0)
        for text, fn in (("GitHub", lambda: QDesktopServices.openUrl(QUrl(PROJECT))),
                         ("Licenses", self.show_licenses),
                         ("Updates", lambda: app.updater.check(manual=True))):
            b = QPushButton(text)
            b.setObjectName("secondary")
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(close)
        root.addLayout(row)

        self.default_pic = default_avatar()
        self.loader = _Loader()
        self.loader.done.connect(self.show_people)
        self.loading = False
        self.people = None
        theme.listen(self.rebuild)

    def show_licenses(self):
        if self.license_win is None:
            self.license_win = LicenseWindow(self.app)
        self.license_win.show()
        self.license_win.raise_()

    def refresh(self):
        if _cache["people"] is not None:
            return self.show_people(_cache["people"], "")
        if self.loading:
            return
        self.loading = True
        self.note.setText("Asking GitHub who helped (names and profile pictures)...")
        self.people = [{"login": OWNER, "commits": 0, "pic": None}]
        self.rebuild()

        def work():
            try:
                self.loader.done.emit(fetch_people(), "")
            except (OSError, ValueError) as e:
                self.loader.done.emit([], f"Could not load the list ({e.__class__.__name__}). Are you offline?")

        threading.Thread(target=work, daemon=True).start()

    def show_people(self, people, error):
        self.loading = False
        if error:
            self.note.setText(error)
            return
        _cache["people"] = people
        self.people = people or [{"login": OWNER, "commits": 0, "pic": None}]
        self.note.setText("Opening this window asks GitHub for the contributor list (api.github.com) and the "
                          "profile pictures (avatars.githubusercontent.com). GitHub sees your IP address like on any "
                          "website. Nothing else is sent and nothing is saved.")
        self.rebuild()

    def rebuild(self):
        if self.people is None:
            return
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(8)
        for person in self.people:
            pix = QPixmap()
            if person.get("pic"):
                pix.loadFromData(person["pic"])
            col.addWidget(PersonCard(person, pix if not pix.isNull() else self.default_pic))
        col.addStretch(1)
        self.scroll.setWidget(holder)
