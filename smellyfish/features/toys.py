"""Little physics toys: a ball to throw and fetch, and fish snacks."""

import time

from PIL import Image
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor, QPainter
from PySide6.QtWidgets import QWidget

from smellyfish.art import sprite

GRAVITY = 2600.0
SPRITES = {"ball": sprite.BALL, "snack": sprite.FISH}


class Toy(QWidget):
    def __init__(self, app, kind, x, y, vx=0.0, vy=0.0):
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.app, self.kind = app, kind
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        rows = SPRITES[kind]
        self.w1, self.h1 = len(rows[0]), len(rows)
        img = Image.new("RGBA", (self.w1, self.h1), (0, 0, 0, 0))
        for yy, row in enumerate(rows):
            for xx, c in enumerate(row):
                if c != ".":
                    img.putpixel((xx, yy), sprite.PAL[c] + (255,))
        self.pil = img
        self.x, self.y, self.vx, self.vy = float(x), float(y), vx, vy
        self.resting = False
        self.support = None
        self.grab_off = None
        self.hist = []
        self.born = time.time()
        self.refresh()
        self.timer = QTimer(self, timeout=self.step)
        self.timer.start(16)
        self.show()

    def refresh(self):
        from smellyfish.ui.views import alpha_region, to_qimage

        pix = self.app.pix
        dpr = self.devicePixelRatioF() or 1.0
        dev = max(1, round(pix * dpr))
        self.image = to_qimage(self.pil.resize((self.w1 * dev, self.h1 * dev), Image.NEAREST), dev / pix)
        self.setFixedSize(self.w1 * pix, self.h1 * pix)
        self.setMask(alpha_region(self.pil.resize((self.w1 * pix, self.h1 * pix), Image.NEAREST)))
        self.move(round(self.x), round(self.y))

    def center(self):
        return self.x + self.width() / 2, self.y + self.height()

    def area(self):
        cx = self.x + self.width() / 2
        return self.app.screen_at(cx, self.y + self.height() - 4).availableGeometry()

    def step(self):
        if self.grab_off is not None:
            return
        if self.resting:
            if self.support is not None:
                self._check_support()
            return
        dt = 0.016
        prev_bottom = self.y + self.height()
        self.vy = min(self.vy + GRAVITY * dt, 3000)
        self.x += self.vx * dt
        self.y += self.vy * dt
        vg = self.app.bounds()
        if self.x < vg.left():
            self.x, self.vx = vg.left(), abs(self.vx) * 0.6
        if self.x + self.width() > vg.right():
            self.x, self.vx = vg.right() - self.width(), -abs(self.vx) * 0.6
        a = self.area()
        floor = a.bottom() + 1
        if self.y < a.top():
            self.y, self.vy = a.top(), abs(self.vy) * 0.5
        landing, support = floor, None
        if self.vy > 0 and self.app.cfg["sit_on_windows"]:
            cx = self.x + self.width() / 2
            for s in self.app.get_surfaces():
                if prev_bottom - 1 <= s.y <= self.y + self.height() + 1 and s.visible_at(cx) and s.y < landing:
                    landing, support = s.y, s.hwnd
        if self.y + self.height() >= landing:
            self.y = landing - self.height()
            self.support = support
            bounce = 0.55 if self.kind == "ball" else 0.2
            if self.vy > 180:
                self.vy = -self.vy * bounce
            else:
                self.vy = 0
            self.vx *= 0.8
            if abs(self.vx) < 15 and self.vy == 0:
                self.vx = 0
                self.resting = True
                self.app.toy_rested(self)
        self.move(round(self.x), round(self.y))

    def throw(self, vx, vy):
        self.vx, self.vy = vx, vy
        self.resting = False
        self.support = None

    def _check_support(self):
        from smellyfish.system import surfaces

        now = time.time()
        if now - getattr(self, "_checked", 0) < 0.3:
            return
        self._checked = now
        top = surfaces.window_top(self.support)
        cx = self.x + self.width() / 2
        if top is None or not top[0] <= cx <= top[1]:
            return self.throw(0, 0)
        if abs(top[2] - (self.y + self.height())) > 1:
            self.y = top[2] - self.height()
            self.move(round(self.x), round(self.y))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.grab_off = e.globalPosition().toPoint() - QPoint(round(self.x), round(self.y))
            self.hist = [(time.time(), e.globalPosition().toPoint())]
            self.resting = False

    def mouseMoveEvent(self, e):
        if self.grab_off is None:
            return
        p = e.globalPosition().toPoint()
        self.x, self.y = p.x() - self.grab_off.x(), p.y() - self.grab_off.y()
        now = time.time()
        self.hist = [h for h in self.hist if now - h[0] < 0.12] + [(now, p)]
        self.move(round(self.x), round(self.y))

    def mouseReleaseEvent(self, e):
        if self.grab_off is None:
            return
        self.grab_off = None
        if len(self.hist) >= 2:
            (t0, p0), (t1, p1) = self.hist[0], self.hist[-1]
            dt = max(t1 - t0, 1e-3)
            self.throw(max(-2400, min(2400, (p1.x() - p0.x()) / dt)), max(-2400, min(2400, (p1.y() - p0.y()) / dt)))
        else:
            self.throw(0, 0)
        self.app.toy_thrown(self)

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawImage(0, 0, self.image)
        p.end()

    def remove(self):
        self.timer.stop()
        self.hide()
        self.deleteLater()


def spawn_near_cursor(app, kind):
    c = QCursor.pos()
    return Toy(app, kind, c.x() - 3 * app.pix, c.y() - 3 * app.pix, 0, -300)
