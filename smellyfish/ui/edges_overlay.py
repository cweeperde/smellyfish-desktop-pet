"""Debug aid: draws the edges Smellyfish thinks it can stand on (green = windows, yellow = desktop items)."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class EdgesOverlay(QWidget):
    def __init__(self, app):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.items = []
        self.timer = QTimer(self, timeout=self.refresh)
        self.stop = QTimer(self, singleShot=True, timeout=self.close_overlay)

    def start(self, seconds=12):
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())
        self.refresh()
        self.show()
        self.timer.start(400)
        self.stop.start(seconds * 1000)

    def close_overlay(self):
        self.timer.stop()
        self.hide()

    def refresh(self):
        self.items = []
        for s in self.app.get_surfaces(fresh=True, icons=True):
            runs, start = [], None
            x = int(s.x0)
            while x <= s.x1:
                ok = s.visible_at(x)
                if ok and start is None:
                    start = x
                if not ok and start is not None:
                    runs.append((start, x))
                    start = None
                x += 4
            if start is not None:
                runs.append((start, int(s.x1)))
            self.items.append((bool(s.icon), s.y, runs, (s.x0, s.x1)))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        origin = self.geometry().topLeft()
        for icon, y, runs, (x0, x1) in self.items:
            p.setPen(QPen(QColor(255, 255, 255, 70), 1, Qt.DotLine))
            p.drawLine(int(x0 - origin.x()), int(y - origin.y()), int(x1 - origin.x()), int(y - origin.y()))
            p.setPen(QPen(QColor(255, 210, 80) if icon else QColor(90, 255, 140), 4))
            for a, b in runs:
                p.drawLine(int(a - origin.x()), int(y - origin.y()), int(b - origin.x()), int(y - origin.y()))
        p.end()
