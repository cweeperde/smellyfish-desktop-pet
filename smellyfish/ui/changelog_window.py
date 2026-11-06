"""What's new: the release notes, newest first."""
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from smellyfish import __version__
from smellyfish.art import sprite
from smellyfish.changelog import CHANGELOG, KINDS
from smellyfish.ui import theme

def tags():
    return {"new": theme.HEAD, "better": theme.GOOD, "fix": theme.WARN}


def render(entries, current):
    TAG = tags()
    out = []
    for e in entries:
        now = f" <span style='color:{theme.MUTED}'>(you are here)</span>" if e["version"] == current else ""
        out.append(f"<p style='margin:14px 0 2px 0'><span style='color:{theme.HEAD}; font-size:17px; "
                   f"font-weight:bold'>v{escape(e['version'])}</span>{now}<br>"
                   f"<span style='color:{theme.MUTED}'>{escape(e['date'])}  -  {escape(e['title'])}</span></p>")
        rows = "".join(
            f"<tr><td style='color:{TAG[k]}; padding:2px 10px 2px 0' valign='top'><b>{KINDS[k].upper()}</b></td>"
            f"<td style='padding:2px 0'>{escape(t)}</td></tr>" for k, t in e["items"])
        out.append(f"<table cellspacing='0'>{rows}</table>")
    return "".join(out)


class ChangelogWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish - What's new")
        theme.apply(self, app)
        theme.listen(lambda: self.refresh() if hasattr(self, "view") else None)
        self.resize(560, 600)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        root.addWidget(theme.banner("What's new", f"Version {__version__}",
                                    sprite.Pose(eyes="happy", blush=True, arm_f=("up_l", "up_r"),
                                                parts=[(sprite.SPARKLE, sprite.BX + 17, sprite.BY - 3)])))
        body = QVBoxLayout()
        body.setContentsMargins(14, 0, 14, 0)
        root.addLayout(body, 1)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        body.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.older = QPushButton("Show older versions")
        self.older.setObjectName("secondary")
        self.older.clicked.connect(self.show_all)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(self.older)
        row.addStretch(1)
        row.addWidget(close)
        body.addLayout(row)
        self.entries = CHANGELOG[:1]

    def show_since(self, old):
        """Only what is new since the version the user had before; everything when unknown."""
        from smellyfish.changelog import since
        self.entries = since(old, __version__) or CHANGELOG[:1]
        self.refresh()

    def show_all(self):
        self.entries = CHANGELOG
        self.refresh()

    def refresh(self):
        self.view.setHtml(render(self.entries, __version__))
        self.older.setVisible(len(self.entries) < len(CHANGELOG))
