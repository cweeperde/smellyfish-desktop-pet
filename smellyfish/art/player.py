"""Animation player: a base state with intro/loop/outro, one-shot reactions and forced physics loops."""

import random

from PySide6.QtCore import QObject, QTimer

from smellyfish.art import sprite

ONCE_PRIO = {
    "alarm": 90,
    "warn": 85,
    "error": 80,
    "reminder": 75,
    "angry": 70,
    "dizzy": 65,
    "trophy": 60,
    "trash_full": 55,
    "zap": 56,
    "sweep": 55,
    "water": 55,
    "land": 5,
    "tickled": 45,
    "petted": 45,
    "checkoff": 42,
    "happy": 40,
    "sad": 40,
    "nom": 40,
    "snack": 40,
    "camera": 40,
    "shy": 35,
    "hello": 30,
    "bye": 30,
    "stretch": 25,
    "startle": 50,
    "calendar": 75,
    "float": 8,
    "breathe": 8,
    "look_around": 10,
    "bubbles": 10,
    "read": 10,
    "sneeze": 10,
    "yawn": 10,
    "yoyo": 10,
    "juggle": 10,
    "coffee": 10,
    "gaming": 10,
    "paper_plane": 10,
    "bubblegum": 10,
    "doodle": 10,
    "sunny": 15,
    "rainy": 15,
    "snowy": 15,
    "shiver": 15,
    "cloudy": 15,
    "stormy": 15,
    "foggy": 15,
    "windy": 15,
    "compact": 45,
    "fishing": 10,
    "skateboard": 10,
    "stargaze": 10,
}


class Player(QObject):
    """Plays a base state (intro/loop/outro), one-shot reactions and forced physics loops."""

    def __init__(self, on_frame, on_once_done=None):
        super().__init__()
        self.anims = sprite.build_all()
        self.on_frame = on_frame
        self.on_once_done = on_once_done
        self.base, self.next_base = "idle", None
        self.mode = "base"
        self.name, self.seg, self.idx = "idle", "loop", 0
        self.beat_driven = False
        self.after_outro = None
        self.variant, self.last_variant = "idle", {}
        self.timer = QTimer(self, singleShot=True, timeout=self.advance)

    def pick(self, name):
        options = sprite.VARIANTS.get(name)
        if not options:
            return name
        last = self.last_variant.get(name)
        weights = [0.35 if v == last else 1.0 for v in options]
        self.last_variant[name] = random.choices(options, weights)[0]
        return self.last_variant[name]

    def start(self, name, seg=None):
        self.variant = self.pick(name)
        a = self.anims[self.variant]
        self.name, self.idx = name, 0
        self.seg = seg or ("intro" if a.get("intro") else "loop")
        if not a.get(self.seg):
            return self.advance(skip=True)
        self.show()

    def show(self):
        pose, ms = self.anims[self.variant][self.seg][self.idx]
        self.on_frame(pose)
        if self.beat_driven and self.name == "music" and self.seg == "loop" and self.mode == "base":
            ms = 1600
        self.timer.start(ms)

    def advance(self, skip=False):
        a = self.anims[self.variant]
        if not skip:
            self.idx += 1
            if self.idx < len(a.get(self.seg, [])):
                return self.show()
        self.idx = 0
        if self.mode == "force":
            self.seg = "loop"
            return self.show()
        if self.mode == "once":
            order = ["intro", "loop", "outro"]
            rest = [s for s in order[order.index(self.seg) + 1 :] if a.get(s)]
            if rest:
                self.seg = rest[0]
                return self.show()
            done = self.name
            self.mode = "base"
            self.start(self.base)
            if self.on_once_done:
                self.on_once_done(done)
            return
        if self.seg in ("intro", "loop"):
            if self.next_base:
                return self.leave()
            self.seg = "loop"
        else:
            return self.enter_next()
        if not a.get(self.seg):
            return self.enter_next() if self.next_base else self.timer.start(500)
        self.show()

    def leave(self):
        if self.anims[self.variant].get("outro"):
            self.seg, self.idx = "outro", 0
            return self.show()
        self.enter_next()

    def enter_next(self):
        self.base, self.next_base = self.next_base or self.base, None
        if self.after_outro:
            name, self.after_outro = self.after_outro, None
            if getattr(self, "on_once_start", None):
                self.on_once_start(name)
            self.mode = "once"
            return self.start(name)
        self.start(self.base)

    def interlude(self, name):
        """A short break from the current base: its outro plays first (the laptop goes away), then the reaction,
        then the base starts again from its intro."""
        if self.mode != "base" or self.next_base or self.seg == "outro":
            return False
        self.after_outro = name
        self.timer.stop()
        self.leave()
        return True

    def set_base(self, name):
        if self.mode != "base":
            self.base, self.next_base = name, None
            return
        if name == self.base and self.seg != "outro":
            self.next_base = None
            return
        self.next_base = name
        if self.seg == "loop":
            self.timer.stop()
            self.leave()

    def once(self, name, force=False):
        """Play a one-shot reaction. It never interrupts physics and only replaces a running reaction
        that is not more important (see ONCE_PRIO)."""
        if not force:
            if self.mode == "force":
                return False
            if self.mode == "once" and ONCE_PRIO.get(name, 30) < ONCE_PRIO.get(self.name, 30):
                return False
        if getattr(self, "on_once_start", None):
            self.on_once_start(name)
        self.timer.stop()
        self.mode = "once"
        self.start(name)
        return True

    def force(self, name):
        if self.mode == "force" and self.name == name:
            return
        self.timer.stop()
        self.mode = "force"
        self.start(name, "loop")

    def release(self, then=None):
        self.timer.stop()
        self.mode = "base"
        if then:
            return self.once(then)
        self.start(self.base)

    def beat(self):
        if self.beat_driven and self.name == "music" and self.seg == "loop" and self.mode == "base":
            self.timer.stop()
            self.advance()

    @property
    def busy(self):
        return self.mode != "base"
