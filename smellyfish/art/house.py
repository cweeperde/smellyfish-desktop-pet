"""The pet's home: arc floor lamp, bed, potted plant and a signpost, drawn at the home position."""

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QToolTip, QWidget

from smellyfish.art import sprite

LAMP_ON = [
    "...gggggg..",
    "..g......g.",
    ".g.....GGG.",
    ".g....GyyyG",
    ".g...GYYYYG",
    ".g...oooooo",
    ".g....y.y.y",
    ".g...y.y.y.",
    ".g.........",
    ".g.........",
    ".g.........",
    ".gh........",
    "GGGGGG.....",
    "GGGGGGGG...",
]
LAMP_OFF = [r.replace("Y", "w").replace("o", "h").replace("y", ".") for r in LAMP_ON]
BED = [
    "qWWWpPpPpPpPpPpPpq",
    "qqqqqqqqqqqqqqqqqq",
    ".q..............q.",
]
PLANT_OK = [
    "..c.c..",
    ".cc.cc.",
    "..cvc..",
    "...v...",
    "TTTTTTT",
    ".TtttT.",
    ".TTTTT.",
    "..TTT..",
]
SIGN_ON = [
    "....Y....",
    "yyyyyy...",
    "bbbbbbb..",
    "bbbbbbbb.",
    "qqqqqqq..",
    "....q....",
    "..yyyyyyy",
    "bbbbbbbbb",
    "..qqqqqqq",
    "....q....",
    "....q....",
    "..qqqqq..",
]
SIGN_OFF = [
    "..RRRRR..",
    ".RRRRRRR.",
    "RRRRRRRRR",
    "RWWWWWWWR",
    "RWWWWWWWR",
    "RRRRRRRRR",
    ".ZZZZZZZ.",
    "..ZZZZZ..",
    "....q....",
    "....q....",
    "....q....",
    "..qqqqq..",
]
BED_H = 3  # the pet sits on the mattress, this many pixels above the floor

# left edge and width (1x pixels) of each prop relative to the home centre; ground is y = 0
LAYOUT = {"lamp": (-21, 11), "bed": (-9, 18), "plant": (15, 7), "sign": (24, 9)}
LEFT, WIDTH, HEIGHT = -21, 54, 14
PLANT_CENTER = 18
WATER_SPOT = PLANT_CENTER - 11


def compose(lamp_on, wander_on):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    def put(rows, x0):
        top = HEIGHT - len(rows)
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                if c != ".":
                    img.putpixel((x0 - LEFT + x, top + y), sprite.PAL[c] + (255,))

    put(LAMP_ON if lamp_on else LAMP_OFF, LAYOUT["lamp"][0])
    put(BED, LAYOUT["bed"][0])
    put(PLANT_OK, LAYOUT["plant"][0])
    put(SIGN_ON if wander_on else SIGN_OFF, LAYOUT["sign"][0])
    return img


def hit(x1, y1):
    """Which prop is at 1x (x, y) inside the house image. The bed area is generous."""
    rel = x1 + LEFT
    for name, (x0, w) in LAYOUT.items():
        if x0 <= rel < x0 + w:
            return name
    return None


TIPS = {
    "lamp": "Lamp: on/off (off = do not disturb)",
    "plant": "Plant: water it",
    "sign": "Signpost: wandering on/off",
    "bed": "Bed: call Smellyfish home",
}


class HouseView(QWidget):
    def __init__(self, app):
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.image = None

    def refresh(self):
        from smellyfish.ui.views import alpha_region, to_qimage

        pix = self.app.pix
        pil = compose(not self.app.cfg["dnd"], self.app.cfg["wander"])
        dpr = self.devicePixelRatioF() or 1.0
        dev = max(1, round(pix * dpr))
        self.image = to_qimage(pil.resize((WIDTH * dev, HEIGHT * dev), Image.NEAREST), dev / pix)
        self.setFixedSize(WIDTH * pix, HEIGHT * pix)
        mask = pil.copy()
        bx0 = LAYOUT["bed"][0] - LEFT
        for x in range(bx0, bx0 + LAYOUT["bed"][1]):
            for y in range(HEIGHT - 10, HEIGHT):
                if mask.getpixel((x, y))[3] == 0:
                    mask.putpixel((x, y), (0, 0, 0, 1))
        self.setMask(alpha_region(mask.resize((WIDTH * pix, HEIGHT * pix), Image.NEAREST)))
        hx, hy = self.app.home_ground()
        self.move(round(hx + LEFT * pix), round(hy - HEIGHT * pix))
        self.update()

    def paintEvent(self, _):
        if self.image is not None:
            p = QPainter(self)
            p.drawImage(0, 0, self.image)
            p.end()

    def prop_at(self, pos):
        return hit(int(pos.x() // self.app.pix), int(pos.y() // self.app.pix))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            name = self.prop_at(e.position().toPoint())
            if name:
                self.app.house_click(name)
        elif e.button() == Qt.RightButton:
            self.app.menu.exec(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        name = self.prop_at(e.position().toPoint())
        if name:
            QToolTip.showText(e.globalPosition().toPoint() + QPoint(12, 12), TIPS[name], self)
