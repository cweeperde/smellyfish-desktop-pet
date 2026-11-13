"""A friend's jellyfish steps out of a door, maybe hands over a letter and goes back in."""

import math
import random

from PIL import Image, ImageDraw
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from smellyfish.art import house as house_mod
from smellyfish.art import sprite

CENTER_X = sprite.BX + 8
DOOR_W, DOOR_H = 12, 17
FRAME_W = 12
STAY_MS = (7000, 11000)
PAL = sprite.PAL
WARM = [(255, 226, 150), (255, 210, 110), (240, 170, 80)]


def door_image(openness=0.0, glow=False):
    """The door as a 12x17 pixel image. openness 0 = shut, 1 = wide open."""
    img = Image.new("RGBA", (DOOR_W, DOOR_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    frame, wood, panel, knob = PAL["q"], PAL["b"], PAL["T"], PAL["Y"]
    d.rectangle([1, 0, FRAME_W - 2, 0], fill=frame)
    d.rectangle([0, 1, FRAME_W - 1, DOOR_H - 1], fill=frame)
    d.rectangle([2, 1, FRAME_W - 3, DOOR_H - 2], fill=PAL["n"])
    if openness > 0.05 or glow:
        for i, y in enumerate(range(DOOR_H - 2, 1, -1)):
            shade = WARM[min(2, i // 5)] if openness > 0.3 else WARM[2]
            d.line([(2, y), (FRAME_W - 3, y)], fill=shade if openness > 0.05 else PAL["n"])
    leaf = round((FRAME_W - 4) * (1 - openness))
    if leaf > 0:
        d.rectangle([2, 1, 1 + leaf, DOOR_H - 2], fill=wood)
        if leaf >= 4:
            d.rectangle([3, 3, max(3, leaf - 1), 6], fill=panel)
            d.rectangle([3, 9, max(3, leaf - 1), 13], fill=panel)
            d.point((leaf - 1, 8), fill=knob)
        d.line([(1 + leaf, 1), (1 + leaf, DOOR_H - 2)], fill=PAL["q"])
    return img


class Sprite(QWidget):
    """A frameless transparent window that shows one pixel image (and optionally a name above it)."""

    def __init__(self, app):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.image = None
        self.label = None
        self.ox = self.top = 0
        self.lw, self.lh, self.label_cx, self.label_y = 0, 16, 0, 0
        self.font = QFont("Cascadia Mono", 9, QFont.Bold)

    def set_pil(self, pil, label=None):
        from smellyfish.ui.views import to_qimage

        pix = self.app.pix
        dpr = self.devicePixelRatioF() or 1.0
        dev = max(1, round(pix * dpr))
        self.image = to_qimage(pil.resize((pil.width * dev, pil.height * dev), Image.NEAREST), dev / pix)
        self.label = label
        w, h = pil.width * pix, pil.height * pix
        self.ox = self.top = 0
        if label:
            fm = QFontMetrics(self.font)
            self.lw, self.lh = fm.horizontalAdvance(label) + 10, 16
            centre = CENTER_X * pix
            top_row = (pil.getbbox() or (0, 0, 0, 0))[1]
            self.top = max(0, self.lh + 4 - top_row * pix)
            self.ox = max(0, int(self.lw / 2 - centre))
            right = max(0, int(self.lw / 2 - (w - centre)))
            self.label_cx = self.ox + centre
            self.label_y = self.top + top_row * pix - self.lh - 2
            w = self.ox + w + right
        self.setFixedSize(int(w), int(h + self.top))
        self.update()

    def paintEvent(self, _):
        if self.image is None:
            return
        p = QPainter(self)
        p.drawImage(self.ox, self.top, self.image)
        if self.label:
            p.setFont(self.font)
            box = QRect(int(self.label_cx - self.lw / 2), int(self.label_y), int(self.lw), self.lh)
            p.setPen(QColor("#221634"))
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                p.drawText(box.translated(dx, dy), Qt.AlignHCenter | Qt.AlignVCenter, self.label)
            p.setPen(QColor("#e2c0fa"))
            p.drawText(box, Qt.AlignHCenter | Qt.AlignVCenter, self.label)
        p.end()


def skin_pal(color):
    c = color.lstrip("#")
    return sprite.skin_from_color(tuple(int(c[i : i + 2], 16) for i in (0, 2, 4)))


def dressed(pose, look):
    """The guest's own outfit, weather clothes and gear on a pose."""
    look = look or {}
    if look.get("h") or look.get("b"):
        pose = sprite.with_gear(pose, look.get("h"), bool(look.get("b")))
    pose = sprite.with_outfit(pose, look.get("o"))
    return sprite.with_weather(pose, look.get("w"))


class Visit:
    """One visit as a small script: door rattles and swings open, the guest hops out, does its thing, hops back in."""

    def __init__(self, app, name, color, letter=None, look=None, on_done=None):
        self.app, self.name, self.color, self.letter, self.look = app, name, color, letter, look
        self.on_done = on_done
        self.door = Sprite(app)
        self.body = Sprite(app)
        self.pal = skin_pal(color)
        self.pose = sprite.Pose(eyes="happy")
        self.cx = 0.0
        self.lift = 0.0
        self.handed = False
        self.door_dx = 0
        self.screen = None
        self.side = 1
        self.script = self.run()
        self.timer = QTimer(singleShot=True, timeout=self.advance)
        self.alive = True

    # -------------------------------------------------------- placing
    def ground(self):
        return self.app.home_ground()

    def place_door(self):
        """The door goes on whichever side of the house has more room and always stays fully on screen."""
        pix = self.app.pix
        hx, hy = self.ground()
        from PySide6.QtCore import QPoint

        screen = QGuiApplication.screenAt(QPoint(round(hx), round(hy) - 4)) or QGuiApplication.primaryScreen()
        self.screen = screen.availableGeometry()
        right = hx + (house_mod.LEFT + house_mod.WIDTH + 3) * pix
        left = hx + (house_mod.LEFT - DOOR_W - 3) * pix
        room_r = self.screen.right() - (right + DOOR_W * pix)
        room_l = left - self.screen.left()
        self.side = 1 if room_r >= room_l else -1
        x = right if self.side == 1 else left
        self.door_left = max(self.screen.left() + 6, min(x, self.screen.right() - DOOR_W * pix - 6))

    def door_cx(self):
        return self.door_left + FRAME_W * self.app.pix / 2

    def draw_door(self, openness=0.0, glow=False):
        pix = self.app.pix
        self.door.set_pil(door_image(openness, glow))
        _hx, hy = self.ground()
        self.door.move(round(self.door_left + self.door_dx * pix), round(hy - DOOR_H * pix))
        self.door.show()

    def clamp(self, x):
        m = 20 * self.app.pix
        return max(self.screen.left() + m, min(self.screen.right() - m, x))

    def draw_guest(self, parts=()):
        pix = self.app.pix
        pose = dressed(self.pose, self.look)
        body = sprite.render(pose.but(parts=list(pose.parts) + list(parts)), 1, pal=self.pal)
        self.body.set_pil(body, self.name)
        _hx, hy = self.ground()
        self.body.move(
            round(self.cx - CENTER_X * pix - self.body.ox), round(hy - sprite.FEET * pix - self.body.top + self.lift)
        )
        self.body.show()
        self.body.raise_()

    # -------------------------------------------------------- script helpers
    def start(self):
        self.advance()

    def advance(self):
        if not self.alive:
            return
        try:
            delay = next(self.script)
        except StopIteration:
            return self.finish()
        self.timer.start(max(10, int(delay)))

    def finish(self):
        self.alive = False
        self.timer.stop()
        self.door.hide()
        self.body.hide()
        self.door.deleteLater()
        self.body.deleteLater()
        if self.on_done:
            self.on_done(self)

    def cancel(self):
        self.finish()

    def carry(self):
        return [(sprite.ENVELOPE, sprite.BX + 16, sprite.BY - 1)] if self.letter and not self.handed else []

    def stand(self, pose, ms):
        self.pose = pose
        self.draw_guest(self.carry())
        return ms

    def swing(self, opening):
        """The door swings open (or shut) over a few frames, with a little ease."""
        steps = (0.15, 0.4, 0.7, 0.9, 1.0) if opening else (0.85, 0.55, 0.25, 0.08, 0.0)
        for v in steps:
            self.draw_door(v, glow=True)
            yield 70

    def rattle(self):
        self.app.sfx("doorbell")
        for dx in (-1, 1, -1, 1, 0):
            self.door_dx = dx
            self.draw_door(0.0)
            yield 55
        yield 250

    def hop(self, target, speed=190):
        """Hops along the ground to target x; yields the delays."""
        pix = self.app.pix
        while abs(target - self.cx) > 2:
            step = max(-speed, min(speed, target - self.cx))
            x0, x1 = self.cx, self.cx + step
            n = 8
            for i in range(1, n + 1):
                t = i / n
                self.cx = x0 + (x1 - x0) * t
                self.lift = 0.0 if i == n else -math.sin(math.pi * t) * 7 * pix
                self.pose = sprite.Pose(eyes="happy", tent="tuck" if t < 0.8 else "spread")
                self.draw_guest(self.carry())
                yield 45
            self.pose = sprite.Pose(eyes="happy", squash=True, tent="spread")
            self.draw_guest(self.carry())
            yield 110

    def pet_spot(self):
        """Next to the pet when it is on the ground near its home, otherwise a bit away from the door."""
        app, pix = self.app, self.app.pix
        _hx, hy = self.ground()
        if abs(app.feet() - hy) < 14 * pix and app.phys == "rest":
            return self.clamp(app.cx() + (20 * pix if self.door_cx() >= app.cx() else -20 * pix))
        return self.clamp(self.door_cx() - self.side * 34 * pix)

    # -------------------------------------------------------- the script
    def run(self):
        app = self.app
        self.place_door()
        self.cx = self.door_cx()
        self.body.hide()
        self.draw_door(0.0)
        yield 500
        yield from self.rattle()
        yield from self.swing(True)
        self.pose = sprite.Pose(eyes="wide", tent="spread")
        self.draw_guest(self.carry())
        yield 260
        yield from self.hop(self.pet_spot())
        yield from self.swing(False)
        self.door_dx = 0
        self.draw_door(0.0)
        for pose in (
            sprite.Pose(eyes="happy", arm_f=("rest_l", "up_r")),
            sprite.Pose(eyes="happy", arm_f=("rest_l", "wave_r")),
            sprite.Pose(eyes="happy", arm_f=("rest_l", "up_r")),
        ):
            yield self.stand(pose, 260)
        if self.letter:
            for lift in (0, 1, 2):
                self.pose = sprite.Pose(eyes="happy", arm_f=("up_l", "up_r"), dy=-lift // 2)
                self.draw_guest([(sprite.ENVELOPE, sprite.BX + 16, sprite.BY - 2 - lift)])
                yield 160
            self.handed = True
            if app.on_letter_delivered:
                app.on_letter_delivered(self.name, self.letter)
            yield self.stand(sprite.Pose(eyes="happy", blush=True), 500)
        stay = random.randint(*STAY_MS)
        waited = 0
        while waited < stay:
            for pose, ms in (
                (sprite.Pose(eyes="happy"), 700),
                (sprite.Pose(eyes="blink"), 140),
                (sprite.Pose(eyes="happy", ex=1), 600),
                (sprite.Pose(eyes="happy", ex=-1), 600),
            ):
                waited += ms
                yield self.stand(pose, ms)
        yield self.stand(sprite.Pose(eyes="happy", arm_f=("rest_l", "wave_r")), 500)
        yield self.stand(sprite.Pose(eyes="happy", arm_f=("rest_l", "up_r")), 400)
        yield from self.swing(True)
        yield from self.hop(self.door_cx())
        self.pose = sprite.Pose(eyes="happy", tent="tuck")
        self.draw_guest()
        yield 220
        self.body.hide()
        yield 280
        yield from self.swing(False)
        for dx in (1, -1, 0):
            self.door_dx = dx
            self.draw_door(0.0)
            yield 60
        yield 350


class Guests:
    """Keeps visits in a queue so only one guest is around at a time."""

    def __init__(self, app, limit=4):
        self.app, self.limit = app, limit
        self.queue = []
        self.current = None

    def add(self, name, color, letter=None, look=None):
        if len(self.queue) >= self.limit:
            return False
        self.queue.append((name, color, letter, look))
        if self.current is None:
            self.next()
        return True

    def next(self):
        if self.current is not None or not self.queue:
            return
        name, color, letter, look = self.queue.pop(0)
        self.current = Visit(self.app, name, color, letter, look, self.done)
        self.current.start()

    def done(self, _visit):
        self.current = None
        self.next()

    def clear(self):
        self.queue = []
        if self.current is not None:
            self.current.cancel()
