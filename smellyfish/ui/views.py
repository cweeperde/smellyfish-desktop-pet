"""The frameless pixel windows: the pet itself, its badge and its speech bubble."""

import sys

from PIL import Image
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QBitmap, QCursor, QImage, QPainter, QRegion
from PySide6.QtWidgets import QWidget

from smellyfish.art import bubble, sprite
from smellyfish.art.badge import badge_image

FEET = sprite.FEET
BODY_X0, BODY_X1 = sprite.BX + 1, sprite.BX + 15
CENTER_X = sprite.BX + 8


def to_qimage(pil, dpr):
    pil = pil.convert("RGBA")
    img = QImage(pil.tobytes(), pil.width, pil.height, pil.width * 4, QImage.Format_RGBA8888).copy()
    img.setDevicePixelRatio(dpr)
    return img


def alpha_region(pil):
    a = pil.getchannel("A")
    img = QImage(a.tobytes(), a.width, a.height, a.width, QImage.Format_Alpha8).copy()
    return QRegion(QBitmap.fromImage(img.createAlphaMask()))


FLAGS = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus


class PixelWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, FLAGS | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        if sys.platform == "darwin":
            # tool windows would otherwise hide whenever another app is active
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.image = None

    def paintEvent(self, _):
        if self.image is not None:
            p = QPainter(self)
            p.drawImage(0, 0, self.image)
            p.end()


class PetView(PixelWindow):
    def set_frame(self, image, region):
        self.image = image
        self.setMask(region)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.app.menu.exec(QCursor.pos())
        elif e.button() == Qt.LeftButton:
            self.app.grab(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        self.app.drag(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.app.drop()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.app.grab(e.globalPosition().toPoint())

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32" and self.app.counter.handle(message):
            return False, 0
        action = self.app.hotkeys.action_for(message) if sys.platform == "win32" else None
        if action:
            self.app.on_hotkey(action)
            return True, 0
        return False, 0


class BadgeView(PixelWindow):
    """Little pills above the pet: running agents, missed things, focus timer."""

    def show_items(self, items):
        if items == getattr(self, "_items", None) and (self.isVisible() or not items):
            return self.place()
        self._items = items
        pil = badge_image(items)
        if pil is None or self.app.hidden_for_game() or not self.app.view.isVisible():
            self.hide()
            return
        pix = max(2, self.app.pix // 2 + 1)
        dpr = self.devicePixelRatioF() or 1.0
        dev = max(1, round(pix * dpr))
        self.image = to_qimage(pil.resize((pil.width * dev, pil.height * dev), Image.NEAREST), dev / pix)
        self.setFixedSize(pil.width * pix, pil.height * pix)
        self.setMask(alpha_region(pil.resize((pil.width * pix, pil.height * pix), Image.NEAREST)))
        self.spans = [(a * pix, b * pix, icon) for a, b, icon in getattr(pil, "spans", [])]
        self.place()
        self.show()
        self.update()

    def place(self):
        a = self.app
        area = a.screen_at(a.cx(), a.feet() - 4).availableGeometry()
        w, h = self.width(), self.height()
        bub = a.bubble
        if bub.isVisible() and bub.spec is not None and bub.tail == "bottom":
            x = bub.x() + (8 if bub.lean > 0 else bub.width() - w - 8)
            y = bub.y() - h - 2
            if y < area.top() + 2:
                body_r, body_l = round(a.x + BODY_X1 * a.pix), round(a.x + BODY_X0 * a.pix)
                x = body_r + 4 if bub.lean < 0 or body_l - w - 4 < area.left() else body_l - w - 4
                y = round(a.y + sprite.BY * a.pix)
        else:
            x = round(a.x + (sprite.BX + 5) * a.pix - w)
            if x < area.left() + 2:
                x = round(a.x + (sprite.BX + 11) * a.pix)
            y = round(a.y + (sprite.BY - 4) * a.pix - h)
        x = max(area.left() + 2, min(x, area.right() - w - 1))
        y = max(area.top() + 2, min(y, area.bottom() - h))
        self.move(x, y)

    def mousePressEvent(self, e):
        x = e.position().x()
        icon = next((icon for a, b, icon in getattr(self, "spans", []) if a <= x < b), None)
        if icon == "note":
            return self.app.open_media()
        if icon == "cal":
            return self.app.open_calendar()
        if icon == "session":
            return self.app.open_sessions()
        self.app.open_history()


class BubbleView(PixelWindow):
    TIP = 18

    def __init__(self, app):
        super().__init__(app)
        self.hits, self.spec, self.tail, self.lean, self.key = [], None, None, -1, None
        self.pressed = None

    def set_spec(self, spec):
        self.spec = spec
        self.key = None
        if spec is None or self.app.hidden_for_game():
            self.hide()
            self.app.badge.place()
            return
        self.place()

    def place(self):
        if self.spec is None or self.app.hanging or self.app.hidden_for_game():
            return
        app, pix, u = self.app, self.app.pix, bubble.UNIT
        px, py = app.x, app.y
        screen = app.screen_at(px + CENTER_X * pix, py + FEET * pix)
        area = screen.availableGeometry()
        unit = max(1, round(u * screen.devicePixelRatio()))
        skey = (id(self.spec), self.spec.get("expanded"))
        if getattr(self, "_size", (None,))[0] != skey:
            self._size = (skey, bubble.size(self.spec))
        bw, bh = self._size[1]
        w, h = (bw + 2) * u, (bh + bubble.TAIL_H + 2) * u
        head_y = round(py + (sprite.BY - 1) * pix)
        feet_y = round(py + (FEET + 1) * pix)
        badge = app.badge.height() + 2 if app.badge.isVisible() else 0
        if head_y - h - badge >= area.top() or (head_y - h >= area.top() and feet_y + h > area.bottom()):
            tail = "bottom"
        elif feet_y + h <= area.bottom() + 1:
            tail = "top"
        else:
            tail = "bottom" if head_y - area.top() >= area.bottom() - feet_y else "top"
        centre = round(px + CENTER_X * pix)
        grow_right = centre < (area.left() + area.right()) / 2
        x = centre - self.TIP * u if grow_right else centre + self.TIP * u - w
        x = max(area.left(), min(x, area.right() + 1 - w))
        y = head_y - h if tail == "bottom" else feet_y
        y = max(area.top(), min(y, area.bottom() + 1 - h))
        tip = round((centre - x) / u)
        key = (id(self.spec), self.spec.get("expanded"), tail, tip, unit, bubble.DARK, str(self.pressed))
        if key != self.key or self.image is None:
            pil, hits = bubble.render(self.spec, unit, tail, tip, self.pressed)
            self.bars = [(round(a * u / unit), round(b * u / unit), v) for a, b, v in bubble.render.bars]
            k = u / unit
            self.key, self.tail = key, tail
            self.lean = -1 if tip < bw / 2 else 1
            self.image = to_qimage(pil, unit / u)
            self.hits = [
                (QRect(round(x0 * k), round(y0 * k), round((x1 - x0) * k), round((y1 - y0) * k)), v)
                for x0, y0, x1, y1, v in hits
            ]
            self.setFixedSize(round(pil.width * k), round(pil.height * k))
        self.move(x, y)
        if not self.isVisible():
            self.show()
        self.update()
        if app.badge.isVisible():
            app.badge.place()

    def hit_at(self, pos):
        return next(((rect, value) for rect, value in self.hits if rect.contains(pos)), None)

    def bar_frac(self, x, value):
        bar = next(((a, b) for a, b, v in getattr(self, "bars", []) if v == value), None)
        return None if bar is None or bar[1] <= bar[0] else (x - bar[0]) / (bar[1] - bar[0])

    def mouseMoveEvent(self, e):
        if self.pressed == ("media_seek",):
            frac = self.bar_frac(e.position().x(), self.pressed)
            if frac is not None:
                self.app.media_seek(frac, done=False)

    def mousePressEvent(self, e):
        hit = self.hit_at(e.position().toPoint())
        if hit is not None and hit[1] == ("media_seek",):
            self.pressed = hit[1]
            return self.mouseMoveEvent(e)
        if hit is None:
            if self.spec and self.spec.get("kind") == "discord" and self.spec.get("chip") == "Discord":
                self.app.click_value("open_discord")
            return
        self.pressed = hit[1]
        self.place()

    def mouseReleaseEvent(self, e):
        value, self.pressed = self.pressed, None
        if value is None:
            return
        if value == ("media_seek",):
            frac = self.bar_frac(e.position().x(), value)
            self.app.media_seek(frac if frac is not None else 0.0, done=True)
            return
        hit = self.hit_at(e.position().toPoint())
        self.place()
        if hit is not None and hit[1] == value:
            QTimer.singleShot(40, lambda: self.app.click_value(value))
