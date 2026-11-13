"""A tiny pixel-art input bubble next to the jellyfish: type, press Enter, the answer comes back as a speech bubble."""

import time

from PIL import Image, ImageDraw
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QFont, QPainter
from PySide6.QtWidgets import QLineEdit, QWidget

from smellyfish.art import bubble, sprite

S = 3
W, H, TAIL = 220, 50, 8
GAP = 6
FIELD = (5, 5, 214, 23)
GO = (150, 28, 180, 44)
LOG = (184, 28, 214, 44)
DOT_ON, DOT_OFF, DOT_BUSY = (90, 210, 130), (150, 146, 170), (255, 200, 70)
FIELD_BORDER = (150, 104, 200)


def lighter(c, k=40):
    return tuple(min(255, v + k) for v in c)


def button(d, box, text, fill, dark, hover=False, pressed=False, enabled=True, ink=bubble.INK):
    x0, y0, x1, y1 = box
    if not enabled:
        fill, dark, ink = (
            ((60, 52, 82), (48, 42, 66), (116, 106, 140))
            if bubble.DARK
            else ((222, 220, 232), (196, 194, 210), (168, 164, 184))
        )
    elif hover:
        fill = lighter(fill, 28)
    if pressed and enabled:
        y0 += 1
        dark = fill
    d.rectangle([x0, y0 + 1, x1, y1 - 1], fill=fill)
    d.rectangle([x0 + 1, y0, x1 - 1, y1], fill=fill)
    d.line([(x0 + 1, y1), (x1 - 1, y1)], fill=dark)
    d.line([(x0 + 1, y1 - 1), (x1 - 1, y1 - 1)], fill=dark)
    w = bubble.text_w(text)
    bubble.draw_text(d, (x0 + (x1 - x0 - w) // 2 + 1, y0 + 3), text, fill=ink)


def panel(tail, hover, pressed, focus, can_send, caption, dot):
    top = TAIL if tail == "top" else 0
    img = Image.new("RGBA", (W, H + TAIL), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([2, top + 2, W - 1, top + H - 1], fill=bubble.SHADOW)
    d.rectangle([1, top, W - 3, top + H - 2], fill=bubble.LAV_D)
    d.rectangle([0, top + 1, W - 2, top + H - 3], fill=bubble.LAV_D)
    d.rectangle([2, top + 1, W - 4, top + H - 3], fill=bubble.PAPER)
    d.rectangle([1, top + 2, W - 3, top + H - 4], fill=bubble.PAPER)

    def sh(b):
        return (b[0], b[1] + top, b[2], b[3] + top)

    f = sh(FIELD)
    border = FIELD_BORDER if focus else bubble.CODE_BG
    d.rectangle([f[0], f[1] + 1, f[2], f[3] - 1], fill=border)
    d.rectangle([f[0] + 1, f[1], f[2] - 1, f[3]], fill=border)
    d.rectangle([f[0] + 1, f[1] + 2, f[2] - 1, f[3] - 2], fill=bubble.CODE_BG)
    d.rectangle([f[0] + 2, f[1] + 1, f[2] - 2, f[3] - 1], fill=bubble.CODE_BG)
    button(d, sh(GO), "SEND", bubble.LAV, bubble.LAV_D, hover == "go", pressed == "go", can_send)
    button(d, sh(LOG), "CHAT", bubble.SEC, bubble.SEC_D, hover == "log", pressed == "log", True, bubble.TEXT)

    cy = top + 31
    d.rectangle([8, cy + 2, 10, cy + 4], fill=dot)
    d.rectangle([7, cy + 3, 11, cy + 3], fill=dot)
    bubble.draw_text(d, (16, cy), caption, fill=bubble.GREY)

    ty = top + H - 2 if tail == "bottom" else top + 1
    if tail == "bottom":
        d.polygon([(24, ty), (40, ty), (32, ty + TAIL - 1)], fill=bubble.LAV_D)
        d.polygon([(26, ty - 1), (38, ty - 1), (32, ty + TAIL - 4)], fill=bubble.PAPER)
    elif tail == "top":
        d.polygon([(24, ty), (40, ty), (32, ty - TAIL + 1)], fill=bubble.LAV_D)
        d.polygon([(26, ty + 1), (38, ty + 1), (32, ty - TAIL + 4)], fill=bubble.PAPER)
    return img


def short_model(name):
    name = (name or "").split("/")[-1]
    return name if len(name) <= 11 else name[:10] + "~"


class AskWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setMouseTracking(True)
        self.tail = "bottom"
        self.top = 0
        self.image = None
        self.key = None
        self.hover = self.pressed = None
        self.focus = False
        self.shown_at = 0.0
        self.edit = QLineEdit(self)
        self.edit.setFrame(False)
        self.edit.setMaxLength(2000)
        self.edit.setPlaceholderText("ask me anything...")
        self.edit.setFont(QFont("Cascadia Mono", 12, QFont.Bold))
        self.edit.setStyleSheet(
            "QLineEdit { background: transparent; color: #82e696; border: none; padding: 0 6px;"
            " selection-background-color: #8c60be; selection-color: #ffffff; }"
        )
        self.edit.returnPressed.connect(self.send)
        self.edit.textChanged.connect(self.restyle)
        self.edit.installEventFilter(self)
        self.closer = QTimer(self, singleShot=True, timeout=self.hide)
        self.ticker = QTimer(self, timeout=self.restyle)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(140)
        self.slide = QPropertyAnimation(self, b"pos", self)
        self.slide.setDuration(160)
        self.slide.setEasingCurve(QEasingCurve.OutBack)
        self.setFixedSize(W * S, (H + TAIL) * S)

    # ------------------------------------------------------------ drawing
    def caption(self):
        app = self.app
        name = short_model(app.cfg.get("llm_model"))
        if app.llm_phase:
            state = {"starting": "waking up", "loading": "loading", "answering": "thinking"}.get(app.llm_phase, "busy")
            return f"{name} - {state}", DOT_BUSY
        if app.llm.loaded:
            return f"{name} - ready", DOT_ON
        return f"{name} - asleep", DOT_OFF

    def restyle(self):
        from smellyfish.ui.views import to_qimage

        caption, dot = self.caption()
        if self.app.llm_phase:
            dot = DOT_BUSY if int(time.time() * 3) % 2 else (255, 230, 150)
        can = bool(self.edit.text().strip())
        key = (self.tail, self.hover, self.pressed, self.focus, can, caption, dot, bubble.DARK)
        if key == self.key:
            return
        self.key = key
        dpr = self.devicePixelRatioF() or 1.0
        dev = max(1, round(S * dpr))
        pil = panel(self.tail, self.hover, self.pressed, self.focus, can, caption, dot)
        self.image = to_qimage(pil.resize((pil.width * dev, pil.height * dev), Image.NEAREST), dev / S)
        self.top = TAIL * S if self.tail == "top" else 0
        top = self.top
        self.edit.setGeometry(
            FIELD[0] * S + 4, top + FIELD[1] * S + 4, (FIELD[2] - FIELD[0]) * S - 8, (FIELD[3] - FIELD[1]) * S - 8
        )
        self.update()

    def paintEvent(self, _):
        if self.image is not None:
            p = QPainter(self)
            p.drawImage(0, 0, self.image)
            p.end()

    # ------------------------------------------------------------ placing and showing
    def place(self):
        a = self.app
        area = a.screen_at(a.cx(), a.feet() - 4).availableGeometry()
        head = a.y + sprite.BY * a.pix
        x = round(a.cx() - 28 * S)
        above = head - self.height() - GAP
        if above >= area.top():
            self.tail = "bottom"
            y = round(above)
        else:
            self.tail = "top"
            y = round(a.feet() + GAP)
        x = max(area.left() + 4, min(x, area.right() - self.width() - 4))
        y = max(area.top() + 4, min(y, area.bottom() - self.height() - 4))
        return QPoint(x, y)

    def open(self):
        self.edit.clear()
        self.key = None
        pos = self.place()
        self.restyle()
        self.setWindowOpacity(0.0)
        self.move(pos + QPoint(0, 10 if self.tail == "bottom" else -10))
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()
        self.shown_at = time.time()
        self.fade.stop()
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.start()
        self.slide.stop()
        self.slide.setStartValue(self.pos())
        self.slide.setEndValue(pos)
        self.slide.start()
        self.ticker.start(300)

    def hideEvent(self, e):
        self.ticker.stop()
        super().hideEvent(e)

    # ------------------------------------------------------------ input
    def box(self, b):
        return QRect(b[0] * S, self.top + b[1] * S, (b[2] - b[0] + 1) * S, (b[3] - b[1] + 1) * S)

    def over(self, pos):
        if self.box(GO).contains(pos):
            return "go"
        if self.box(LOG).contains(pos):
            return "log"
        return None

    def mouseMoveEvent(self, e):
        spot = self.over(e.position().toPoint())
        if spot != self.hover:
            self.hover = spot
            self.setCursor(QCursor(Qt.PointingHandCursor if spot else Qt.ArrowCursor))
            self.restyle()

    def leaveEvent(self, e):
        self.hover = None
        self.restyle()

    def mousePressEvent(self, e):
        spot = self.over(e.position().toPoint())
        if spot:
            self.pressed = spot
            self.restyle()

    def mouseReleaseEvent(self, e):
        spot, self.pressed = self.pressed, None
        self.restyle()
        if spot and spot == self.over(e.position().toPoint()):
            if spot == "go":
                self.send()
            else:
                self.hide()
                self.app.open_chat()

    def send(self):
        text = self.edit.text().strip()
        if not text:
            return
        self.hide()
        self.app.ask_llm(text)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def eventFilter(self, obj, e):
        if obj is self.edit:
            kind = e.type()
            if kind == e.Type.KeyPress and e.key() == Qt.Key_Escape:
                self.hide()
                return True
            if kind in (e.Type.FocusIn, e.Type.FocusOut):
                self.focus = kind == e.Type.FocusIn
                self.restyle()
        return super().eventFilter(obj, e)

    def changeEvent(self, e):
        if (
            e.type() == e.Type.ActivationChange
            and not self.isActiveWindow()
            and self.isVisible()
            and time.time() - self.shown_at > 0.6
        ):
            self.closer.start(250)
        elif self.isActiveWindow():
            self.closer.stop()
        super().changeEvent(e)

    def refresh(self):
        pass
