"""The desktop pet: windows, animation player, physics and event handling."""
import datetime
import math
import os
import random
import re
import sys
import time

from PIL import Image, ImageDraw
from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QBitmap, QCursor, QGuiApplication, QIcon, QImage, QPainter, \
    QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from smellyfish import __version__
from smellyfish import paths
from smellyfish import settings as cfg
from smellyfish import updater
from smellyfish.art import bubble
from smellyfish.art import house as house_mod
from smellyfish.art import sounds
from smellyfish.art import sprite
from smellyfish.art.house import HouseView
from smellyfish.features import toys
from smellyfish.features.focus import FocusTimer
from smellyfish.features.life import Life
from smellyfish.features.todos import Todos, fmt_due
from smellyfish.integrations import install_hooks
from smellyfish.integrations import discord_presence
from smellyfish.integrations.discord_watch import DiscordWatch
from smellyfish.integrations.server import HookServer, ask_answer, permission_answer
from smellyfish.integrations.usage import UsageWatch
from smellyfish.integrations.weather import Weather
from smellyfish.system import recyclebin
from smellyfish.system import surfaces
from smellyfish.system.beat import BeatDetector
from smellyfish.system.hotkeys import Hotkeys
from smellyfish.system.inputcount import InputCounter
from smellyfish.system.pcmonitor import PcMonitor
from smellyfish.ui.gallery import DiscordSetup, GalleryWindow, HistoryWindow
from smellyfish.ui.settings_window import SCHEMA, SettingsWindow
from smellyfish.ui import theme
from smellyfish.ui.todo_window import TodoWindow
from smellyfish.ui.chat_window import ChatWindow
from smellyfish.ui.ask_window import AskWindow
from smellyfish.ui.about_window import AboutWindow
from smellyfish.ui.quick_send import QuickSend
from smellyfish.ui.edges_overlay import EdgesOverlay
from smellyfish.integrations.llm import LLM
from smellyfish.integrations.llm import guide as llm_guide
from smellyfish.integrations.lan import LanService
from smellyfish.features.guest import Guests
from smellyfish.ui.lobby_window import LobbyWindow
from smellyfish.ui.changelog_window import ChangelogWindow

FEET = sprite.FEET
BODY_X0, BODY_X1 = sprite.BX + 1, sprite.BX + 15
CENTER_X = sprite.BX + 8
HALF_W = BODY_X1 - CENTER_X
GRAVITY = 2600.0
TICK_MS = 16
QUIET_MS = 6000
DONE_MS = 20000
WANDER_RANGE = 450
MAX_JUMP_UP = 520
CLIMB_SPEED = 230
HOP_RANGE = 950
LIMIT_MS = 4 * 60 * 1000
TOOL_ANIM = {"Read": "search", "Grep": "search", "Glob": "search", "LS": "search", "NotebookRead": "search",
             "Bash": "terminal", "PowerShell": "terminal", "BashOutput": "terminal", "shell": "terminal",
             "local_shell": "terminal", "exec_command": "terminal",
             "WebFetch": "browse", "WebSearch": "browse", "web_search": "browse",
             "TodoWrite": "todo", "update_plan": "todo"}
WORK = {"working", "thinking", "search", "terminal", "browse", "todo", "cooking"}


def tool_anim(name):
    name = name or ""
    if name in TOOL_ANIM:
        return TOOL_ANIM[name]
    if name.startswith("mcp__") and ("search" in name.lower() or "fetch" in name.lower()):
        return "browse"
    return "working"


def short_count(n):
    if n < 10000:
        return str(n)
    if n < 1000000:
        return f"{n // 1000}k"
    return f"{n // 1000000}M"


def fmt_elapsed(sec, short=False):
    sec = int(max(0, sec))
    if short:
        if sec < 3600:
            return f"{sec // 60}:{sec % 60:02d}"
        return f"{sec // 3600}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m" if short else f"{sec // 60}m {sec % 60}s"
    return f"{sec // 3600}h{(sec % 3600) // 60}m" if short else f"{sec // 3600}h {(sec % 3600) // 60}m"


ONCE_PRIO = {
    "alarm": 90, "warn": 85, "error": 80, "reminder": 75, "angry": 70, "dizzy": 65, "trophy": 60,
    "trash_full": 55, "zap": 56, "sweep": 55, "water": 55, "land": 5,
    "tickled": 45, "petted": 45, "checkoff": 42, "happy": 40, "sad": 40, "nom": 40, "snack": 40, "camera": 40, "shy": 35,
    "hello": 30, "bye": 30, "stretch": 25,
    "look_around": 10, "bubbles": 10, "read": 10, "sneeze": 10, "yawn": 10, "yoyo": 10, "juggle": 10,
    "tea": 10, "gaming": 10, "paper_plane": 10, "bubblegum": 10, "doodle": 10,
    "sunny": 15, "rainy": 15, "snowy": 15, "shiver": 15, "cloudy": 15,
}
ROAM_BASES = {"idle", "music", "call", "call_muted", "call_deaf", "hot", "offline", "battery_low",
              "working", "thinking", "search", "terminal", "browse", "todo", "cooking"}
ANIM_SOUNDS = {"tickled": "giggle", "petted": "purr", "sweep": "sweep", "water": "splash", "nom": "munch",
               "snack": "munch", "checkoff": "pop", "camera": "shutter", "trophy": "fanfare", "sneeze": "sneeze", "yawn": "yawn",
               "hello": "hello", "bubbles": "pop", "dizzy": "boing", "trash_full": "stink", "sad": "sad",
               "happy": "happy", "zap": "zap", "shy": "pop", "paper_plane": "whoosh", "juggle": "jump"}

LLM_PHASES = {"starting": "Waking up the model server", "loading": "Loading the model",
              "answering": "Thinking"}


AMBIENT = {"idle", "sleeping", "hot", "offline", "battery_low", "call", "call_muted", "call_deaf", "music", "focus",
           "peek"}
FIDGETS = ["look_around", "bubbles", "read", "sneeze", "look_around", "yoyo", "juggle", "tea", "gaming",
           "paper_plane", "bubblegum", "doodle"]
HIDDEN_IN_GALLERY = {"held", "fall", "swim", "climb"}
CEILING_BASES = {"idle", "music", "call", "call_muted", "call_deaf", "hot", "offline", "battery_low"}
WEATHER_ANIM = {"rain": "rainy", "sun": "sunny", "snow": "snowy", "cold": "shiver", "cloud": "cloudy"}
BALL_IDLE_S = 60
MAIL_S = 8
CLIP_COOLDOWN = 20


def to_qimage(pil, dpr):
    pil = pil.convert("RGBA")
    img = QImage(pil.tobytes(), pil.width, pil.height, pil.width * 4, QImage.Format_RGBA8888).copy()
    img.setDevicePixelRatio(dpr)
    return img


def alpha_region(pil):
    a = pil.getchannel("A")
    img = QImage(a.tobytes(), a.width, a.height, a.width, QImage.Format_Alpha8).copy()
    return QRegion(QBitmap.fromImage(img.createAlphaMask()))


def bubble_safe(text):
    """The bubble font only knows Latin-1 plus a few typographic marks, so emoji and the like are dropped."""
    keep = set("…—–“”„’")
    text = "".join(ch for ch in (text or "") if ord(ch) <= 255 or ch in keep)
    return " ".join(text.split(" ")).strip()


def summarize(text, limit=600):
    text = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(^|\n)#+\s*([^\n]+)", r"\1\2: ", text)
    text = re.sub(r"[#*_`>|]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def source_name(payload):
    return "Codex" if payload.get("_source") == "codex" else "Claude"


def perm_spec(payload):
    tool = payload.get("tool_name") or "Tool"
    ti = payload.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        prompt, detail = "Run this command?", "$ " + str(ti.get("command", ""))
    elif tool == "apply_patch":
        files = re.findall(r"\*\*\* (?:Update|Add|Delete) File: (.+)", str(ti.get("command", "")))
        prompt, detail = "Change these files?", ", ".join(files) or str(ti.get("command", ""))[:400]
    elif tool in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        prompt, detail = "Change this file?", str(ti.get("file_path") or ti.get("notebook_path") or "")
    elif tool in ("WebFetch", "WebSearch"):
        prompt, detail = "Go online?", str(ti.get("url") or ti.get("query") or "")
    else:
        prompt = ti.get("description") or "Use this tool?"
        detail = ", ".join(f"{k}: {v}" for k, v in list(ti.items())[:4] if k != "description")[:400]
    short = tool.split("__")[-1] if tool.startswith("mcp__") else tool
    return {"kind": "perm", "tool": short, "prompt": prompt, "detail": detail, "right": source_name(payload),
            "can_always": bool(payload.get("permission_suggestions"))}


class Interactive:
    """A bubble that answers a blocked hook request."""

    def __init__(self, pending):
        self.pending = pending
        self.payload = pending.payload
        self.session = self.payload.get("session_id")
        self.is_ask = self.payload.get("hook_event_name") == "PreToolUse"
        self.questions = (self.payload.get("tool_input") or {}).get("questions") or []
        self.page = 0
        self.answers = {}
        self.picked = []
        self.expanded = False

    def spec(self):
        if not self.is_ask:
            s = perm_spec(self.payload)
        else:
            q = self.questions[self.page]
            s = {"kind": "ask", "header": q.get("header", ""), "question": q.get("question", ""),
                 "page": f"{self.page + 1}/{len(self.questions)}",
                 "options": [o.get("label", "?") for o in q.get("options", [])],
                 "descs": [o.get("description", "") for o in q.get("options", [])],
                 "multi": bool(q.get("multiSelect")), "picked": list(self.picked)}
        s["expanded"] = self.expanded
        return s


# ---------------------------------------------------------------- tiny badge font (3x5)
GLYPHS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
    "!": [".#.", ".#.", ".#.", "...", ".#."], "m": ["...", "##.", "###", "#.#", "#.#"],
    ":": ["...", ".#.", "...", ".#.", "..."], "+": ["...", ".#.", "###", ".#.", "..."],
    "z": ["...", "###", ".#.", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "T": ["###", ".#.", ".#.", ".#.", ".#."], "E": ["###", "#..", "##.", "#..", "###"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."], "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "F": ["###", "#..", "##.", "#..", "#.."], "C": ["###", "#..", "#..", "#..", "###"],
    "L": ["#..", "#..", "#..", "#..", "###"], "S": ["###", "#..", "###", "..#", "###"],
    "G": ["###", "#..", "#.#", "#.#", "###"],
    "s": ["...", ".##", "#..", "..#", "##."], "h": ["#..", "#..", "###", "#.#", "#.#"],
    "k": ["#..", "#.#", "##.", "#.#", "#.#"],
}


BADGE_ICONS = {
    "timer": ["#####", ".###.", "..#..", ".###.", "#####"],
    "sessions": ["##.##", "##.##", ".....", "##.##", "##.##"],
    "clicks": ["#....", "##...", "###..", "####.", "##.#."],
    "call": [".###.", "#...#", "#...#", "##.##", "##.##"],
    "msg": ["#####", "##.##", "#.#.#", "#...#", "#####"],
    "due": [".###.", "#.#.#", "#.###", "#...#", ".###."],
}


def badge_image(items):
    """items: list of (text, rgb[, icon]). Returns a 1x RGBA pixel image of bevelled pills with a little tail."""
    pills = []
    for item in items:
        text, color = item[0], item[1]
        icon = BADGE_ICONS.get(item[2]) if len(item) > 2 else None
        w = sum(len(GLYPHS.get(ch, GLYPHS["!"])[0]) + 1 for ch in text) + 3 + (6 if icon else 0)
        pill = Image.new("RGBA", (w, 9), (0, 0, 0, 0))
        d = ImageDraw.Draw(pill)
        light = tuple(min(255, c + 45) for c in color) + (255,)
        dark = tuple(int(c * 0.65) for c in color) + (255,)
        d.rectangle([1, 0, w - 2, 8], fill=color + (255,))
        d.rectangle([0, 1, w - 1, 7], fill=color + (255,))
        d.line([(1, 0), (w - 2, 0)], fill=light)
        d.line([(1, 8), (w - 2, 8)], fill=dark)
        d.line([(0, 7), (0, 1)], fill=light)
        d.line([(w - 1, 1), (w - 1, 7)], fill=dark)
        x = 2
        if icon:
            for gy, row in enumerate(icon):
                for gx, c in enumerate(row):
                    if c == "#":
                        pill.putpixel((2 + gx, 2 + gy), (255, 255, 255, 255))
            x = 8
        for ch in text:
            for gy, row in enumerate(GLYPHS.get(ch, GLYPHS["!"])):
                for gx, c in enumerate(row):
                    if c == "#":
                        pill.putpixel((x + gx, 2 + gy), (255, 255, 255, 255))
            x += len(GLYPHS.get(ch, GLYPHS["!"])[0]) + 1
        pills.append(pill)
    if not pills:
        return None
    img = Image.new("RGBA", (sum(p.width for p in pills) + 2 * (len(pills) - 1), 12), (0, 0, 0, 0))
    x = 0
    for p in pills:
        img.alpha_composite(p, (x, 0))
        x += p.width + 2
    tail = tuple(items[-1][1][:3]) + (255,)
    tx = img.width - 7
    for k in range(3):
        for dx in range(5 - 2 * k):
            img.putpixel((tx + k + dx, 9 + k), tail)
    return img


# ---------------------------------------------------------------- animation player
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
        self.timer = QTimer(self, singleShot=True, timeout=self.advance)

    def start(self, name, seg=None):
        a = self.anims[name]
        self.name, self.idx = name, 0
        self.seg = seg or ("intro" if a.get("intro") else "loop")
        if not a.get(self.seg):
            return self.advance(skip=True)
        self.show()

    def show(self):
        pose, ms = self.anims[self.name][self.seg][self.idx]
        self.on_frame(pose)
        if self.beat_driven and self.name == "music" and self.seg == "loop" and self.mode == "base":
            ms = 1600
        self.timer.start(ms)

    def advance(self, skip=False):
        a = self.anims[self.name]
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
            rest = [s for s in order[order.index(self.seg) + 1:] if a.get(s)]
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
        if self.anims[self.name].get("outro"):
            self.seg, self.idx = "outro", 0
            return self.show()
        self.enter_next()

    def enter_next(self):
        self.base, self.next_base = self.next_base or self.base, None
        self.start(self.base)

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


# ---------------------------------------------------------------- windows
FLAGS = Qt.FramelessWindowHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus


class PixelWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, FLAGS | Qt.WindowStaysOnTopHint)
        self.app = app
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
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
        self.place()
        self.show()
        self.update()

    def place(self):
        a = self.app
        area = a.screen_at(a.cx(), a.feet() - 4).availableGeometry()
        x = round(a.x + (sprite.BX + 5) * a.pix - self.width())
        if x < area.left() + 2:
            x = round(a.x + (sprite.BX + 11) * a.pix)
        x = max(area.left() + 2, min(x, area.right() - self.width() - 1))
        y = round(a.y + (sprite.BY - 4) * a.pix - self.height())
        y = max(area.top() + 2, y)
        self.move(x, y)

    def mousePressEvent(self, e):
        self.app.open_history()


class BubbleView(PixelWindow):
    def __init__(self, app):
        super().__init__(app)
        self.hits, self.spec, self.tail = [], None, None

    def set_spec(self, spec):
        self.spec = spec
        self.tail = None
        if spec is None or self.app.hidden_for_game():
            self.hide()
            return
        self.place()

    def place(self):
        if self.spec is None or self.app.hanging or self.app.hidden_for_game():
            return
        pix = self.app.pix
        px, py = round(self.app.x), round(self.app.y)
        screen = self.app.screen_at(px + CENTER_X * pix, py + FEET * pix)
        area = screen.availableGeometry()
        dpr = screen.devicePixelRatio()
        unit = max(1, round(bubble.UNIT * dpr))
        k = bubble.UNIT / unit
        h_est = self.height() if self.image is not None else 200
        w_est = self.width() if self.image is not None else 250
        head_y = py + (sprite.BY - 1) * pix
        tail = "bottom" if head_y - h_est >= area.top() else "top"
        centre = px + CENTER_X * pix
        side = "right" if centre - 14 + w_est > area.right() else "left"
        if (tail, side) != self.tail or self.image is None or self.image.devicePixelRatio() != unit / bubble.UNIT:
            pil, hits = bubble.render(self.spec, unit, tail, side)
            self.tail = (tail, side)
            self.image = to_qimage(pil, unit / bubble.UNIT)
            self.hits = [(QRect(round(x0 * k), round(y0 * k), round((x1 - x0) * k), round((y1 - y0) * k)), v)
                         for x0, y0, x1, y1, v in hits]
            self.setFixedSize(round(pil.width * k), round(pil.height * k))
        x = centre - 14 if side == "left" else centre + 14 - self.width()
        y = head_y - self.height() if tail == "bottom" else py + (FEET + 1) * pix
        x = max(area.left(), min(x, area.right() + 1 - self.width()))
        y = max(area.top(), min(y, area.bottom() + 1 - self.height()))
        self.move(x, y)
        if not self.isVisible():
            self.show()
        self.update()

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        for rect, value in self.hits:
            if rect.contains(pos):
                self.app.click_value(value)
                return
        if self.spec and self.spec.get("kind") == "discord":
            self.app.click_value("open_discord")


# ---------------------------------------------------------------- app
class Smellyfish(QObject):
    def __init__(self):
        super().__init__()
        self.cfg = cfg.Settings()
        sounds.set_muted(self.cfg["mute_all"])
        self.cfg.on_error = self.on_save_error
        self.save_retry = QTimer(self, singleShot=True, timeout=self.cfg.save)
        self.pix = int(self.cfg["scale"])
        self.view = PetView(self)
        self.bubble = BubbleView(self)
        self.badge = BadgeView(self)
        self.house = HouseView(self)
        self.settings_win = self.gallery_win = self.history_win = self.discord_win = None
        self.achievements_win = self.todo_win = self.changelog_win = self.chat_win = self.lobby_win = self.ask_win = self.about_win = None
        self.chat_log = []
        self.cheers = []
        self.pending_sends = []
        self.send_timer = QTimer(self, timeout=self.flush_sends)
        self.updated_from = None
        self.cache, self.hang_cache = {}, {}
        self.pose = None
        self.eyes = (0, 0)
        self.player = Player(self.show_pose, self.on_once_done)
        self.player.on_once_start = self.anim_sound
        self.monitor = PcMonitor()
        self.monitor.event.connect(self.on_pc)
        self.beats = BeatDetector()
        self.beats.beat.connect(self.player.beat)
        self.discord = DiscordWatch(self.cfg)
        self.discord.changed.connect(lambda _s: (self.update_ambient(), self.badge_update()))
        self.discord.rpc_status.connect(self.on_discord_status)
        self.discord.message.connect(self.on_discord_message)
        self.discord_status_text = "Connected" if self.cfg.get("discord_token") else "Not connected"
        self.presence = discord_presence.DiscordPresence()
        self.presence_started = time.time()
        self.last_who = "Claude"
        self.presence_timer = QTimer(self, timeout=self.update_presence)
        self.presence_timer.start(5000)
        self.focus = FocusTimer(self.cfg)
        self.focus.phase_end.connect(self.on_focus_end)
        self.focus.changed.connect(self.on_focus_tick)
        self._focus_phase_seen = None
        self.hotkeys = Hotkeys()
        self.hotkey_conflicts = []
        self.life = Life(self.cfg)
        self.todos = Todos(self.cfg)
        self.lan = LanService(self)
        self.guests = Guests(self)
        self.on_letter_delivered = self.deliver_letter
        self.lan.look_provider = self.lan_look
        self.lan.visit.connect(self.on_lan_visit)
        self.lan.letter.connect(self.on_lan_letter)
        self.lan.chat.connect(self.on_lan_chat)
        self.lan.state.connect(lambda _s: QTimer.singleShot(0, self.build_menu))
        self.llm = LLM(self.cfg, self)
        self.llm.chunk.connect(self.on_llm_chunk)
        self.llm.finished.connect(self.on_llm_done)
        self.llm.phase.connect(self.on_llm_phase)
        self.llm_phase = ""
        self.weather = Weather(self.cfg)
        self.weather.changed.connect(lambda _k: (self.cache.clear(), self.render()))
        self.weather.status.connect(lambda t: self.settings_win and self.settings_win.set_weather_status(t))
        self.ball, self.snacks, self.fetch, self.carrying = None, [], None, False
        self.chase_until = 0.0
        self.chase_timer = QTimer(self, timeout=self.chase_step)
        self.mail_until = 0.0
        self.last_clip = 0.0
        QGuiApplication.clipboard().dataChanged.connect(self.on_clipboard)

        self.interactive, self.info = [], None
        self.prompt_time = {}
        self.sessions = {}
        self.history, self.unseen = [], 0

        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.phys = "rest"
        self.perch = None
        self.perch_seen = None
        self.surfs, self.surfs_at = [], 0
        self.icon_surfs, self.icon_since = [], None
        self.homing, self.route_hops, self.home_after_land, self.after_land = False, 0, False, None
        self.target = None
        self.water_phase = None
        self.wandering = False
        self.anchor_cx = None
        self.press, self.clicks, self.throws = None, [], []
        self.hanging = False
        self.theta = self.omega = 0.0
        self.cur_hist, self._last_vx = [], 0.0
        self.hover_since, self.last_shy, self.last_yawn = None, 0.0, time.time()
        self.badge_peek_until, self.badge_marks, self.badge_hover = 0.0, {}, False
        self.game_hidden = False
        self.swim = None
        self.ceil, self.ceil_goal = None, None
        self.climb, self.climb_flip = None, False
        self.plan = []
        self.outfit_day, self.outfit = None, None

        self.tick = QTimer(self, timeout=self.step)
        self.swim_timer = QTimer(self, timeout=self.swim_step)
        self.climb_timer = QTimer(self, timeout=self.climb_step)
        self.hang_timer = QTimer(self, timeout=self.hang_step)
        self.perch_timer = QTimer(self, timeout=self.check_perch)
        self.ceil_timer = QTimer(self, timeout=self.ceiling_step)
        self.eye_timer = QTimer(self, timeout=self.follow_eyes)
        self.quiet = QTimer(self, singleShot=True, timeout=self.on_quiet)
        self.done_timer = QTimer(self, singleShot=True, timeout=self.on_done_timeout)
        self.limit_timer = QTimer(self, singleShot=True, timeout=self.on_limit_over)
        self.wander_timer = QTimer(self, singleShot=True, timeout=self.wander)
        self.fidget_timer = QTimer(self, singleShot=True, timeout=self.fidget)
        self.trip_timer = QTimer(self, singleShot=True, timeout=self.trip_home)
        self.ambient_timer = QTimer(self, timeout=self.update_ambient)
        self.reminder_timer = QTimer(self, timeout=self.check_reminders)
        self.reminder_timer.start(5000)
        self.task_timer = QTimer(self, timeout=self.badge_update)
        self.task_timer.start(1000)
        self.top_timer = QTimer(self, timeout=self.keep_on_top)
        self.top_timer.start(1500)
        self.strokes = []
        self.last_stroke = 0.0

        self.server = HookServer(policy=self.policy)
        self.server.event.connect(self.on_event)
        self.server.ask.connect(self.on_ask)
        self.server.expired.connect(self.on_expired)
        self.server.debug_cmd.connect(self.on_debug)
        self.usage = UsageWatch(self.cfg)
        self.usage.warn.connect(self.on_usage_warn)
        self.server.status.connect(self.usage.claude_status)
        self.trash_visit = None
        self.trash = RecycleWatchProxy(self)
        self.counter = InputCounter(self.on_press)
        self.presses, self.tap_until, self.tap_side = 0, 0.0, 1
        self.press_flush = QTimer(self, timeout=self.flush_presses)
        self.press_flush.start(30000)
        self.updater = updater.Updater(self.cfg)
        self.updater.ready.connect(self.on_update_ready)
        self.updater.status.connect(lambda t: self.notice({"kind": "wait", "chip": "Update", "text": t}))
        self.server.debug = {
            "state": lambda _: {"anim": self.player.name, "base": self.player.base, "mode": self.player.mode,
                                "bubble": self.bubble_kind(), "interactive": len(self.interactive),
                                "phys": self.phys, "pos": [round(self.x), round(self.y)],
                                "feet": round(self.feet()), "cx": round(self.cx()), "perch": bool(self.perch),
                                "homing": self.homing, "home": self.home(),
                                "unseen": self.unseen, "sessions": len(self.sessions), "focus": self.focus.phase,
                                "badge": self.badge.isVisible(), "snacks": self.life.stats.get("snacks", 0),
                                "carrying": self.carrying, "mini": bool(self.cfg.get("mini")),
                                "achievements": sorted(self.life.unlocked),
                                "info": {k: v for k, v in (self.info or {}).items() if k in ("chip", "right", "text")},
                                "badge_items": [t for t, _c in getattr(self, "badge_items", [])],
                                "trash_visit": self.trash_visit, "screen": [self.bounds().x(), self.bounds().y()], "chasing": time.time() < self.chase_until},
        }
        for name in ("click", "snap", "poke", "fling", "drag", "home", "sethome", "house", "play", "focus",
                     "dnd", "hotkey", "snack", "ball", "clip", "mini", "trash", "setting", "stroke", "ui"):
            self.server.debug[name] = (lambda n: lambda p: (self.server.debug_cmd.emit((n, p)), {"queued": True})[1])(
                name)

        bubble.set_dark(self.cfg["dark_ui"])
        theme.set_dark(self.cfg["dark_ui"])
        self.menu = QMenu()
        self.build_menu()
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.tray_icon(), self)
            self.tray.setToolTip("Smellyfish")
            self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(self.on_tray)
            self.tray.show()

        self.apply_view()
        self.place_initial()
        self.refresh_house()
        self.view.show()
        self.view.raise_()
        self.register_hotkeys()
        self.sync_clicker()
        self.player.start("idle")
        self.perch_timer.start(100)
        self.eye_timer.start(100)
        self.ambient_timer.start(2000)
        self.schedule_wander()
        self.schedule_fidget()
        self.schedule_trip()
        self.sync_beats()
        if self.cfg["dnd"]:
            self.player.set_base("sleeping")
        if self.cfg.get("mini"):
            QTimer.singleShot(500, self.place_mini)
        QTimer.singleShot(4000, self.check_whats_new)

    # ------------------------------------------------------------ rendering
    def show_pose(self, pose):
        if getattr(self, "_badge_anim", None) != self.player.name:
            self._badge_anim = self.player.name
            if self.cfg["discord"] and self.discord.state["in_call"]:
                QTimer.singleShot(0, self.badge_update)
        self.pose = pose
        if not self.hanging and not self.dangling():
            self.render()

    def current_outfit(self):
        today = datetime.date.today()
        if self.outfit_day != today:
            self.outfit_day, self.outfit = today, sprite.outfit_for(today.month, today.day)
        return self.outfit if self.cfg["seasonal"] else None

    def render(self):
        pose = self.pose
        if pose is None or self.hanging or self.dangling():
            return
        ex, ey = 0, 0
        if self.cfg["eyes_follow"] and not pose.side and pose.eyes == "open" and pose.ex == 0 and pose.ey == 0 \
                and self.player.name in ("idle", "question", "call"):
            ex, ey = self.eyes
        outfit = self.current_outfit()
        flip = self.phys == "climb" and self.climb_flip
        if self.cfg.get("mini") and self.cfg.get("mini_side") == "left" and pose.side and pose.flip:
            pose = pose.but(flip=False)
        weather = self.weather.kind if self.cfg["weather"] else None
        carry = self.carrying and not pose.side
        skin = self.skin_key()
        gear = self.gear()
        tap = self.tap_side if time.time() < self.tap_until and not pose.side else 0
        key = (id(pose), ex, ey, outfit, flip, weather, carry, skin, gear, tap)
        if key not in self.cache:
            p = pose.but(ex=ex, ey=ey) if (ex or ey) else pose
            if flip:
                p = p.but(flip=True)
            if tap:
                p = p.but(arm_f=("up_l", "rest_r") if tap == 1 else ("rest_l", "up_r"), dy=p.dy + 1,
                          eyes="happy" if p.eyes == "open" else p.eyes)
            if gear != (None, False, False):
                p = sprite.with_gear(p, *gear)
            p = sprite.with_outfit(p, outfit)
            p = sprite.with_weather(p, weather)
            if carry:
                p = p.but(parts=p.parts + [(sprite.BALL, sprite.BX + 14 + p.dx, sprite.BY + 1 + p.dy)])
            pal = self.skin_pal()
            dpr = self.view.devicePixelRatioF() or 1.0
            dev = max(1, round(self.pix * dpr))
            self.cache[key] = (to_qimage(sprite.render(p, dev, pal=pal), dev / self.pix),
                               alpha_region(sprite.render(p, self.pix)))
            if len(self.cache) > 2000:
                self.cache.clear()
        self.view.set_frame(*self.cache[key])

    # ------------------------------------------------------------ click counter (bongo cat style)
    def sync_clicker(self):
        if self.cfg.get("clicker"):
            self.counter.start(int(self.view.winId()))
        else:
            self.counter.stop()
            self.flush_presses()
        self.badge_update()

    def on_press(self, kind, n):
        self.presses += n
        if self.presses >= 50:
            self.flush_presses()
        elif self.badge.isVisible() or self.presses % 5 == 0:
            self.badge_update()

    def clicks_today(self):
        today = time.strftime("%Y-%m-%d")
        st = self.life.stats
        base = st.get("clicks_today", 0) if st.get("clicks_day") == today else 0
        return base + self.presses

    def flush_presses(self):
        if not self.presses:
            return
        n, self.presses = self.presses, 0
        today = time.strftime("%Y-%m-%d")
        st = self.life.stats
        if st.get("clicks_day") != today:
            st["clicks_day"], st["clicks_today"] = today, 0
        st["clicks_today"] = st.get("clicks_today", 0) + n
        st["best_day_clicks"] = max(st.get("best_day_clicks", 0), st["clicks_today"])
        self.bump("clicks", n)
        self.badge_update()

    def gear(self):
        """What the pet keeps wearing whatever it is doing: (headset, band, sweat)."""
        name = self.player.name
        if self.cfg["dnd"] or name in ("sleeping", "peek") or self.cfg.get("mini"):
            return None, False, False
        d = self.discord.state
        headset = None
        if self.cfg["discord"] and d["in_call"]:
            headset = "mic"
        band = self.focus.phase == "focus"
        sweat = bool(self.cfg["react_cpu"] and self.monitor.hot and name != "hot")
        return headset, band, sweat

    def skin_key(self):
        return self.cfg.get("skin"), self.cfg.get("skin_color")

    def skin_pal(self):
        name = self.cfg.get("skin") or "lavender"
        if name == "custom":
            c = (self.cfg.get("skin_color") or "#c492ec").lstrip("#")
            return sprite.skin_from_color(tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)))
        return sprite.SKINS.get(name)

    def apply_view(self):
        self.cache.clear()
        self.hang_cache.clear()
        if not self.hanging:
            self.view.setFixedSize(sprite.CW * self.pix, sprite.CH * self.pix)
        for w in (self.view, self.house):
            w.setWindowOpacity(float(self.cfg["opacity"]))
        self.render()

    def tray_icon(self):
        b = sprite.BX, sprite.BY
        pil = sprite.render(sprite.Pose(), 4).crop(((b[0] - 1) * 4, (b[1] - 1) * 4, (b[0] + 17) * 4, (b[1] + 13) * 4))
        return QIcon(QPixmap.fromImage(to_qimage(pil, 1.0)))

    def animation_names(self):
        return [n for n in sprite.ANIMATIONS if n not in HIDDEN_IN_GALLERY]

    def preview_anim(self, name):
        if name and not self.hanging and self.phys == "rest":
            self.player.once(name, force=True)

    # ------------------------------------------------------------ achievements
    def bump(self, stat, n=1):
        for title, desc in self.life.bump(stat, n):
            self.add_history("Smellyfish", "Achievement", f"{title}: {desc}")
            self.celebrate(title, desc)

    def celebrate(self, title, desc):
        QTimer.singleShot(1800, lambda: self.cheer(title, desc))

    def cheer(self, title, desc):
        """Shows an achievement bubble, but never on top of something else the user still has to read."""
        if self.cfg["dnd"] or self.hidden_for_game():
            self.unseen += 1
            return self.badge_update()
        if self.interactive or self.info:
            self.cheers.append((title, desc))
            return
        self.set_info({"kind": "trophy", "chip": "Achievement", "text": f"{title}! {desc}"})
        QTimer.singleShot(8000, lambda: self.set_info(None) if self.info and self.info.get(
            "kind") == "trophy" else None)
        if self.phys == "rest" and not self.hanging:
            self.player.once("trophy")
        else:
            self.sfx("fanfare")

    def flush_cheers(self):
        if self.cheers and not self.info and not self.interactive:
            self.cheer(*self.cheers.pop(0))

    # ------------------------------------------------------------ sound
    def fun_sounds_on(self):
        return (self.cfg["sfx"] and not self.cfg["dnd"] and not self.hidden_for_game()
                and self.player.base != "sleeping" and self.player.name != "sleeping")

    def sfx(self, name):
        if self.fun_sounds_on():
            sounds.play(name, self.cfg["volume"])

    def notify_sound(self, name):
        if self.cfg["sound_done"] and not self.cfg["dnd"] and not self.hidden_for_game():
            sounds.play(name, self.cfg.get("notify_volume", self.cfg["volume"]))

    def anim_sound(self, name):
        snd = ANIM_SOUNDS.get(name)
        if snd:
            self.sfx(snd)

    # ------------------------------------------------------------ house & home
    def refresh_house(self):
        if self.cfg["show_house"] and not self.hidden_for_game() and getattr(self, "_visible", True):
            self.house.refresh()
            self.house.show()
            self.view.raise_()
        else:
            self.house.hide()

    def home_ground(self):
        h = self.cfg.get("home")
        fixed = self.fixed_screen()
        screens = [fixed] if fixed else QGuiApplication.screens()
        if h and any(s.geometry().contains(QPoint(round(h[0]), round(h[1]) - 4)) for s in screens):
            return h
        area = (fixed or QGuiApplication.primaryScreen()).availableGeometry()
        return [area.right() - 60 - (house_mod.LEFT + house_mod.WIDTH) * self.pix, area.bottom() + 1]

    def home(self):
        """Where the pet sits: on the bed."""
        hx, hy = self.home_ground()
        bed = house_mod.BED_H * self.pix if self.cfg["show_house"] else 0
        return [hx, hy - bed]

    def house_zone(self):
        if not self.cfg["show_house"]:
            return None
        hx, hy = self.home_ground()
        return (hx + (house_mod.LEFT - HALF_W) * self.pix, hx + (house_mod.LEFT + house_mod.WIDTH + HALF_W) * self.pix,
                hy)

    def in_house(self, cx, feet):
        z = self.house_zone()
        return bool(z) and z[0] <= cx <= z[1] and abs(feet - z[2]) < 6 * self.pix

    def at_home(self):
        hx, hy = self.home()
        return abs(self.cx() - hx) < 16 and abs(self.feet() - hy) < 4 and self.phys == "rest"

    def house_click(self, name):
        if name == "lamp":
            self.apply_setting("dnd", not self.cfg["dnd"])
        elif name == "plant":
            if not self.cfg.get("weather_place"):
                return self.show_weather()
            self.weather.refresh()
            self.show_weather(animate=False)
            QTimer.singleShot(900, self.water_now)
        elif name == "sign":
            self.apply_setting("wander", not self.cfg["wander"])
        elif name == "bed":
            self.go_home()

    def water_now(self):
        if not self.cfg["show_house"]:
            return
        self.water_phase = "wanted"
        if self.at_home():
            self.arrived_home()
        else:
            self.go_home()

    def arrived_home(self):
        self.homing = False
        self.anchor_cx = self.cx()
        if self.cfg["dnd"] or not self.cfg["show_house"]:
            self.water_phase = None
            return
        recently = time.time() - float(self.cfg.get("plant_watered_at") or 0) < 2 * 3600
        if self.water_phase == "wanted" or (self.cfg["auto_water"] and not recently and random.random() < 0.5):
            self.water_phase = "to_plant"
            hx, hy = self.home_ground()
            self.jump_to(hx + house_mod.WATER_SPOT * self.pix, hy, 0.42,
                         surfaces.Surface(None, hx + (house_mod.WATER_SPOT - 4) * self.pix,
                                          hx + (house_mod.WATER_SPOT + 4) * self.pix, hy))
        else:
            self.water_phase = None

    def on_once_done(self, name):
        if name == "water":
            self.bump("watered")
            self.cfg.set("plant_watered_at", time.time())
            self.refresh_house()
            self.water_phase = "back"
            hx, hy = self.home()
            QTimer.singleShot(300, lambda: self.jump_to(hx, hy, 0.42, surfaces.Surface(None, hx - 30, hx + 30, hy)))

    # ------------------------------------------------------------ geometry
    def cx(self):
        return self.x + CENTER_X * self.pix

    def feet(self):
        return self.y + FEET * self.pix

    def fixed_screen(self):
        want = self.cfg.get("monitor") or "primary"
        if want == "all":
            return None
        if want != "primary":
            for sc in QGuiApplication.screens():
                g = sc.geometry()
                if f"{g.x()},{g.y()}" == want:
                    return sc
        return QGuiApplication.primaryScreen()

    def bounds(self):
        sc = self.fixed_screen()
        return sc.geometry() if sc else QGuiApplication.primaryScreen().virtualGeometry()

    def screen_at(self, x, y):
        fixed = self.fixed_screen()
        if fixed is not None:
            return fixed
        s = QGuiApplication.screenAt(QPoint(round(x), round(y)))
        if s is None:
            cands = [sc for sc in QGuiApplication.screens() if sc.geometry().left() <= x <= sc.geometry().right()]
            s = min(cands or QGuiApplication.screens(),
                    key=lambda sc: abs(sc.geometry().center().y() - y) + abs(sc.geometry().center().x() - x))
        return s

    def area(self):
        return self.screen_at(self.cx(), self.feet() - 4).availableGeometry()

    def move_to(self, x, y):
        self.x, self.y = x, y
        self.view.move(round(x), round(y))
        if self.bubble.isVisible():
            self.bubble.place()
        if self.badge.isVisible():
            self.badge.place()

    def place_initial(self):
        pos = self.cfg.get("position")
        fixed = self.fixed_screen()
        if pos and any(s.availableGeometry().contains(QPoint(pos[0] + CENTER_X * self.pix, pos[1] + FEET * self.pix - 4))
                       for s in ([fixed] if fixed else QGuiApplication.screens())):
            self.move_to(*pos)
            self.fall()
        else:
            hx, hy = self.home()
            self.move_to(hx - CENTER_X * self.pix, hy - FEET * self.pix)
            self.anchor_cx = hx

    def own_hwnds(self):
        return {int(w.winId()) for w in (self.view, self.bubble, self.house, self.badge)}

    def get_surfaces(self, fresh=False, icons=False):
        """Window tops; icons=True adds desktop icons. The icon the pet sits on is always included."""
        if fresh or time.time() - self.surfs_at > 0.3:
            room = (FEET - sprite.BY + 2) * self.pix
            foot = None
            if self.cfg.get("sit_on_icons"):
                foot = (2 * HALF_W * self.pix, (FEET - sprite.BY + 3) * self.pix)
            found = surfaces.surfaces(self.own_hwnds(), room, self.cfg["sit_on_windows"], foot)
            fixed = self.fixed_screen()
            if fixed is not None:
                g = fixed.geometry()
                keep = []
                for s in found:
                    if g.top() <= s.y <= g.bottom() and s.x1 > g.left() + 20 and s.x0 < g.right() - 20:
                        s.x0, s.x1 = max(s.x0, g.left()), min(s.x1, g.right())
                        keep.append(s)
                found = keep
            self.surfs = [s for s in found if not s.icon]
            self.icon_surfs = [s for s in found if s.icon]
            self.surfs_at = time.time()
        if icons:
            return self.surfs + self.icon_surfs
        here = self.perch[0] if self.perch else None
        return self.surfs + [s for s in self.icon_surfs if here is not None and s.hwnd == here]

    def fits(self, s, cx):
        m = HALF_W * self.pix
        return s.visible_span(cx - m, cx + m)

    def bed_surface(self):
        if not self.cfg["show_house"]:
            return None
        hx, hy = self.home()
        half = house_mod.LAYOUT["bed"][1] / 2 * self.pix
        return surfaces.Surface(None, hx - half, hx + half, hy)

    def floor_surface(self):
        a = self.area()
        return surfaces.Surface(None, a.left(), a.right(), a.bottom() + 1)

    # ------------------------------------------------------------ physics
    def fall(self, vx=0.0, vy=0.0, target=None):
        if not self.cfg["gravity"]:
            self.phys, self.perch = "rest", None
            self.keep_on_screen()
            self.save_position()
            return
        self.phys, self.perch = "air", None
        self.vx, self.vy = vx, vy
        self.target = target
        self.surfs_at = 0
        self.player.force("fall")
        if vy < -200:
            self.sfx("jump")
        self.tick.start(TICK_MS)

    def step(self):
        if self.phys != "air":
            self.tick.stop()
            return
        dt = TICK_MS / 1000
        prev_feet = self.feet()
        self.vy = min(self.vy + GRAVITY * dt, 3200)
        x, y = self.x + self.vx * dt, self.y + self.vy * dt
        vg = self.bounds()
        if x + BODY_X0 * self.pix < vg.left():
            x, self.vx = vg.left() - BODY_X0 * self.pix, abs(self.vx) * 0.5
        if x + BODY_X1 * self.pix > vg.right():
            x, self.vx = vg.right() - BODY_X1 * self.pix, -abs(self.vx) * 0.5
        self.x, self.y = x, y
        if self.ceil_goal is not None and self.vy > -80:
            return self.attach_ceiling()
        area = self.area()
        if self.y + sprite.BY * self.pix < area.top():
            self.y, self.vy = area.top() - sprite.BY * self.pix, abs(self.vy) * 0.3
        new_feet, cx = self.feet(), self.cx()
        hit = None
        if self.vy > 0:
            cands = [] if self.target is not None else [s for s in self.get_surfaces(icons=True) if self.fits(s, cx)]
            if self.target is not None:
                cands.append(self.target)
            bed = self.bed_surface()
            if bed is not None:
                cands.append(bed)
            for s in cands:
                if prev_feet - 1 <= s.y <= new_feet + 1 and s.visible_at(cx) and (hit is None or s.y < hit.y):
                    hit = s
            floor = area.bottom() + 1
            if hit is None and new_feet >= floor:
                hit = surfaces.Surface(None, area.left(), area.right(), floor)
        if hit is None:
            self.move_to(self.x, self.y)
            return
        self.y = hit.y - FEET * self.pix
        if self.vy > 1300 and self.target is None:
            self.vy, self.vx = -self.vy * 0.3, self.vx * 0.6
            self.move_to(self.x, self.y)
            self.sfx("land")
            return
        self.land(hit)

    def land(self, hit):
        self.tick.stop()
        self.target = None
        self.ceil_goal = None
        impact = self.vy
        self.phys, self.vx, self.vy = "rest", 0.0, 0.0
        self.perch = (hit.hwnd, hit.x0, hit.y) if hit.hwnd else None
        self.perch_seen = (time.time(), hit.x0, hit.y)
        self.move_to(self.x, hit.y - FEET * self.pix)
        reaction, self.after_land = self.after_land, None
        if reaction == "angry":
            self.sfx("angry")
        elif impact > 500:
            self.sfx("land")
        if impact > 2600:
            self.bump("big_falls")
        self.save_position()
        if self.water_phase == "to_plant":
            self.water_phase = "watering"
            return self.player.release("water")
        self.player.release(reaction or "land")
        if self.trash_visit == "going":
            self.trash_visit = "there"
            QTimer.singleShot(350, self.trash_report)
            return
        if self.plan:
            QTimer.singleShot(260, self.next_step)
            return
        if self.fetch is not None:
            QTimer.singleShot(250, self.reach_toy)
            return
        if self.water_phase == "back":
            self.water_phase = None
            self.anchor_cx = self.cx()
            return
        if self.homing:
            if self.at_home():
                QTimer.singleShot(400, self.arrived_home)
            else:
                QTimer.singleShot(320, self.step_home)
            return
        if self.home_after_land:
            self.home_after_land = False
            QTimer.singleShot(700, self.go_home)
            return
        if self.anchor_cx is None or not self.wandering:
            self.anchor_cx = self.cx()
        chained = self.wandering and getattr(self, "wander_chain", 0) > 0
        self.wandering = False
        if chained:
            self.wander_chain -= 1
            QTimer.singleShot(random.randint(1200, 2600),
                              lambda: self.can_roam() and self.cfg["wander"] and self.wander_window())
        else:
            self.wander_chain = 0
        self.schedule_wander()

    def snap_target(self):
        cx, feet = self.cx(), self.feet()
        best = None
        extra = [b for b in (self.bed_surface(),) if b is not None]
        for s in self.get_surfaces(fresh=True, icons=True) + extra + [self.floor_surface()]:
            ok = self.fits(s, cx) if s.hwnd else s.visible_at(cx)
            if ok and s.y - 14 <= feet <= s.y + 10 * self.pix:
                if best is None or abs(s.y - feet) < abs(best.y - feet):
                    best = s
        return best

    def check_perch(self):
        if (self.phys != "rest" or not self.cfg["gravity"] or self.cfg.get("mini") or self.plan
                or self.trash_visit):
            return
        now = time.time()
        if self.perch:
            hwnd, x0, y0 = self.perch
            top = surfaces.window_top(hwnd)
            if top is None:
                return self.lost_perch()
            nx0, nx1, ny = top
            t_prev, sx0, sy0 = self.perch_seen
            dt = max(now - t_prev, 1e-3)
            speed = math.hypot(nx0 - sx0, ny - sy0) / dt
            self.perch_seen = (now, nx0, ny)
            if speed > 2600:
                self.after_land = "dizzy"
                return self.fall((nx0 - sx0) / dt * 0.4, -300)
            if (nx0, ny) != (x0, y0):
                self.perch = (hwnd, nx0, ny)
                self.move_to(self.x + nx0 - x0, ny - FEET * self.pix)
                if self.anchor_cx is not None:
                    self.anchor_cx += nx0 - x0
            if not nx0 <= self.cx() <= nx1:
                return self.lost_perch()
            if isinstance(hwnd, tuple) and self.icon_reached(hwnd, now):
                return self.leave_icon()
            if now - self.surfs_at > 1.0:
                cur = next((s for s in self.get_surfaces() if s.hwnd == hwnd), None)
                if cur is None or not self.fits(cur, self.cx()):
                    self.lost_perch()
        else:
            floor = self.area().bottom() + 1
            if abs(self.feet() - floor) <= 1:
                return
            hx, hy = self.home()
            if abs(self.feet() - hy) <= 1 and abs(self.cx() - hx) < 60:
                return
            if not any(abs(s.y - self.feet()) < 2 and self.fits(s, self.cx()) for s in self.get_surfaces()):
                self.lost_perch()

    def icon_reached(self, key, now):
        """The cursor has been over the icon the pet sits on for a moment (the user wants to use it)."""
        b = surfaces.icon_bounds(key)
        pos = QCursor.pos()
        if b is None or self.press is not None or not (b[0] - 6 <= pos.x() <= b[2] + 6 and b[1] - 6 <= pos.y() <= b[3] + 6):
            self.icon_since = None
            return False
        self.icon_since = self.icon_since or now
        return now - self.icon_since > 0.5

    def leave_icon(self):
        """Hop down from a desktop icon to somewhere nearby."""
        self.icon_since = None
        cx, feet = self.cx(), self.feet()
        a = self.area()
        margin = HALF_W * self.pix
        side = random.choice((-1, 1))
        tx = max(a.left() + margin, min(a.right() - margin, cx + side * random.randint(110, 260)))
        floor = self.screen_at(tx, feet + 4).availableGeometry().bottom() + 1
        self.wandering = True
        self.anchor_cx = tx
        self.run_plan([("hop", (tx, max(feet, floor), None))])

    def lost_perch(self):
        self.home_after_land = True
        self.fall()

    def keep_on_screen(self):
        a = self.area()
        x = max(a.left() - BODY_X0 * self.pix, min(self.x, a.right() - BODY_X1 * self.pix))
        y = max(a.top() - sprite.BY * self.pix, min(self.y, a.bottom() + 1 - FEET * self.pix))
        self.move_to(x, y)

    # ------------------------------------------------------------ hopping and the way home
    def jump_to(self, tx, t_feet, flight=0.5, target=None):
        dx = tx - self.cx()
        dyw = t_feet - self.feet()
        # the target has to be reached while falling, otherwise the pet flies past it and drifts off to the side
        flight = max(flight, math.sqrt(2 * max(0.0, -dyw) / GRAVITY) + 0.14)
        vx = dx / flight
        vy = (dyw - 0.5 * GRAVITY * flight * flight) / flight
        self.fall(vx, max(vy, -2100), target)

    def can_roam(self):
        return (self.phys == "rest" and self.cfg["gravity"] and not self.homing and not self.cfg["dnd"]
                and self.fetch is None and not self.carrying and time.time() > self.chase_until
                and self.player.base in ROAM_BASES and not self.player.busy and not self.bubble.isVisible()
                and not self.interactive
                and not self.hidden_for_game() and self.water_phase is None and self.focus.phase != "focus")

    # ------------------------------------------------------------ plans: hop / climb / swim step by step
    def run_plan(self, steps):
        self.plan = list(steps)
        self.next_step()

    def next_step(self):
        if self.phys != "rest" or not self.plan:
            return
        kind, args = self.plan.pop(0)
        if kind == "hop":
            tx, ty, target = args
            rise = max(0.0, self.feet() - ty)
            dist = abs(tx - self.cx())
            self.jump_to(tx, ty, 0.42 + min(0.35, rise / 1000 + dist / 2500), target)
        elif kind == "climb":
            self.start_climb(*args)
        elif kind == "swim":
            self.start_swim(*args)

    def ledge(self, x, y):
        return surfaces.Surface(None, x - 24, x + 24, y)

    def start_climb(self, to_feet, flip, hwnd=None, left=None):
        self.tick.stop()
        self.phys, self.perch = "climb", None
        if hwnd:
            top = surfaces.window_top(hwnd)
            if top is None:
                self.plan = []
                return self.fall()
            if to_feet < self.feet():
                to_feet = top[2]
        self.climb = {"to": to_feet, "dir": -1 if to_feet < self.feet() else 1, "hwnd": hwnd, "left": left,
                      "checked": time.time()}
        self.climb_flip = flip
        self.player.force("climb")
        self.render()
        self.climb_timer.start(TICK_MS)

    def climb_step(self):
        c = self.climb
        if c is None or self.phys != "climb":
            self.climb_timer.stop()
            return
        if c["hwnd"] and time.time() - c["checked"] > 0.15:
            c["checked"] = time.time()
            top = surfaces.window_top(c["hwnd"])
            if top is None:
                self.climb_timer.stop()
                self.climb, self.climb_flip = None, False
                self.phys = "rest"
                self.plan = []
                return self.fall()
            x0, x1, y = top
            wall = x0 if c["left"] else x1
            m = HALF_W * self.pix + 2
            self.move_to(wall - m - CENTER_X * self.pix if c["left"] else wall + m - CENTER_X * self.pix, self.y)
            if c["dir"] < 0:
                c["to"] = y
            if self.plan and self.plan[0][0] == "hop":
                kind, (tx, ty, target) = self.plan[0]
                if c["dir"] < 0:
                    inside = x0 + m + 30 if c["left"] else x1 - m - 30
                    self.plan[0] = ("hop", (inside, y, surfaces.Surface(c["hwnd"], x0, x1, y)))
        feet = self.feet() + c["dir"] * CLIMB_SPEED * self.pix / 4 * TICK_MS / 1000
        done = (c["dir"] < 0 and feet <= c["to"]) or (c["dir"] > 0 and feet >= c["to"])
        if done:
            feet = c["to"]
        self.move_to(self.x, feet - FEET * self.pix)
        if done:
            self.climb_timer.stop()
            self.climb = None
            self.phys = "rest"
            self.climb_flip = False
            self.bump("climbs")
            if self.plan:
                self.next_step()
            else:
                self.fall()

    def climb_up_plan(self, s, tx, left=None):
        """Steps to get from the floor onto window s by climbing its left or right side
        (the nearer one unless a side is given; now and then the far one for variety)."""
        cx, feet = self.cx(), self.feet()
        if self.perch is not None or s.icon:
            return None
        margin = HALF_W * self.pix
        if left is None:
            left = abs(cx - s.x0) <= abs(cx - s.x1)
            if random.random() < 0.3:
                far = self.climb_up_plan(s, tx, not left)
                if far:
                    return far
        wall = s.x0 if left else s.x1
        stand = wall - (margin + 2) if left else wall + (margin + 2)
        floor = self.screen_at(stand, feet - 4).availableGeometry().bottom() + 1
        bottom = min(getattr(s, "bottom", floor), floor)
        if floor - bottom > MAX_JUMP_UP - 40 or not self.side_clear(s, left, s.y + 4, bottom - 4):
            return None
        a = self.area()
        if not a.left() + margin <= stand <= a.right() - margin:
            return None
        steps = []
        if abs(stand - cx) > 6 or abs(feet - floor) > 2:
            steps.append(("hop", (stand, floor, self.ledge(stand, floor))))
        if floor - bottom > 8:
            steps.append(("hop", (stand, bottom, self.ledge(stand, bottom))))
        steps.append(("climb", (s.y, not left, s.hwnd, left)))
        inside = s.x0 + margin + 30 if left else s.x1 - margin - 30
        steps.append(("hop", (inside, s.y, s)))
        return steps

    def climb_down_plan(self, toward_x):
        """From a window top: hop to the nearer corner, climb down its side to the floor."""
        if not self.perch:
            return None
        s = next((w for w in self.get_surfaces(fresh=True) if w.hwnd == self.perch[0]), None)
        if s is None or s.icon:
            return None
        margin = HALF_W * self.pix
        left = toward_x < (s.x0 + s.x1) / 2
        wall = s.x0 if left else s.x1
        stand = wall - (margin + 2) if left else wall + (margin + 2)
        a = self.screen_at(stand, s.y + 4).availableGeometry()
        floor = a.bottom() + 1
        if not a.left() + margin <= stand <= a.right() - margin:
            return None
        if not self.side_clear(s, left, s.y + 4, min(getattr(s, "bottom", floor), floor) - 4):
            return None
        return [("hop", (stand, s.y, self.ledge(stand, s.y))), ("climb", (floor, not left, s.hwnd, left))]

    def side_clear(self, s, left, y_from, y_to):
        """The window edge and the strip beside it (where the pet hangs) are not behind other windows."""
        m = HALF_W * self.pix
        wall = s.x0 if left else s.x1
        out = -1 if left else 1
        xs = (wall - out * 2, wall + out * 2, wall + out * m, wall + out * 2 * m)
        if not all(s.side_visible(x, y_from, y_to, step=8) for x in xs):
            return False
        a = self.area()
        return a.left() <= wall + out * 2 * m <= a.right()

    def wander(self):
        self.schedule_wander()
        if not (self.can_roam() and self.cfg["wander"]) or self.cfg.get("mini"):
            return
        if self.player.base != "idle" and random.random() < 0.35:
            return
        if self.cfg.get("ceiling_hang") and random.random() < 0.3 and self.hang_from_window():
            return
        hop_chance = 0.45 if self.perch else 0.6
        if self.perch and isinstance(self.perch[0], tuple) and random.random() < 0.5:
            return self.leave_icon()
        if self.cfg["window_hop"] and (self.cfg["sit_on_windows"] or self.cfg.get("sit_on_icons")) \
                and random.random() < hop_chance and self.wander_window():
            return
        a = self.area()
        margin = HALF_W * self.pix
        lo, hi = a.left() + margin, a.right() - margin
        surf = None
        if self.perch:
            surf = next((s for s in self.get_surfaces(fresh=True) if s.hwnd == self.perch[0]), None)
            if surf is None:
                return
            if random.random() < 0.2:
                down = self.climb_down_plan(random.choice((surf.x0, surf.x1)))
                if down:
                    self.wandering = True
                    return self.run_plan(down)
            lo, hi = max(lo, surf.x0 + margin), min(hi, surf.x1 - margin)
        anchor = self.anchor_cx if self.anchor_cx is not None else self.cx()
        reach = WANDER_RANGE
        zone = self.house_zone()
        if zone and self.in_house(anchor, self.feet()):
            reach += (zone[1] - zone[0]) / 2
        lo, hi = max(lo, anchor - reach), min(hi, anchor + reach)
        near = 40 if surf is not None else 80
        options = [x for x in range(int(lo), int(hi) + 1, 8) if abs(x - self.cx()) >= near
                   and (surf is None or self.fits(surf, x)) and not self.in_house(x, self.feet())]
        if not options:
            return
        tx = random.choice(options)
        y = self.feet()
        target = surf if surf is not None else surfaces.Surface(None, tx - 24, tx + 24, y)
        steps = []
        x = self.cx()
        while abs(tx - x) > 1:
            x += max(-260, min(260, tx - x))
            steps.append(("hop", (x, y, target if abs(x - tx) < 1 else
                                  (surf or surfaces.Surface(None, x - 24, x + 24, y)))))
        self.wandering = True
        self.anchor_cx = tx
        self.run_plan(steps)

    def show_edges(self):
        if getattr(self, "edges_win", None) is None:
            self.edges_win = EdgesOverlay(self)
        self.edges_win.start(12)

    def hang_from_window(self, manual=False):
        """Jump up to the underside of a window and dangle there upside down."""
        pix, m = self.pix, HALF_W * self.pix
        cx, feet = self.cx(), self.feet()
        a = self.screen_at(cx, feet - 4).geometry()
        drop = (FEET - sprite.BY) * pix
        options = []
        for s in self.get_surfaces(fresh=True):
            if s.icon or s.bottom + drop * 0.8 > a.bottom() or s.bottom < a.top() + 60:
                continue
            rise = feet - (s.bottom + drop)
            if not 20 <= rise <= MAX_JUMP_UP:
                continue
            for x in range(int(s.x0 + m + 30), int(s.x1 - m - 30), 40):
                if abs(x - cx) > 650:
                    continue
                if any(c[0] <= x + m and c[2] >= x - m and c[1] <= s.bottom + 2 and c[3] >= s.bottom - 2
                       for c in s.covers):
                    continue
                options.append((s, x, rise))
        if not options:
            if manual:
                self.notice({"kind": "wait", "chip": "Smellyfish", "text": "No window with free space below it that "
                             "I can reach from here."}, seconds=6)
            return False
        s, x, rise = random.choice(options)
        vy = -math.sqrt(2 * GRAVITY * rise)
        t = -vy / GRAVITY
        self.ceil_goal = {"hwnd": s.hwnd, "x": x, "bottom": s.bottom}
        self.wandering = False
        self.anchor_cx = x
        self.fall((x - cx) / t, vy)
        return True

    def attach_ceiling(self):
        g, self.ceil_goal = self.ceil_goal, None
        self.tick.stop()
        info = surfaces.window_bottom(g["hwnd"])
        if info is None or not info[0] + 20 < self.cx() < info[1] - 20:
            return self.fall()
        self.phys, self.perch = "ceiling", None
        self.vx = self.vy = 0.0
        self.ceil = {"hwnd": g["hwnd"], "bottom": info[2], "x0": info[0], "checked": 0.0,
                     "until": time.time() + random.uniform(10, 24)}
        if random.random() < 0.5:
            self.ceil.update(single=True, pivot=[self.cx(), info[2]], nudge=0.0)
            self.theta, self.omega = random.choice((-0.35, 0.35)), 0.0
            self.cache.clear()
            self.ceil_timer.start(TICK_MS)
            return self.dangle_step(self.ceil)
        self.move_to(self.x, info[2] - sprite.BY * self.pix)
        self.player.force("ceiling")
        self.ceil_timer.start(120)

    def ceiling_step(self):
        c = self.ceil
        if c is None or self.phys != "ceiling":
            self.ceil_timer.stop()
            return
        now = time.time()
        if c.get("single"):
            self.dangle_step(c)
            if now - c["checked"] < 0.15:
                return
        c["checked"] = now
        info = surfaces.window_bottom(c["hwnd"])
        at = c["pivot"][0] if c.get("single") else self.cx()
        if info is None or not info[0] + 10 < at < info[1] - 10 or self.cfg["dnd"]                 or now > c["until"] or self.player.base not in CEILING_BASES:
            return self.release_ceiling()
        x0, _x1, bottom = info
        if x0 != c["x0"] or bottom != c["bottom"]:
            if c.get("single"):
                c["pivot"] = [c["pivot"][0] + x0 - c["x0"], bottom]
            else:
                self.move_to(self.x + x0 - c["x0"], bottom - sprite.BY * self.pix)
            c["x0"], c["bottom"] = x0, bottom

    def dangling(self):
        return self.phys == "ceiling" and bool(self.ceil and self.ceil.get("single"))

    def dangle_step(self, c):
        dt = TICK_MS / 1000
        now = time.time()
        length = self.hang_length()
        if now > c["nudge"]:
            self.omega += random.choice((-1, 1)) * random.uniform(0.8, 1.5)
            c["nudge"] = now + random.uniform(2.5, 4.5)
        alpha = -(0.35 * GRAVITY / length) * math.sin(self.theta) - 0.9 * self.omega
        self.omega += alpha * dt
        self.theta = max(-1.0, min(1.0, self.theta + self.omega * dt))
        angle = int(round(math.degrees(self.theta) / 4) * 4)
        image, region, r = self.hang_frame(int(now * 3) % 6, angle)
        size = (2 * r + 1) * self.pix
        if self.view.width() != size:
            self.view.setFixedSize(size, size)
        self.view.set_frame(image, region)
        px, py = c["pivot"]
        off = round((r + 0.5) * self.pix)
        self.view.move(round(px) - off, round(py) - off)
        self.x = px + length * math.sin(self.theta) - CENTER_X * self.pix
        self.y = py + length * math.cos(self.theta) - (sprite.BY + 4.5) * self.pix

    def leave_dangle(self):
        c = self.ceil
        length = self.hang_length()
        px, py = c["pivot"]
        vx = length * self.omega * math.cos(self.theta)
        vy = -length * self.omega * math.sin(self.theta)
        c["single"] = False
        self.view.setFixedSize(sprite.CW * self.pix, sprite.CH * self.pix)
        self.move_to(px + length * math.sin(self.theta) - CENTER_X * self.pix,
                     py + length * math.cos(self.theta) - (sprite.BY + 4.5) * self.pix)
        self.cache.clear()
        return max(-1500, min(1500, vx)), max(-1500, min(1500, vy))

    def release_ceiling(self):
        self.ceil_timer.stop()
        vx = vy = 0.0
        if self.dangling():
            vx, vy = self.leave_dangle()
        self.ceil = None
        if self.phys == "ceiling":
            self.phys = "rest"
            self.fall(vx, vy)

    def wander_window(self):
        """Go to another window: jump if it is close, otherwise climb up its side."""
        here = self.perch[0] if self.perch else None
        margin = HALF_W * self.pix
        cx, feet = self.cx(), self.feet()
        jumps, climbs = [], []
        for s in self.get_surfaces(fresh=True, icons=True):
            if s.hwnd == here:
                continue
            for x in range(int(s.x0 + margin), int(s.x1 - margin), 40):
                if abs(x - cx) > 1100 or not self.fits(s, x):
                    continue
                if s.y >= feet - MAX_JUMP_UP and abs(x - cx) <= 900:
                    jumps.append((s, x))
            if self.perch is None and not s.icon and s.y < feet - MAX_JUMP_UP + 40:
                for left in (True, False):
                    x = s.x0 + margin + 30 if left else s.x1 - margin - 30
                    if abs(x - cx) <= 1400 and self.fits(s, x):
                        plan = self.climb_up_plan(s, x, left)
                        if plan:
                            climbs.append((s, x, plan))
        if any(not s.icon for s, _ in jumps) or climbs:
            if random.random() > 0.2:
                jumps = [j for j in jumps if not j[0].icon]
        if climbs and (not jumps or random.random() < 0.7):
            s, x, plan = random.choice(climbs)
            self.anchor_cx = x
            self.wandering = True
            self.run_plan(plan)
            return True
        if jumps:
            s, x = random.choice(jumps)
            self.anchor_cx = x
            self.wandering = True
            if random.random() < 0.35:
                self.wander_chain = random.randint(1, 2)
            self.run_plan([("hop", (x, s.y, s))])
            return True
        return False

    def schedule_wander(self):
        if self.perch:
            self.wander_timer.start(random.randint(9000, 22000))
        else:
            self.wander_timer.start(random.randint(20000, 45000))

    def trip_home(self):
        self.schedule_trip()
        if self.cfg["trips_home"] and self.can_roam() and not self.at_home() and not self.cfg.get("mini"):
            self.go_home()

    def schedule_trip(self):
        self.trip_timer.start(random.randint(180000, 420000))

    def go_home(self):
        if self.phys == "ceiling":
            self.release_ceiling()
            return QTimer.singleShot(1200, self.go_home)
        if self.hanging or self.phys in ("swim", "climb"):
            return
        if self.cfg.get("mini"):
            return self.place_mini()
        self.homing, self.route_hops = True, 0
        self.plan = []
        if self.phys == "air":
            return
        if self.at_home():
            return self.arrived_home()
        self.step_home()

    def step_home(self):
        """Hop and climb home: window tops first, climb down high windows, hop along the floor.
        Swimming is only the last resort (other screen, nothing to stand on)."""
        if not self.homing or self.phys != "rest":
            return
        if self.at_home():
            return self.arrived_home()
        hx, hy = self.home()
        cx, feet = self.cx(), self.feet()
        self.route_hops += 1
        if self.route_hops > 14:
            return self.start_swim(hx, hy)
        dist_now = abs(cx - hx)
        margin = HALF_W * self.pix
        best, best_score = None, 0
        if self.cfg["sit_on_windows"] and dist_now > 200:
            here = self.perch[0] if self.perch else None
            for s in self.get_surfaces(fresh=True):
                if s.hwnd == here or s.y < feet - MAX_JUMP_UP + 80:
                    continue
                for x in range(int(s.x0 + margin), int(s.x1 - margin) + 1, 30):
                    progress = dist_now - abs(x - hx)
                    hop = math.hypot(x - cx, s.y - feet)
                    if progress >= 110 and hop <= 600 and self.fits(s, x):
                        score = progress - 0.15 * abs(s.y - feet)
                        if score > best_score:
                            best, best_score = (s, x), score
        if best:
            s, x = best
            return self.run_plan([("hop", (x, s.y, s))])
        home_surface = surfaces.Surface(None, hx - 30, hx + 30, hy)
        if math.hypot(hx - cx, hy - feet) <= 600 and hy >= feet - MAX_JUMP_UP + 80:
            return self.run_plan([("hop", (hx, hy, home_surface))])
        floor = self.area().bottom() + 1
        if self.perch and floor - feet > 300:
            down = self.climb_down_plan(hx)
            if down:
                return self.run_plan(down)
        same_floor = abs(feet - floor) <= 2 and self.screen_at(hx, hy - 4) == self.screen_at(cx, feet - 4)
        if same_floor:
            step = max(-320, min(320, hx - cx))
            return self.run_plan([("hop", (cx + step, floor, surfaces.Surface(None, cx + step - 30,
                                                                                cx + step + 30, floor)))])
        if self.perch:
            return self.run_plan([("hop", (cx + max(-300, min(300, hx - cx)), floor, None))])
        self.start_swim(hx, hy)

    def start_swim(self, tx, t_feet):
        """Float like a jellyfish along a smooth arc (used for long or blocked ways home)."""
        self.tick.stop()
        x0, y0 = self.cx(), self.feet()
        dist = math.hypot(tx - x0, t_feet - y0)
        lift = 70 + 0.25 * dist
        top = max(self.area().top() + (FEET - sprite.BY + 4) * self.pix, min(y0, t_feet) - lift)
        self.swim = {"p0": (x0, y0), "p1": ((x0 + tx) / 2, top), "p2": (tx, t_feet), "t": 0.0,
                     "dur": max(1.4, dist / 240)}
        self.phys, self.perch = "swim", None
        self.player.force("swim")
        self.swim_timer.start(TICK_MS)

    def swim_step(self):
        sw = self.swim
        if sw is None or self.phys != "swim":
            self.swim_timer.stop()
            return
        sw["t"] = min(1.0, sw["t"] + TICK_MS / 1000 / sw["dur"])
        t = sw["t"]
        e = t * t * (3 - 2 * t)
        (x0, y0), (x1, y1), (x2, y2) = sw["p0"], sw["p1"], sw["p2"]
        cx = (1 - e) ** 2 * x0 + 2 * (1 - e) * e * x1 + e * e * x2
        feet = (1 - e) ** 2 * y0 + 2 * (1 - e) * e * y1 + e * e * y2
        feet += math.sin(t * math.pi * 6) * 3 * (1 - t)
        self.move_to(cx - CENTER_X * self.pix, feet - FEET * self.pix)
        if t >= 1.0:
            self.swim_timer.stop()
            self.swim = None
            self.land(surfaces.Surface(None, x2 - 40, x2 + 40, y2))

    def set_home_here(self):
        bed = house_mod.BED_H * self.pix if self.cfg["show_house"] else 0
        self.cfg.set("home", [round(self.cx()), round(self.feet())])
        self.move_to(self.x, self.y - bed)
        self.anchor_cx = self.cx()
        self.refresh_house()
        self.player.once("happy")

    def save_position(self):
        self.cfg.set("position", [round(self.x), round(self.y)])

    # ------------------------------------------------------------ mouse: grab, hang, throw
    def grab(self, gpos):
        self.wake()
        if self.cfg.get("mini"):
            self.cfg.set("mini", False)
            self.refresh_house()
            QTimer.singleShot(0, self.build_menu)
        self.press = (gpos, time.time())
        self.homing = False
        self.water_phase = None
        self.plan = []
        if self.phys == "climb":
            self.climb_timer.stop()
            self.climb = None
            self.phys = "air"
            self.vx = self.vy = 0.0
        if self.phys == "swim":
            self.swim_timer.stop()
            self.swim = None
            self.phys = "air"
            self.vx = self.vy = 0.0
        if self.phys == "ceiling":
            self.ceil_timer.stop()
            if self.dangling():
                self.leave_dangle()
            self.ceil = None
            self.phys = "air"
            self.vx = self.vy = 0.0
        self.ceil_goal = None
        if self.phys == "air":
            self.tick.stop()

    def drag(self, gpos):
        if self.press is None or self.hanging:
            return
        if (gpos - self.press[0]).manhattanLength() >= 5:
            self.start_hang(gpos)

    def start_hang(self, gpos):
        self.hanging = True
        self.phys, self.perch = "held", None
        self.theta, self.omega = random.choice((-0.2, 0.2)), 0.0
        self.cur_hist, self._last_vx = [(time.time(), gpos.x(), gpos.y())], 0.0
        self.player.force("held")
        self.badge.hide()
        self.hang_step()
        self.hang_timer.start(TICK_MS)

    def hang_frame(self, phase, angle):
        gear, outfit = self.gear(), self.current_outfit()
        weather = self.weather.kind if self.cfg["weather"] else None
        key = (phase, angle, self.pix, self.skin_key(), gear, outfit, weather)
        if key not in self.hang_cache:
            dressed = sprite.Pose()
            if gear != (None, False, False):
                dressed = sprite.with_gear(dressed, *gear)
            dressed = sprite.with_weather(sprite.with_outfit(dressed, outfit), weather, inv=True)
            img, (px, py) = sprite.hang_image(phase, self.skin_pal(), dressed)
            r = int(math.ceil(max(math.hypot(x - px + 0.5, y - py + 0.5) for x in (0, img.width) for y in
                                  (0, img.height)))) + 1
            canvas = Image.new("RGBA", (2 * r + 1, 2 * r + 1), (0, 0, 0, 0))
            canvas.alpha_composite(img, (r - px, r - py))
            rot = canvas.rotate(angle, resample=Image.NEAREST, center=(r + 0.5, r + 0.5))
            dpr = self.view.devicePixelRatioF() or 1.0
            dev = max(1, round(self.pix * dpr))
            big = rot.resize((rot.width * dev, rot.height * dev), Image.NEAREST)
            small = rot.resize((rot.width * self.pix, rot.height * self.pix), Image.NEAREST)
            self.hang_cache[key] = (to_qimage(big, dev / self.pix), alpha_region(small), r)
        return self.hang_cache[key]

    def hang_length(self):
        return (sprite.GRAB_LEN + 4.5) * self.pix

    def hang_step(self):
        if not self.hanging:
            return
        now = time.time()
        c = QCursor.pos()
        self.cur_hist = [h for h in self.cur_hist if now - h[0] < 0.15] + [(now, c.x(), c.y())]
        dt = TICK_MS / 1000
        vx_now = self.cursor_velocity()[0]
        ax = max(-20000, min(20000, (vx_now - self._last_vx) / dt))
        self._last_vx = vx_now
        length = self.hang_length()
        alpha = (-(GRAVITY / length) * math.sin(self.theta) - 3.4 * self.omega
                 - 0.6 * (ax / length) * math.cos(self.theta))
        self.omega += alpha * dt
        self.theta = max(-1.2, min(1.2, self.theta + self.omega * dt))
        angle = int(round(math.degrees(self.theta) / 4) * 4)
        image, region, r = self.hang_frame(int(now * 7) % 6, angle)
        size = (2 * r + 1) * self.pix
        if self.view.width() != size:
            self.view.setFixedSize(size, size)
        self.view.set_frame(image, region)
        off = round((r + 0.5) * self.pix)
        self.view.move(c.x() - off, c.y() - off)

    def cursor_velocity(self):
        if len(self.cur_hist) < 2:
            return 0.0, 0.0
        (t0, x0, y0), (t1, x1, y1) = self.cur_hist[0], self.cur_hist[-1]
        dt = max(t1 - t0, 1e-3)
        return (x1 - x0) / dt, (y1 - y0) / dt

    def stop_hang(self):
        self.hang_timer.stop()
        self.hanging = False
        c = QCursor.pos()
        length = self.hang_length()
        bx = c.x() + length * math.sin(self.theta)
        by = c.y() + length * math.cos(self.theta)
        vx, vy = self.cursor_velocity()
        vx += length * self.omega * math.cos(self.theta)
        vy -= length * self.omega * math.sin(self.theta)
        self.view.setFixedSize(sprite.CW * self.pix, sprite.CH * self.pix)
        self.move_to(bx - CENTER_X * self.pix, by - (sprite.BY + 4.5) * self.pix)
        self.badge_update()
        return max(-2600, min(2600, vx)), max(-2600, min(2600, vy))

    def drop(self):
        if self.press is None:
            return
        self.press = None
        if not self.hanging:
            if self.phys == "rest":
                self.poke()
            elif self.phys == "air":
                self.tick.start(TICK_MS)
            return
        vx, vy = self.stop_hang()
        self.render()
        self.anchor_cx = None
        if not self.cfg["gravity"]:
            self.phys = "rest"
            self.keep_on_screen()
            self.player.release("land")
            self.save_position()
            return
        if math.hypot(vx, vy) < 700:
            s = self.snap_target()
            if s is not None:
                return self.land(s)
        now = time.time()
        self.bump("throws")
        if math.hypot(vx, vy) > 3200:
            self.bump("yeets")
        if math.hypot(vx, vy) > 1500:
            self.throws = [t for t in self.throws if now - t < 25] + [now]
            if len(self.throws) >= 3:
                self.throws = []
                self.after_land = "angry"
        self.fall(vx, vy)

    def poke(self):
        now = time.time()
        self.clicks = [t for t in self.clicks if now - t < 3.5] + [now]
        self.sfx("poke")
        self.bump("pokes")
        if len(self.clicks) >= 7:
            self.clicks = []
            self.sfx("angry")
            self.bump("angry")
            self.player.once("angry")
        elif len(self.clicks) == 4:
            self.player.once("dizzy")
            self.bump("dizzy")
        elif len(self.clicks) < 4 and not self.player.busy and self.player.base not in WORK:
            self.player.once("happy")

    def check_stroke(self, c, now):
        p = self.pix
        x0, x1 = self.x + BODY_X0 * p, self.x + BODY_X1 * p
        head = (self.y + (sprite.BY - 1) * p, self.y + (sprite.BY + 5) * p)
        legs = (self.y + (sprite.BY + 8) * p, self.y + (sprite.FEET + 1) * p)
        zone = None
        if x0 <= c.x() <= x1 and not self.hanging and self.press is None and self.phys == "rest":
            zone = "head" if head[0] <= c.y() <= head[1] else "legs" if legs[0] <= c.y() <= legs[1] else None
        if zone is None:
            self.strokes = []
            return
        self.strokes = [s for s in self.strokes if now - s[0] < 1.6 and s[2] == zone] + [(now, c.x(), zone)]
        turns, last_dir, anchor = 0, 0, self.strokes[0][1]
        for _t, x, _z in self.strokes[1:]:
            if abs(x - anchor) >= 2 * p:
                d = 1 if x > anchor else -1
                if last_dir and d != last_dir:
                    turns += 1
                last_dir, anchor = d, x
        if turns >= 3 and now - self.last_stroke > 6 and not self.player.busy and not self.cfg["dnd"]:
            self.last_stroke = now
            self.strokes = []
            self.hover_since = None
            self.last_shy = now
            if zone == "legs":
                self.bump("tickles")
                self.player.once("tickled")
            else:
                self.bump("pets")
                self.player.once("petted")

    def follow_eyes(self):
        c = QCursor.pos()
        body = QRect(round(self.x + BODY_X0 * self.pix), round(self.y + sprite.BY * self.pix),
                     (BODY_X1 - BODY_X0) * self.pix, 12 * self.pix)
        now = time.time()
        self.check_stroke(c, now)
        if body.contains(c) and not self.hanging and self.press is None:
            self.hover_since = self.hover_since or now
            if (self.cfg["react_hover"] and now - self.hover_since > 0.8 and now - self.last_shy > 25
                    and not self.player.busy and self.player.base in AMBIENT and self.phys == "rest"
                    and not self.cfg["dnd"]):
                self.last_shy = now
                self.player.once("shy")
        else:
            self.hover_since = None
        if (self.hover_since is not None) != self.badge_hover:
            self.badge_hover = self.hover_since is not None
            self.badge_update()
        if not self.cfg["eyes_follow"]:
            return
        ex0 = self.x + (sprite.BX + 8) * self.pix
        ey0 = self.y + (sprite.BY + 5) * self.pix
        dx, dy = c.x() - ex0, c.y() - ey0
        thr = 30 * self.pix / 4
        ex = 0 if abs(dx) < thr else (1 if dx > 0 else -1)
        ey = 0 if abs(dy) < thr else (1 if dy > 0 else -1)
        if math.hypot(dx, dy) > 900:
            ex = ey = 0
        if (ex, ey) != self.eyes:
            self.eyes = (ex, ey)
            self.render()

    # ------------------------------------------------------------ ambient (PC) states
    def hidden_for_game(self):
        return self.game_hidden

    def music_on(self):
        if not self.cfg["react_music"]:
            return False
        return self.monitor.spotify or (self.cfg["beat_sync"] and self.beats.playing)

    def sync_beats(self):
        want = bool(self.cfg["react_music"] and self.cfg["beat_sync"])
        if want and not self.beats.running:
            self.beats.start()
        elif not want and self.beats.running:
            self.beats.stop()
        self.player.beat_driven = want

    def ambient(self):
        m = self.monitor
        d = self.discord.state
        if self.cfg.get("mini"):
            return "sleeping" if self.cfg["dnd"] else "peek"
        if self.cfg["dnd"] or m.locked:
            return "sleeping"
        if self.cfg["react_network"] and not m.online:
            return "offline"
        if self.cfg["react_battery"] and m.battery_low:
            return "battery_low"
        if self.cfg["discord"] and d["in_call"]:
            return "call_deaf" if d["deaf"] else "call_muted" if d["mute"] else "call"
        if self.focus.phase == "focus":
            return "focus"
        if self.music_on():
            return "music"
        if self.cfg["react_cpu"] and m.hot:
            return "hot"
        mins = self.cfg["sleep_after_min"]
        if mins and m.idle_s > mins * 60:
            return "sleeping"
        return "idle"

    def night_owl(self):
        today = time.strftime("%Y-%m-%d")
        if 2 <= time.localtime().tm_hour < 5 and self.monitor.idle_s < 120 and getattr(self, "_owl_day", None) != today:
            self._owl_day = today
            self.bump("night_owl")

    def break_nudge(self):
        """After a long stretch of activity, suggest a short break (stretch, drink water)."""
        now = time.time()
        if self.monitor.idle_s > 300 or self.monitor.locked:
            self.active_since = now
            return
        start = getattr(self, "active_since", None) or now
        self.active_since = start
        if not self.cfg.get("break_nudge") or now - start < 75 * 60 or self.quiet_mode():
            return
        if self.interactive or self.info or self.player.busy or self.player.base not in ROAM_BASES:
            return
        self.active_since = now
        mins = int((now - start) // 60)
        self.bump("breaks")
        self.set_info({"kind": "wait", "chip": "Break", "text": f"You've been at it for {mins} minutes. "
                       "Stretch a little and drink some water?", "buttons": [("Will do!", "ok", True)]})
        self.done_timer.start(DONE_MS)
        self.player.once("stretch")

    def update_ambient(self):
        self.break_nudge()
        self.night_owl()
        if self.player.base == "exhausted" and time.time() - getattr(self, "exhausted_at", 0) > 60:
            fresh = [pct for lim in self.usage.latest.values() for pct, _r in lim.values()]
            if fresh and max(fresh) < 99:
                self.on_limit_over()
        game = bool(self.cfg["game_mode"] and self.monitor.fullscreen)
        if game != self.game_hidden:
            self.game_hidden = game
            visible = getattr(self, "_visible", True) and not game
            self.view.setVisible(visible)
            self.house.setVisible(visible and self.cfg["show_house"])
            if game:
                self.bubble.hide()
                self.badge.hide()
            else:
                self.refresh_bubble()
                self.badge_update()
                self.view.raise_()
        if self.interactive or self.player.base not in AMBIENT:
            return
        want = self.ambient()
        if want != self.player.base:
            self.player.set_base(want)
        if (want == "idle" and self.cfg["react_night"] and self.monitor.night and not self.player.busy
                and time.time() - self.last_yawn > 600 and random.random() < 0.05):
            self.last_yawn = time.time()
            self.player.once("yawn")

    def fidget(self):
        self.schedule_fidget()
        if (self.cfg["fidgets"] and self.phys == "rest" and self.player.base == "idle" and not self.player.busy
                and not self.bubble.isVisible() and not self.homing and self.water_phase is None
                and not self.cfg["dnd"]):
            if self.at_home() and self.cfg["show_house"] and self.cfg["auto_water"] and random.random() < 0.1:
                return self.arrived_home()
            weather = self.weather.kind if self.cfg["weather"] else None
            if weather and random.random() < 0.3:
                return self.player.once(WEATHER_ANIM.get(weather, "cloudy"))
            self.player.once(random.choice(FIDGETS))

    def schedule_fidget(self):
        self.fidget_timer.start(random.randint(18000, 40000))

    def on_pc(self, kind):
        if kind == "locked" and self.cfg["react_lock"]:
            self.update_ambient()
            return
        if self.player.busy or self.interactive or self.player.base not in AMBIENT or self.cfg["dnd"]:
            return
        if kind in ("user_back", "unlocked") and (self.cfg["react_greet"] or self.cfg["react_lock"]):
            self.player.base = "idle"
            self.player.once("hello")
            if self.cfg.get("todo_greet") and self.todos.open_items() and kind == "user_back":
                QTimer.singleShot(2500, self.todo_nudge)
        elif kind == "plugged" and self.cfg["react_battery"]:
            self.player.once("zap")
        elif kind == "online_again" and self.cfg["react_network"]:
            self.player.once("happy")

    def todo_nudge(self):
        if not self.interactive and not self.info and not self.cfg["dnd"] and not self.hidden_for_game():
            self.todo_summary()
            QTimer.singleShot(12000, lambda: self.set_info(None) if self.info and self.info.get(
                "kind") == "todo" else None)

    def idle_base(self):
        return self.ambient()

    def wake(self):
        if self.player.base == "sleeping" and not self.cfg["dnd"]:
            self.player.set_base("idle")

    # ------------------------------------------------------------ focus timer
    def toggle_focus(self):
        self.focus.toggle()
        if self.info and self.info.get("kind") == "focus":
            self.set_info(None, force=True)
        self.update_ambient()

    def start_break(self):
        self.focus.start("break")
        if self.info and self.info.get("kind") == "focus":
            self.set_info(None, force=True)
        self.update_ambient()
        QTimer.singleShot(0, self.build_menu)

    def on_focus_tick(self):
        self.badge_update()
        if self.focus.phase != self._focus_phase_seen:
            self._focus_phase_seen = self.focus.phase
            QTimer.singleShot(0, self.build_menu)

    def on_focus_end(self, phase):
        if phase == "focus":
            self.bump("focus_rounds")
        if self.player.base == "focus":
            self.player.base = self.ambient()
        self.player.once("alarm")
        self.notify_sound("alarm")
        if phase == "focus":
            spec = {"kind": "focus", "chip": "Focus", "text": f"Great work! Time for a {self.cfg['break_min']} "
                                                              f"minute break.",
                    "buttons": [("Start break", "break_start", True), ("Keep going", "focus_start", False),
                                ("Stop", "focus_stop", False)]}
        else:
            spec = {"kind": "focus", "chip": "Break over", "text": "Ready for the next focus round?",
                    "buttons": [("Start focus", "focus_start", True), ("Stop", "focus_stop", False)]}
        self.add_history("Focus", spec["chip"], spec["text"])
        self.set_info(spec, force=True)
        self.update_ambient()

    # ------------------------------------------------------------ toys
    def give_snack(self):
        if self.cfg.get("mini"):
            self.leave_mini()
        a = self.area()
        x = max(a.left(), min(self.cx() + random.choice((-1, 1)) * random.randint(60, 160), a.right() - 30))
        self.snacks.append(toys.Toy(self, "snack", x, a.top() + 20, 0, 0))

    def throw_ball(self):
        if self.ball is not None:
            self.ball.remove()
        self.ball = toys.spawn_near_cursor(self, "ball")
        self.ball_touched = time.time()
        if not hasattr(self, "ball_timer"):
            self.ball_timer = QTimer(self, timeout=self.ball_check)
        self.ball_timer.start(5000)
        QTimer.singleShot(0, self.build_menu)

    def ball_check(self):
        if self.ball is None:
            return self.ball_timer.stop()
        if self.carrying or self.fetch is self.ball:
            return
        if time.time() - getattr(self, "ball_touched", 0) > BALL_IDLE_S:
            self.put_ball_away()

    def put_ball_away(self):
        if self.ball is not None:
            self.ball.remove()
            self.ball = None
        if self.carrying:
            self.carrying = False
            self.cache.clear()
            self.render()
        if self.fetch is not None and self.fetch.kind == "ball":
            self.fetch = None
        QTimer.singleShot(0, self.build_menu)

    def toy_thrown(self, toy):
        if toy is self.ball:
            self.ball_touched = time.time()
        if self.fetch is toy:
            self.fetch = None
            self.plan = []

    def toy_rested(self, toy):
        QTimer.singleShot(600, lambda: self.go_get(toy))

    def go_get(self, toy):
        if toy not in self.snacks and toy is not self.ball:
            return
        if not toy.resting or self.hanging or self.carrying or self.phys != "rest" or self.player.busy:
            return QTimer.singleShot(1500, lambda: self.go_get(toy))
        if self.cfg["dnd"] or self.cfg.get("mini") or self.interactive:
            return QTimer.singleShot(5000, lambda: self.go_get(toy))
        self.fetch = toy
        self.homing = False
        self.reach_toy()

    def reach_toy(self):
        toy = self.fetch
        if toy is None or self.phys != "rest":
            return
        if not toy.resting:
            return QTimer.singleShot(500, self.reach_toy)
        tx, ty = toy.center()
        if abs(tx - self.cx()) < 26 * self.pix / 4 and abs(ty - self.feet()) < 30:
            return self.grab_toy()
        plan = self.route_to(tx, ty, toy.support)
        if plan is None:
            self.fetch = None
            return
        self.run_plan(plan)

    def route_to(self, tx, ty, hwnd=None):
        """Next steps towards point (tx, ty): jump, climb up a window, climb down, or hop along."""
        cx, feet = self.cx(), self.feet()
        margin = HALF_W * self.pix
        if ty < feet - 20:
            s = next((w for w in self.get_surfaces(fresh=True) if w.hwnd == hwnd), None) if hwnd else None
            if s is None:
                return None
            x = max(s.x0 + margin, min(s.x1 - margin, tx))
            if ty >= feet - MAX_JUMP_UP and abs(x - cx) <= 900:
                return [("hop", (x, s.y, s))]
            return self.climb_up_plan(s, x)
        if ty > feet + 20 and self.perch:
            down = self.climb_down_plan(tx)
            if down and ty - feet > 300:
                return down
            return [("hop", (cx + max(-300, min(300, tx - cx)), ty, None))]
        step = max(-280, min(280, tx - cx))
        nx = cx + step
        here = next((w for w in self.get_surfaces() if self.perch and w.hwnd == self.perch[0]), None)
        if here is not None:
            nx = max(here.x0 + margin, min(here.x1 - margin, nx))
            return [("hop", (nx, feet, here))]
        return [("hop", (nx, feet, surfaces.Surface(None, nx - 30, nx + 30, feet)))]

    def grab_toy(self):
        toy, self.fetch = self.fetch, None
        if toy.kind == "snack":
            self.snacks.remove(toy)
            toy.remove()
            self.player.once("snack")
            self.bump("snacks")
            return
        toy.hide()
        toy.resting = True
        self.carrying = True
        self.cache.clear()
        self.render()
        QTimer.singleShot(500, self.bring_ball)

    def bring_ball(self):
        if not self.carrying or self.phys != "rest":
            return QTimer.singleShot(400, self.bring_ball)
        c = QCursor.pos()
        if abs(c.x() - self.cx()) > 60 * self.pix / 4 and getattr(self, "bring_hops", 0) < 8:
            self.bring_hops = getattr(self, "bring_hops", 0) + 1
            floor = self.area().bottom() + 1
            plan = self.route_to(c.x(), floor if self.perch else self.feet())
            if plan:
                self.run_plan(plan)
                return QTimer.singleShot(1200, self.bring_ball)
        self.bring_hops = 0
        self.drop_ball()

    def drop_ball(self):
        self.ball_touched = time.time()
        self.carrying = False
        self.cache.clear()
        self.render()
        if self.ball is not None:
            self.ball.x, self.ball.y = self.cx() + 6 * self.pix, self.y + sprite.BY * self.pix
            self.ball.move(round(self.ball.x), round(self.ball.y))
            self.ball.show()
            self.ball.throw(random.choice((-1, 1)) * 150, -500)
        self.bump("fetches")
        self.player.once("happy")

    # ------------------------------------------------------------ reminders
    def add_reminder(self):
        from smellyfish.ui.gallery import ReminderDialog
        dlg = ReminderDialog(self)
        if dlg.exec():
            text, minutes = dlg.values()
            if text:
                items = list(self.cfg.get("reminders") or [])
                items.append({"text": text, "due": time.time() + minutes * 60})
                self.cfg.set("reminders", items)
                self.player.once("happy")
                QTimer.singleShot(0, self.build_menu)

    def check_reminders(self):
        self.check_todos()
        items = list(self.cfg.get("reminders") or [])
        now = time.time()
        due = [r for r in items if r["due"] <= now]
        if not due:
            return
        self.cfg.set("reminders", [r for r in items if r["due"] > now])
        for r in due:
            self.add_history("Reminder", "Reminder", r["text"])
            if self.cfg["dnd"] or self.hidden_for_game():
                self.unseen += 1
                self.badge_update()
                continue
            self.notify_sound("alarm")
            spec = {"kind": "reminder", "chip": "Reminder", "text": r["text"],
                    "buttons": [("Done", "ok", True), ("Snooze 5 min", "snooze", False)], "_text": r["text"]}
            self.set_info(spec, force=True)
            if self.phys == "rest" and not self.hanging:
                self.player.once("reminder")
        QTimer.singleShot(0, self.build_menu)

    # ------------------------------------------------------------ what's new
    def check_whats_new(self):
        """After an update, offer the release notes once (not on a fresh install, not while quiet)."""
        seen = self.cfg.get("seen_version") or ""
        if seen == __version__:
            return
        if not seen and getattr(self.cfg, "fresh", False):
            return self.cfg.set("seen_version", __version__)
        if self.quiet_mode() or self.interactive:
            return
        self.updated_from = seen or "1.3.1"
        self.cfg.set("seen_version", __version__)
        from smellyfish.changelog import since
        news = since(self.updated_from, __version__)
        title = news[0]["title"] if news else "Small improvements"
        self.add_history("Smellyfish", "Updated", f"Now running v{__version__}: {title}")
        self.notice({"kind": "trophy", "chip": "Updated", "right": f"v{__version__}", "text": title,
                     "buttons": [("What's new", "whats_new", True), ("OK", "ok", False)]}, seconds=0)
        if self.phys == "rest" and not self.hanging:
            self.player.once("happy")

    def open_changelog(self, since_version=None):
        win = self._open("changelog_win", ChangelogWindow)
        if since_version:
            win.show_since(since_version)

    # ------------------------------------------------------------ to-do list
    # ------------------------------------------------------------ LAN lobby
    def lan_name(self):
        name = self.cfg.get("lan_name")
        if not name:
            name = "Jelly" + str(random.randint(10, 99))
            self.cfg.set("lan_name", name)
        return name

    def lan_color(self):
        c = self.cfg.get("skin_color") or "#c492ec"
        if self.cfg.get("skin") != "custom":
            rgb = (sprite.SKINS.get(self.cfg.get("skin") or "lavender") or {}).get("#", (196, 146, 236))
            c = "#%02x%02x%02x" % tuple(rgb)
        return c

    def open_lobby(self):
        self._open("lobby_win", LobbyWindow)

    def lan_look(self):
        headset = self.gear()[0]
        return {"o": self.current_outfit(), "w": self.weather.kind if self.cfg["weather"] else None,
                "h": "mic" if headset == "mic" else None, "b": self.focus.phase == "focus"}

    def on_lan_visit(self, name, color, look=None):
        if not self.cfg.get("lan_visits"):
            return
        self.add_history(name, "Visit", f"{name} came by")
        if self.quiet_mode():
            return self.missed(name, "Visit", f"{name} came by")
        self.guests.add(name, color, None, look)

    def on_lan_letter(self, name, color, text, look=None):
        self.add_history(name, "Letter", text)
        if not self.cfg.get("lan_letters"):
            return
        if self.quiet_mode():
            return self.missed(name, "Letter", text)
        if not self.guests.add(name, color, text, look):
            self.missed(name, "Letter", text)

    def deliver_letter(self, name, text):
        self.bump("letters")
        if self.phys == "rest" and not self.player.busy and not self.hanging:
            self.player.once("mail")
        self.notice({"kind": "done", "chip": "Letter", "right": name, "text": text,
                     "buttons": [("Reply", ("lan_reply", name), True), ("OK", "ok", False)]},
                    seconds=max(12, min(45, len(text) // 8)))
        self.notify_sound("message")

    def queue_send(self, kind, **fields):
        """A letter or visit that hit the cooldown goes out by itself as soon as it is over."""
        if len(self.pending_sends) >= 5:
            return False
        self.pending_sends.append((kind, fields))
        if not self.send_timer.isActive():
            self.send_timer.start(500)
        return True

    def flush_sends(self):
        for item in list(self.pending_sends):
            kind, fields = item
            result = self.lan.send(kind, **fields)
            if result.startswith("Wait"):
                continue
            self.pending_sends.remove(item)
            label = "Letter" if kind == "letter" else "Visit"
            self.notice({"kind": "wait", "chip": "Lobby", "text": f"{label} sent." if not result else
                         f"{label} not sent: {result}"}, seconds=4)
        if not self.pending_sends:
            self.send_timer.stop()

    def quick_letter(self, to_name=None):
        if self.lan.role is None:
            return
        dlg = QuickSend(self, "letter", to_name)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self.quick_dialog = dlg

    def quick_visit(self):
        if self.lan.role is None:
            return
        dlg = QuickSend(self, "visit")
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self.quick_dialog = dlg

    def on_lan_chat(self, name, text):
        if self.lan.me is not None and name == self.lan.me.name:
            return
        self.add_history(name, "Lobby", text)
        if self.lobby_win is not None and self.lobby_win.isActiveWindow():
            return
        self.mail_until = time.time() + MAIL_S
        self.badge_update()
        QTimer.singleShot(MAIL_S * 1000 + 200, self.badge_update)
        if self.quiet_mode():
            self.unseen += 1
            return self.badge_update()
        if self.interactive or (self.info and self.info.get("kind") == "focus"):
            return
        spec = {"kind": "discord", "chip": "Lobby", "right": name, "text": text, "max_lines": 4,
                "buttons": [("Open lobby", "lan_open", True), ("OK", "ok", False)]}
        self.set_info(spec)
        self.notify_sound("message")
        if not self.player.busy and self.player.base in AMBIENT:
            self.player.once("mail")
        QTimer.singleShot(9000, lambda: self.set_info(None) if self.info is spec else None)

    # ------------------------------------------------------------ local model
    def llm_status(self):
        if not self.cfg.get("llm_enabled"):
            return "Local model is off (see Settings)."
        if not self.cfg.get("llm_model"):
            return "Pick a model in the settings."
        if self.llm_phase:
            state = LLM_PHASES[self.llm_phase].lower() + "..."
        else:
            state = "loaded and ready" if self.llm.loaded else "sleeping, wakes up when you ask"
        return f"{self.cfg['llm_model']} ({state})"

    def llm_ready(self):
        if self.llm.enabled():
            return True
        self.notice({"kind": "wait", "chip": "Chat", "text": "Turn on the local model and pick one in "
                     "the settings first.", "buttons": [("Settings", "settings", True), ("OK", "ok", False)]},
                    seconds=0)
        return False

    def open_ask(self):
        if not self.llm_ready():
            return
        if self.ask_win is None:
            self.ask_win = AskWindow(self)
        self.llm.preload()
        self.ask_win.open()

    def open_chat(self):
        if self.llm_ready():
            self._open("chat_win", ChatWindow)

    def ask_llm(self, text):
        self.llm_started = time.time()
        self.llm_text = ""
        self.llm_phase = "loading" if not self.llm.loaded else "answering"
        self.chat_log += [("you", text), ("wait", LLM_PHASES[self.llm_phase])]
        del self.chat_log[:-60]
        if self.chat_win is not None:
            self.chat_win.render()
        if self.cfg.get("llm_reply") == "bubble":
            self.notice({"kind": "wait", "chip": "Smellyfish", "text": LLM_PHASES[self.llm_phase] + "..."},
                        seconds=0)
        self.player.set_base("ponder" if self.llm_phase == "loading" else "thinking")
        return self.llm.ask(text)

    def unload_llm(self):
        if self.llm.unload_now():
            self.notice({"kind": "wait", "chip": "Smellyfish", "text": "Model unloaded. It wakes up again when you ask."},
                        seconds=5)
        else:
            self.notice({"kind": "wait", "chip": "Smellyfish", "text": "Busy answering, try again in a moment."},
                        seconds=5)
        if self.chat_win is not None:
            self.chat_win.refresh()

    def on_llm_phase(self, rid, phase):
        if rid != self.llm.rid or self.llm_text:
            return
        self.llm_phase = phase
        self.player.set_base("ponder" if phase in ("starting", "loading") else "thinking")
        label = LLM_PHASES[phase]
        if self.chat_log and self.chat_log[-1][0] == "wait":
            self.chat_log[-1] = ("wait", label)
        if self.cfg.get("llm_reply") == "bubble" and self.info and self.info.get("chip") == "Smellyfish":
            self.set_info(dict(self.info, text=label + "..."), force=True)
        if self.chat_win is not None:
            self.chat_win.render()
            self.chat_win.refresh()

    def on_llm_chunk(self, rid, text):
        self.llm_text = text
        if self.chat_log:
            self.chat_log[-1] = ("bot", text)
        if self.chat_win is not None:
            self.chat_win.render()
        if self.cfg.get("llm_reply") == "bubble" and self.info and self.info.get("chip") == "Smellyfish"                 and time.time() - getattr(self, "llm_shown", 0) > 0.25:
            self.llm_shown = time.time()
            self.set_info(dict(self.info, text=bubble_safe(text)[-700:], md=True), force=True)

    def on_llm_done(self, rid, text, error):
        if rid != self.llm.rid:
            return
        self.llm.done()
        self.llm_phase = ""
        if self.player.base in ("ponder", "thinking") and not any(
                time.time() - self.sessions.get(sid, 0) < 600 for sid in self.prompt_time):
            self.player.set_base(self.idle_base())
        if self.chat_log:
            self.chat_log[-1] = ("bot", text or error or "...")
        if self.chat_win is not None:
            self.chat_win.render()
            self.chat_win.refresh()
        if self.cfg.get("llm_reply") != "bubble" and self.chat_win is not None and self.chat_win.isVisible():
            return
        shown = bubble_safe(text) or error or "..."
        if text:
            buttons = [("Chat", "llm_open", True), ("OK", "ok", False)]
        else:
            self.chat_log.append(("help", llm_guide(error, self.cfg.get("llm_model"))))
            buttons = [("Help", "llm_open", True), ("Settings", "settings", False)]
        self.notice({"kind": "done" if text else "wait", "chip": "Smellyfish", "text": shown, "md": bool(text),
                     "buttons": buttons}, seconds=max(10, min(60, len(shown) // 8)) if text else 0)
        self.notify_sound("message")
        if text and self.phys == "rest" and not self.player.busy and not self.hanging:
            self.player.once("happy")

    def open_todos(self):
        self._open("todo_win", TodoWindow)

    def quick_todo(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(None, "Smellyfish - New task", "Task:")
        if ok and text.strip():
            self.todo_add(text, None)

    def todos_changed(self):
        QTimer.singleShot(0, self.build_menu)
        self.badge_update()
        if self.todo_win is not None and self.todo_win.isVisible():
            self.todo_win.refresh()

    def todo_add(self, text, due):
        if self.todos.add(text, due):
            self.bump("todos_added")
            self.todos_changed()
            if self.phys == "rest" and not self.hanging and not self.cfg["dnd"]:
                self.player.once("happy")

    def todo_set_done(self, tid, done=True):
        t = self.todos.get(tid)
        if not t or not self.todos.set_done(tid, done):
            return
        self.todos_changed()
        if self.info and self.info.get("todo") == tid:
            self.set_info(None, force=True)
        if not done:
            return
        self.bump("todos_done")
        if not self.todos.open_items():
            self.bump("todo_clears")
            self.todo_all_done()
        elif self.phys == "rest" and not self.hanging and not self.cfg["dnd"]:
            self.player.once("checkoff")

    def todo_all_done(self):
        if self.cfg["dnd"] or self.hidden_for_game():
            return
        if not self.interactive and not (self.info and self.info.get("kind") == "focus"):
            self.set_info({"kind": "trophy", "chip": "To-do", "text": "Everything is done. Nice work!"})
            QTimer.singleShot(7000, lambda: self.set_info(None) if self.info and self.info.get(
                "kind") == "trophy" else None)
        if self.phys == "rest" and not self.hanging:
            self.player.once("trophy")

    def todo_delete(self, tid):
        self.todos.remove(tid)
        self.todos_changed()

    def todo_clear_done(self):
        self.todos.clear_done()
        self.todos_changed()

    def check_todos(self):
        due = self.todos.take_due()
        if not due:
            return
        for t in due:
            self.add_history("To-do", "Task due", t["text"])
        if self.cfg["dnd"] or self.hidden_for_game():
            self.unseen += len(due)
            self.badge_update()
            return
        t = due[0]
        more = f"\n(+{len(due) - 1} more due)" if len(due) > 1 else ""
        self.notify_sound("alarm")
        spec = {"kind": "reminder", "chip": "To-do", "text": t["text"] + more, "todo": t["id"],
                "buttons": [("Done", ("todo_done", t["id"]), True), ("Snooze 10 min", ("todo_snooze", t["id"]), False)]}
        self.set_info(spec, force=True)
        if self.phys == "rest" and not self.hanging:
            self.player.once("reminder")
        self.todos_changed()

    def todo_summary(self):
        """A bubble with the first open tasks (also after coming back to the PC)."""
        items = self.todos.open_items()
        if not items:
            self.notice({"kind": "wait", "chip": "To-do", "text": "Nothing to do. Add a task from the menu.",
                         "buttons": [("Open list", "todo_open", True)]}, seconds=0)
            return
        shown = items[:4]
        lines = [f"- {t['text']}" + (f" ({fmt_due(t['due'])})" if t["due"] else "") for t in shown]
        if len(items) > len(shown):
            lines.append(f"+{len(items) - len(shown)} more")
        buttons = [("Done: " + shown[0]["text"], ("todo_done", shown[0]["id"]), True), ("Open list", "todo_open", False)]
        self.set_info({"kind": "todo", "chip": "To-do", "right": f"{len(items)} open", "text": "\n".join(lines),
                       "buttons": buttons, "max_lines": 10}, force=True)
        if self.phys == "rest" and not self.hanging and not self.cfg["dnd"]:
            self.player.once("reminder")

    def snooze(self):
        if self.info and self.info.get("_text"):
            items = list(self.cfg.get("reminders") or [])
            items.append({"text": self.info["_text"], "due": time.time() + 300})
            self.cfg.set("reminders", items)
        self.set_info(None, force=True)

    def type_answer(self):
        from PySide6.QtWidgets import QInputDialog
        if not self.interactive or not self.interactive[0].is_ask:
            return
        it = self.interactive[0]
        q = it.questions[it.page]
        text, ok = QInputDialog.getText(None, "Smellyfish - your answer", q.get("question", "Your answer:"))
        if ok and text.strip() and self.interactive and self.interactive[0] is it:
            self.click_value(("option", text.strip()))

    # ------------------------------------------------------------ weather info
    def show_weather(self, animate=True):
        if self.cfg.get("weather_place"):
            self.bump("weather_checks")
        if not self.cfg.get("weather_place") and not self.cfg.get("weather_auto"):
            self.notice({"kind": "wait", "chip": "Weather", "text": "Tell me where you are and I'll show you "
                                                                     "the weather. Enter a place in the settings.",
                         "buttons": [("Settings", "settings", True), ("OK", "ok", False)]}, seconds=0)
            return
        self.notice({"kind": "wait", "chip": "Weather", "text": self.weather.text})
        kind = self.weather.kind or "cloud"
        if animate and self.phys == "rest" and not self.player.busy and not self.hanging:
            self.player.once(WEATHER_ANIM.get(kind, "cloudy"))

    # ------------------------------------------------------------ chase the cursor
    def toggle_chase(self):
        if time.time() < self.chase_until:
            self.chase_until = 0.0
            self.chase_timer.stop()
        else:
            if self.cfg.get("mini"):
                self.leave_mini()
            self.chase_until = time.time() + 45
            self.chase_timer.start(500)
        QTimer.singleShot(0, self.build_menu)

    def chase_step(self):
        if time.time() > self.chase_until:
            self.chase_timer.stop()
            return QTimer.singleShot(0, self.build_menu)
        if self.phys != "rest" or self.hanging or self.player.busy or self.plan:
            return
        c = QCursor.pos()
        dx = c.x() - self.cx()
        feet = self.feet()
        if c.y() < feet - 160:
            margin = HALF_W * self.pix
            above = [s for s in self.get_surfaces(fresh=True) if s.x0 + margin <= c.x() <= s.x1 - margin
                     and c.y() - 40 <= s.y < feet - 40 and (not self.perch or s.hwnd != self.perch[0])]
            if above:
                s = min(above, key=lambda w: abs(w.y - c.y()))
                plan = self.route_to(c.x(), s.y, s.hwnd)
                if plan:
                    return self.run_plan(plan)
        if c.y() > feet + 160 and self.perch:
            plan = self.route_to(c.x(), self.area().bottom() + 1)
            if plan:
                return self.run_plan(plan)
        if abs(dx) < 50 * self.pix / 4:
            return
        y = self.feet()
        margin = HALF_W * self.pix
        target = None
        if self.perch:
            target = next((s for s in self.get_surfaces() if s.hwnd == self.perch[0]), None)
        a = self.area()
        lo, hi = (target.x0 + margin, target.x1 - margin) if target else (a.left() + margin, a.right() - margin)
        nx = max(lo, min(hi, self.cx() + max(-240, min(240, dx))))
        if abs(nx - self.cx()) < 10:
            return
        self.run_plan([("hop", (nx, y, target or surfaces.Surface(None, nx - 30, nx + 30, y)))])

    # ------------------------------------------------------------ mini mode
    def toggle_mini(self):
        if self.cfg.get("mini"):
            self.leave_mini()
        else:
            self.cfg.set("mini", True)
            self.place_mini()
        QTimer.singleShot(0, self.build_menu)

    def place_mini(self):
        self.tick.stop()
        self.swim_timer.stop()
        self.climb_timer.stop()
        self.plan, self.homing = [], False
        self.phys, self.perch = "rest", None
        a = self.screen_at(self.cx(), self.feet() - 4).availableGeometry()
        if self.cfg.get("mini_side") == "left":
            x = a.left() - 10 * self.pix
        else:
            x = a.right() + 1 - 14 * self.pix
        self.move_to(x, a.bottom() + 1 - FEET * self.pix)
        self.cache.clear()
        self.render()
        self.house.hide()
        self.update_ambient()

    def leave_mini(self):
        self.cfg.set("mini", False)
        a = self.area()
        self.move_to(a.right() - 30 * self.pix, self.y)
        self.refresh_house()
        self.update_ambient()
        QTimer.singleShot(300, self.go_home)

    # ------------------------------------------------------------ clipboard
    def on_clipboard(self):
        if not self.cfg.get("react_clipboard") or self.cfg["dnd"] or self.hidden_for_game():
            return
        now = time.time()
        md = QGuiApplication.clipboard().mimeData()
        if md is None:
            return
        image = md.hasImage()
        if image:
            self.bump("screenshots")
        if now - self.last_clip < CLIP_COOLDOWN:
            return
        if self.player.busy or self.player.base not in AMBIENT or self.phys != "rest" or self.cfg.get("mini"):
            return
        self.last_clip = now
        if image:
            self.player.once("camera")
        elif md.hasText() and md.text().strip():
            self.player.once("nom")

    # ------------------------------------------------------------ Discord
    def connect_discord(self):
        self.discord.start_rpc(True)

    def disconnect_discord(self):
        self.discord.disconnect()

    def update_presence(self):
        if not self.cfg.get("discord_presence"):
            return self.presence.update(None)
        base = "idle" if self.llm_phase else self.player.base
        details, state = discord_presence.lines(base, self.last_who, self.cfg["dnd"], bool(self.wandering))
        self.presence.update(discord_presence.activity(details, state, self.presence_started))

    def on_discord_status(self, text):
        self.discord_status_text = text
        if self.discord_win is not None:
            self.discord_win.set_status(text)

    def on_discord_message(self, title, body):
        text = f"{title}: {body}" if body else title
        self.add_history("Discord", "Message", text)
        self.mail_until = time.time() + MAIL_S
        self.badge_update()
        QTimer.singleShot(MAIL_S * 1000 + 200, self.badge_update)
        if self.cfg["dnd"] or self.hidden_for_game():
            self.unseen += 1
            return self.badge_update()
        if self.interactive or (self.info and self.info.get("kind") == "focus"):
            return
        spec = {"kind": "discord", "chip": "Discord", "text": text, "max_lines": 4,
                "buttons": [("Open Discord", "open_discord", True), ("OK", "ok", False)]}
        self.set_info(spec)
        self.notify_sound("message")
        if not self.player.busy and self.player.base in AMBIENT:
            self.player.once("mail")
        QTimer.singleShot(9000, lambda: self.set_info(None) if self.info is spec else None)

    # ------------------------------------------------------------ history & badge
    def add_history(self, source, title, text):
        self.history.append({"t": time.time(), "source": source, "title": title, "text": text})
        del self.history[:-60]
        if self.history_win is not None and self.history_win.isVisible():
            self.history_win.refresh()

    def badge_update(self):
        now = time.time()
        self.sessions = {k: v for k, v in self.sessions.items() if now - v < 1800}
        items = []
        urgent = []
        if self.focus.phase:
            items.append((fmt_elapsed(self.focus.remaining, True), (230, 120, 60) if self.focus.phase == "focus"
                          else (90, 170, 110), "timer"))
            if self.focus.remaining < 60:
                urgent.append(len(items) - 1)
        self.prompt_time = {k: v for k, v in self.prompt_time.items() if now - v < 4 * 3600}
        if self.cfg.get("task_timer", True) and self.prompt_time and self.player.base in WORK | {"question"}:
            took = now - min(self.prompt_time.values())
            items.append((fmt_elapsed(took, True), (90, 110, 150), "timer"))
            if int(took // 300) != self.badge_marks.get("task"):
                if took >= 300:
                    self.peek_badges(5)
                self.badge_marks["task"] = int(took // 300)
        else:
            self.badge_marks.pop("task", None)
        if len(self.sessions) >= 2:
            items.append((str(min(len(self.sessions), 99)), (140, 96, 190), "sessions"))
        if len(self.sessions) != self.badge_marks.get("sessions", 0):
            self.badge_marks["sessions"] = len(self.sessions)
            if self.sessions:
                self.peek_badges(5)
        d = self.discord.state
        if self.cfg["discord"] and d["in_call"] and not self.player.name.startswith("call"):
            if d["deaf"]:
                items.append(("DEAF", (200, 60, 70), "call"))
            elif d["mute"]:
                items.append(("MUTE", (200, 60, 70), "call"))
            else:
                items.append(("CALL", (70, 160, 100), "call"))
        if now < getattr(self, "mail_until", 0):
            items.append(("MSG", (88, 101, 242), "msg"))
            urgent.append(len(items) - 1)
        if self.cfg.get("clicker"):
            clicks = self.clicks_today()
            items.append((short_count(clicks), (70, 130, 110), "clicks"))
            if clicks // 250 != self.badge_marks.get("clicks", clicks // 250):
                self.peek_badges(4)
            self.badge_marks["clicks"] = clicks // 250
        late = len(self.todos.overdue(now))
        if late:
            items.append((f"DUE {late}" if late > 1 else "DUE", (200, 120, 60), "due"))
            urgent.append(len(items) - 1)
        if self.unseen:
            items.append(("!" if self.unseen == 1 else str(min(self.unseen, 99)), (235, 80, 90)))
            urgent.append(len(items) - 1)
        peek = now < self.badge_peek_until or self.hover_since is not None
        items = [it for i, it in enumerate(items) if peek or i in urgent]
        if self.hanging or self.phys == "ceiling":
            items = []
        self.badge_items = items
        self.badge.show_items(items)
        if self.tray:
            tip = "Smellyfish"
            if self.focus.phase:
                tip += f" - {self.focus.phase} {self.focus.label()}"
            if self.unseen:
                tip += f" - {self.unseen} missed"
            self.tray.setToolTip(tip)

    def peek_badges(self, seconds):
        self.badge_peek_until = max(self.badge_peek_until, time.time() + seconds)

    def replay(self, entry):
        if self.info and self.info.get("kind") == "focus":
            return
        self.set_info({"kind": "wait", "chip": entry["title"], "right": entry["source"], "text": entry["text"]},
                      force=True)

    # ------------------------------------------------------------ Claude Code / Codex events
    def policy(self, payload):
        if self.cfg["dnd"] or self.hidden_for_game():
            return False
        if payload.get("hook_event_name") == "PermissionRequest":
            return bool(self.cfg["perm_in_bubble"])
        return bool(self.cfg["ask_in_bubble"])

    def quiet_mode(self):
        return self.cfg["dnd"] or self.hidden_for_game()

    def missed(self, source, title, text):
        self.add_history(source, title, text)
        self.unseen += 1
        self.badge_update()

    def on_event(self, payload):
        ev = payload.get("hook_event_name")
        sid = payload.get("session_id")
        who = source_name(payload)
        self.last_who = who
        if ev == "UserPromptSubmit":
            self.sessions[sid] = time.time()
            self.prompt_time[sid] = time.time()
            self.peek_badges(5)
        elif ev in ("PreToolUse", "PostToolUse", "PostToolUseFailure") and sid in self.sessions:
            self.sessions[sid] = time.time()
        elif ev in ("Stop", "StopFailure", "SessionEnd", "Interrupt"):
            self.sessions.pop(sid, None)
            start = self.prompt_time.pop(sid, None)
            if start:
                payload["_elapsed"] = time.time() - start
        self.badge_update()
        if self.quiet_mode():
            return self.quiet_event(payload, ev, who)

        if ev == "UserPromptSubmit":
            self.drop_session(sid)
            self.set_info(None)
            self.limit_timer.stop()
            self.player.set_base("thinking")
        elif ev in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            if ev == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
                text = f"{who} has a question for you in the terminal."
                self.add_history(who, "Question", text)
                self.set_info({"kind": "wait", "chip": "Question", "right": who, "text": text})
                self.notify_sound("question")
                self.player.set_base("question")
                return
            if not self.interactive:
                if ev == "PreToolUse":
                    anim = tool_anim(payload.get("tool_name"))
                    started = self.prompt_time.get(sid)
                    if anim == "working" and (self.player.base == "cooking" or (
                            started and time.time() - started > 60 and random.random() < 0.2)):
                        anim = "cooking"
                    self.player.set_base(anim)
                elif self.player.base not in WORK:
                    self.player.set_base("working")
                if ev == "PostToolUseFailure" and not self.player.busy:
                    self.player.once("error")
            self.quiet.start(QUIET_MS)
        elif ev == "Notification":
            kind = payload.get("notification_type")
            if kind == "permission_prompt" and self.interactive:
                return
            if kind in ("permission_prompt", "idle_prompt", "agent_needs_input", "elicitation_dialog"):
                text = payload.get("message") or f"{who} is waiting for you."
                self.add_history(who, "Waiting", text)
                self.set_info({"kind": "wait", "chip": "Waiting", "right": who, "text": text})
                self.notify_sound("question")
                if not self.interactive:
                    self.player.set_base("question")
        elif ev in ("Stop", "StopFailure"):
            self.drop_session(sid)
            self.quiet.stop()
            took = payload.get("_elapsed")
            right = who + (f" {fmt_elapsed(took)}" if took else "")
            if ev == "StopFailure":
                err = payload.get("error") or ""
                text = payload.get("last_assistant_message") or err or "API error"
                limited = err in ("rate_limit", "billing_error") or "limit" in text.lower()
                self.add_history(who, "Usage limit" if limited else "Error", text)
                self.set_info({"kind": "wait", "chip": "Usage limit" if limited else "Error", "right": right,
                               "text": text})
                self.notify_sound("question")
                if self.interactive:
                    pass
                elif limited:
                    self.player.set_base("exhausted")
                    self.exhausted_at = time.time()
                    self.limit_timer.start(LIMIT_MS)
                else:
                    self.player.set_base(self.after_task_base())
                    self.player.once("error")
            else:
                text = summarize(payload.get("last_assistant_message")) or f"{who} is done."
                self.add_history(who, "Done", text)
                self.bump("tasks_done")
                if self.cfg["done_bubble"]:
                    self.set_info({"kind": "done", "chip": "Done", "right": right, "text": text})
                self.notify_sound("done")
                if not self.interactive:
                    self.player.set_base("done")
            self.done_timer.start(DONE_MS)
        elif ev in ("SessionEnd", "Interrupt"):
            self.drop_session(sid)
            self.set_info(None)
            self.quiet.stop()
            if not self.interactive:
                self.player.set_base(self.after_task_base())

    def quiet_event(self, payload, ev, who):
        """Do not disturb / fullscreen: no animation changes, only the badge and the missed list."""
        if ev == "Stop":
            self.missed(who, "Done", summarize(payload.get("last_assistant_message")) or f"{who} is done.")
        elif ev == "StopFailure":
            self.missed(who, "Error", payload.get("last_assistant_message") or payload.get("error") or "API error")
        elif ev == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
            self.missed(who, "Question", f"{who} asked you something in the terminal.")
        elif ev == "Notification" and payload.get("notification_type") in ("permission_prompt", "idle_prompt",
                                                                           "agent_needs_input"):
            self.missed(who, "Waiting", payload.get("message") or f"{who} is waiting for you.")

    def on_quiet(self):
        if self.player.base in WORK - {"thinking"} and not self.interactive:
            self.player.set_base("thinking")

    def on_done_timeout(self):
        if self.info and self.info.get("kind") in ("done", "wait"):
            self.set_info(None)
        if not self.interactive and self.player.base == "done":
            self.player.set_base(self.after_task_base())

    def after_task_base(self):
        """Another task still running keeps the pet thinking instead of going idle."""
        now = time.time()
        busy = any(now - self.sessions.get(sid, 0) < 600 for sid in self.prompt_time)
        return "thinking" if busy else self.idle_base()

    def on_limit_over(self):
        if self.player.base == "exhausted":
            self.player.set_base(self.idle_base())

    def on_ask(self, pending):
        self.wake()
        self.interactive.append(Interactive(pending))
        self.done_timer.stop()
        self.notify_sound("question")
        self.player.set_base("question")
        self.refresh_bubble()

    def on_expired(self, rid):
        expired = [i for i in self.interactive if i.pending.rid == rid]
        self.interactive = [i for i in self.interactive if i.pending.rid != rid]
        for it in expired:
            self.missed(source_name(it.payload), "Unanswered", "A question timed out and went to the terminal.")
            self.player.once("sad")
        self.after_answer()

    def drop_session(self, sid):
        stale = [i for i in self.interactive if i.session == sid]
        for i in stale:
            self.server.resolve(i.pending.rid, {})
        self.interactive = [i for i in self.interactive if i.session != sid]
        if stale:
            self.refresh_bubble()

    def after_answer(self):
        self.refresh_bubble()
        if not self.interactive and self.player.base == "question":
            self.player.set_base("working")
            self.quiet.start(QUIET_MS)

    # ------------------------------------------------------------ bubble
    def set_info(self, spec, force=False):
        if spec is None and not force and self.info and self.info.get("kind") == "focus":
            return
        if spec is not None and not force and self.info and self.info.get("kind") == "focus":
            return
        self.info = spec if (force or not self.cfg["dnd"]) else None
        self.refresh_bubble()

    def notice(self, spec, seconds=10):
        """Answer to something the user asked for (update check, weather...): shown even while the pet sleeps
        or is in do-not-disturb, unless a game is in the foreground. seconds=0 keeps it until dismissed."""
        if self.hidden_for_game() or self.interactive:
            return
        self.wake()
        self.set_info(spec, force=True)
        if seconds:
            QTimer.singleShot(seconds * 1000, lambda: self.set_info(None, force=True) if self.info is spec else None)

    def bubble_kind(self):
        spec = self.interactive[0].spec() if self.interactive else self.info
        return spec["kind"] if spec else None

    def refresh_bubble(self):
        spec = self.interactive[0].spec() if self.interactive else self.info
        key = None
        if spec:
            key = (spec.get("kind"), spec.get("question") or spec.get("text") or spec.get("detail"))
        new = bool(key) and key != getattr(self, "_last_bubble", None)
        self._last_bubble = key
        self.bubble.set_spec(spec)
        if not spec and self.cheers:
            QTimer.singleShot(900, self.flush_cheers)
        if not spec:
            self.blips_left = 0
        elif new and spec.get("kind") != "focus" and self.bubble.isVisible():
            self.talk(spec.get("question") or spec.get("text") or spec.get("prompt") or "")

    def talk(self, text):
        """Little babble blips when a bubble appears (Animal Crossing style)."""
        now = time.time()
        if (not self.cfg.get("talk_blips") or self.cfg["dnd"] or self.hidden_for_game() or not text.strip()
                or now - getattr(self, "last_talk", 0) < 3):
            return
        self.last_talk = now
        self.blips_left = max(3, min(8, len(text) // 14 + 3))
        if not hasattr(self, "blip_timer"):
            self.blip_timer = QTimer(self, timeout=self.blip)
        self.blip_timer.start(120)
        self.blip()

    def blip(self):
        if self.blips_left <= 0 or not self.bubble.isVisible():
            self.blips_left = 0
            return self.blip_timer.stop()
        self.blips_left -= 1
        if not self.fun_sounds_on():
            return
        sounds.play(f"blip{random.randint(0, 4)}", self.cfg["volume"])

    def open_discord(self):
        try:
            os.startfile("discord://")
        except OSError:
            pass

    def click_value(self, value):
        if self.mail_until:
            self.mail_until = 0.0
            self.badge_update()
        if value == "open_discord":
            self.set_info(None)
            return self.open_discord()
        if value == "__type__":
            return QTimer.singleShot(0, self.type_answer)
        if value == "snooze":
            return self.snooze()
        if value == "whats_new":
            self.set_info(None, force=True)
            return self.open_changelog(self.updated_from)
        if value == "lan_open":
            self.set_info(None, force=True)
            return self.open_lobby()
        if value == "llm_open":
            self.set_info(None, force=True)
            return self.open_chat()
        if value == "todo_open":
            self.set_info(None, force=True)
            return self.open_todos()
        if isinstance(value, tuple) and value and value[0] == "lan_reply":
            self.set_info(None, force=True)
            if self.lan.id_for(value[1]) is None:
                return self.notice({"kind": "wait", "chip": "Lobby", "text": f"{value[1]} is not in the lobby any "
                                    "more."}, seconds=5)
            return self.quick_letter(value[1])
        if isinstance(value, tuple) and value and value[0] in ("todo_done", "todo_snooze"):
            self.set_info(None, force=True)
            if value[0] == "todo_done":
                return self.todo_set_done(value[1])
            self.todos.snooze(value[1], 10)
            return self.todos_changed()
        if value == "settings":
            self.set_info(None)
            return self.open_settings()
        if value == bubble.EXPAND:
            if self.interactive:
                self.interactive[0].expanded = not self.interactive[0].expanded
            elif self.info:
                self.info = dict(self.info, expanded=not self.info.get("expanded"))
                self.done_timer.stop()
            return self.refresh_bubble()
        if self.interactive:
            it = self.interactive[0]
            result = None
            if value == bubble.TERMINAL:
                result = {}
            elif it.is_ask and isinstance(value, (tuple, list)) and value[0] == "toggle":
                it.picked = [o for o in it.picked if o != value[1]] if value[1] in it.picked else it.picked + [value[1]]
                return self.refresh_bubble()
            elif it.is_ask and isinstance(value, (tuple, list)) and value[0] in ("option", "confirm"):
                q = it.questions[it.page]
                if value[0] == "confirm":
                    if not it.picked:
                        return
                    order = [o.get("label") for o in q.get("options", [])]
                    it.answers[q.get("question", "")] = ", ".join(sorted(it.picked, key=order.index))
                    it.picked = []
                else:
                    it.answers[q.get("question", "")] = value[1]
                it.page += 1
                if it.page >= len(it.questions):
                    result = ask_answer(it.payload, it.answers)
                else:
                    return self.refresh_bubble()
            elif not it.is_ask and value in ("allow", "deny", "always"):
                result = permission_answer(it.payload, value)
            if result is not None:
                self.interactive.pop(0)
                self.server.resolve(it.pending.rid, result)
                if result:
                    self.bump("answered")
                self.after_answer()
                if value == "deny":
                    self.player.once("sad")
                elif result:
                    self.player.once("happy")
            return
        if value in ("break_start", "focus_start", "focus_stop"):
            self.set_info(None, force=True)
            if value == "focus_stop":
                self.focus.stop()
            else:
                self.focus.start("break" if value == "break_start" else "focus")
                if value == "break_start":
                    self.player.once("stretch")
            return self.update_ambient()
        if value == "update_restart":
            updater.restart()
            return QApplication.quit()
        if value in ("trash_empty", "trash_later"):
            self.set_info(None)
            self.end_trash_visit()
            if value == "trash_empty":
                self.empty_trash()
            return
        if value == "ok":
            self.set_info(None)
            if self.player.base in ("done", "question"):
                self.player.set_base(self.idle_base())

    # ------------------------------------------------------------ settings
    def get_setting(self, key):
        if key == "hooks":
            return install_hooks.is_installed("user")
        if key == "codex_hooks":
            return install_hooks.is_installed("codex")
        if key == "claude_statusline":
            return install_hooks.statusline_state() == "ours"
        if key == "autostart":
            return cfg.autostart_enabled()
        return self.cfg.get(key)

    def apply_dark(self, on):
        bubble.set_dark(on)
        theme.set_dark(on)
        if self.ask_win is not None:
            self.ask_win.key = None
            self.ask_win.restyle()
        self.refresh_bubble()
        QTimer.singleShot(0, self.build_menu)

    def apply_setting(self, key, value):
        if key == "hooks":
            install_hooks.apply("user", bool(value))
        elif key == "codex_hooks":
            install_hooks.apply("codex", bool(value))
        elif key == "claude_statusline":
            if not install_hooks.apply_statusline(bool(value)):
                self.notice({"kind": "wait", "chip": "Status line", "right": "Claude",
                             "text": "You already have your own Claude Code status line, so I left it alone."})
                if self.settings_win is not None:
                    self.settings_win.refresh()
        elif key == "autostart":
            cfg.set_autostart(bool(value))
        else:
            if self.cfg.get(key) == value:
                return
            self.cfg.set(key, value)
            if key == "scale":
                self.set_scale(value)
            elif key == "opacity":
                for w in (self.view, self.house):
                    w.setWindowOpacity(float(value))
            elif key in ("gravity", "sit_on_windows") and self.cfg["gravity"] and self.phys == "rest":
                self.fall()
            elif key == "dark_ui":
                self.apply_dark(value)
            elif key in ("eyes_follow", "seasonal", "skin", "skin_color"):
                self.cache.clear()
                self.hang_cache.clear()
                self.render()
            elif key == "temp_unit":
                self.weather.render()
            elif key in ("weather", "weather_place", "weather_auto", "weather_ip"):
                self.cache.clear()
                self.weather.here = None
                self.weather.refresh(force=True)
                self.render()
            elif key == "mute_all":
                sounds.set_muted(value)
            elif key == "dnd":
                self.set_dnd(value)
            elif key == "discord_presence":
                self.update_presence()
            elif key == "clicker":
                self.sync_clicker()
            elif key == "monitor":
                self.surfs_at = 0
                self.refresh_house()
                if self.fixed_screen() is not None and not self.bounds().contains(
                        QPoint(round(self.cx()), round(self.feet()) - 4)):
                    hx, hy = self.home()
                    self.plan = []
                    self.homing = False
                    self.move_to(hx - CENTER_X * self.pix, hy - FEET * self.pix - 40)
                    self.fall()
            elif key == "on_top":
                self.set_on_top(value)
            elif key in ("show_house", "wander"):
                self.refresh_house()
            elif key in ("react_music", "beat_sync"):
                self.sync_beats()
            elif key == "hotkeys":
                self.register_hotkeys()
        QTimer.singleShot(0, self.build_menu)
        if self.settings_win is not None and self.settings_win.isVisible():
            self.settings_win.refresh()

    def register_hotkeys(self):
        from smellyfish.system import hotkeys as hk
        mapping = dict(hk.DEFAULTS, **(self.cfg.get("hotkeys") or {}))
        self.hotkey_conflicts = self.hotkeys.register(int(self.view.winId()), mapping)

    def on_hotkey(self, action):
        if action == "toggle":
            self.set_visible(not getattr(self, "_visible", True))
        elif action == "home":
            self.go_home()
        elif action == "dnd":
            self.apply_setting("dnd", not self.cfg["dnd"])
        elif action == "history":
            self.open_history()
        elif action == "focus":
            self.toggle_focus()
        elif action == "chase":
            self.toggle_chase()
        elif action == "mini":
            self.toggle_mini()
        elif action == "todo":
            self.open_todos()
        elif action == "ask":
            self.open_ask()

    def build_menu(self):
        m = self.menu
        m.clear()
        title = m.addAction(f"Smellyfish v{__version__}")
        title.setEnabled(False)
        if self.llm.enabled():
            m.addAction("Ask Smellyfish...", self.open_ask)
        m.addAction(f"Missed ({self.unseen})..." if self.unseen else "Missed...", self.open_history)
        m.addAction("What's the weather?", self.show_weather)
        open_n = len(self.todos.open_items())
        m.addAction(f"To-do ({open_n} open)..." if open_n else "To-do...", self.open_todos)
        pending = len(self.cfg.get("reminders") or [])
        m.addAction(f"Remind me... ({pending} pending)" if pending else "Remind me...", self.add_reminder)
        focus = m.addMenu("Focus")
        if self.focus.phase:
            focus.addAction(f"Stop ({self.focus.phase}, {self.focus.label()} left)", self.toggle_focus)
        else:
            focus.addAction(f"Start focus ({self.cfg['focus_min']} min)", self.toggle_focus)
        focus.addAction(f"Take a break now ({self.cfg['break_min']} min)", self.start_break)
        m.addAction("Lobby (LAN)..." if self.lan.role is None else f"Lobby: {self.lan.lobby_name}...", self.open_lobby)
        if self.lan.role is not None:
            m.addAction("Send letter...", self.quick_letter)
            m.addAction("Visit someone...", self.quick_visit)
        m.addAction("Go home", self.go_home)
        dnd = QAction("Do not disturb", m, checkable=True, checked=bool(self.cfg["dnd"]))
        dnd.toggled.connect(lambda on: self.apply_setting("dnd", on))
        m.addAction(dnd)
        mute_all = QAction("Mute all sounds", m, checkable=True, checked=bool(self.cfg["mute_all"]))
        mute_all.toggled.connect(lambda on: self.apply_setting("mute_all", on))
        m.addAction(mute_all)
        m.addSeparator()

        play = m.addMenu("Play")
        play.addAction("Give a snack", self.give_snack)
        play.addAction("Throw a ball", self.throw_ball)
        if self.ball is not None:
            play.addAction("Put the ball away", self.put_ball_away)
        play.addAction("Stop chasing the cursor" if time.time() < self.chase_until else "Chase the cursor",
                       self.toggle_chase)
        play.addAction("Hang from a window", lambda: self.hang_from_window(manual=True))
        play.addAction("Show detected edges (12 s)", self.show_edges)

        more = m.addMenu("More")
        more.addAction(f"Achievements ({self.life.unlocked_count()})...", self.open_achievements)
        more.addAction("Animation tester...", self.open_gallery)
        more.addSeparator()
        show = QAction("Show Smellyfish", more, checkable=True, checked=getattr(self, "_visible", True))
        show.toggled.connect(self.set_visible)
        more.addAction(show)
        more.addAction("Set home here", self.set_home_here)
        mini = QAction("Mini mode", more, checkable=True, checked=bool(self.cfg.get("mini")))
        mini.toggled.connect(lambda _on: self.toggle_mini())
        more.addAction(mini)
        mute = QAction("Mute fun sounds", more, checkable=True, checked=not self.cfg["sfx"])
        mute.toggled.connect(lambda on: self.apply_setting("sfx", not on))
        more.addAction(mute)
        more.addSeparator()
        more.addAction("What's new...", self.open_changelog)

        quick = m.addMenu("Settings")
        quick.addAction("Open the settings window...", self.open_settings)
        quick.addSeparator()
        for section, items in SCHEMA:
            sub = quick.addMenu(section.replace("&", "&&"))
            for key, label, choices in items:
                current = self.get_setting(key)
                if callable(choices):
                    choices = choices()
                if choices:
                    cm = sub.addMenu(label)
                    group = QActionGroup(cm)
                    for text, value in choices:
                        a = QAction(text, cm, checkable=True, checked=current == value)
                        a.triggered.connect(lambda _=False, k=key, v=value: self.apply_setting(k, v))
                        group.addAction(a)
                        cm.addAction(a)
                    if key == "scale":
                        cm.addSeparator()
                        cm.addAction("Custom...", self.open_settings)
                else:
                    a = QAction(label, sub, checkable=True, checked=bool(current))
                    a.toggled.connect(lambda on, k=key: self.apply_setting(k, on))
                    sub.addAction(a)

        m.addSeparator()
        m.addAction("Check for updates", lambda: self.updater.check(manual=True))
        m.addAction("About Smellyfish...", self.open_about)
        m.addAction("Quit", QApplication.quit)

    def _open(self, attr, cls):
        win = getattr(self, attr)
        if win is None:
            win = cls(self)
            setattr(self, attr, win)
        if hasattr(win, "refresh"):
            win.refresh()
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def open_settings(self):
        self._open("settings_win", SettingsWindow)

    def open_about(self):
        self._open("about_win", AboutWindow)

    def open_gallery(self):
        self._open("gallery_win", GalleryWindow)

    def open_history(self):
        self.unseen = 0
        self.badge_update()
        QTimer.singleShot(0, self.build_menu)
        self._open("history_win", HistoryWindow)

    def open_achievements(self):
        from smellyfish.ui.gallery import AchievementsWindow
        self._open("achievements_win", AchievementsWindow)

    def test_sound(self, key="notify_volume", volume=None):
        if key == "volume":
            sounds.play(random.choice(["giggle", "boing", "pop", "happy"]),
                        self.cfg["volume"] if volume is None else volume)
        else:
            sounds.play("done", self.cfg.get("notify_volume", 70) if volume is None else volume)

    def on_save_error(self, error):
        self.save_retry.start(3000)
        if time.time() - getattr(self, "_save_error_shown", 0) > 600:
            self._save_error_shown = time.time()
            text = (f"I couldn't save your settings ({error.__class__.__name__}). I'll keep trying; "
                    "details are in smellyfish.log.")
            self.add_history("Smellyfish", "Settings", text)
            QTimer.singleShot(0, lambda: self.set_info({"kind": "wait", "chip": "Settings", "text": text}))

    def verify_saved(self, keys):
        """Read settings.json back and report keys whose saved value differs from what the app uses."""
        import json
        try:
            with open(cfg.PATH, encoding="utf-8") as f:
                disk = json.load(f)
        except (OSError, ValueError) as e:
            return f"settings file unreadable ({e.__class__.__name__})"
        bad = [k for k in keys if json.dumps(disk.get(k), sort_keys=True) != json.dumps(self.cfg.get(k),
                                                                                          sort_keys=True)]
        return ", ".join(bad)

    def open_discord_setup(self):
        self._open("discord_win", DiscordSetup)

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.open_settings()
        elif reason == QSystemTrayIcon.Trigger:
            self.set_visible(not getattr(self, "_visible", True))

    def set_visible(self, on):
        self._visible = on
        self.view.setVisible(on)
        self.house.setVisible(on and self.cfg["show_house"])
        if not on:
            self.bubble.hide()
            self.badge.hide()
        else:
            if self.bubble.spec:
                self.bubble.place()
            self.badge_update()
        QTimer.singleShot(0, self.build_menu)

    def set_scale(self, pix):
        feet, cx = self.feet(), self.cx()
        self.pix = max(1, int(pix))
        self.apply_view()
        self.move_to(cx - CENTER_X * self.pix, feet - FEET * self.pix)
        self.bubble.tail = None
        self.bubble.place()
        self.refresh_house()
        self.badge_update()

    def set_dnd(self, on):
        if on:
            for i in self.interactive:
                self.server.resolve(i.pending.rid, {})
            self.interactive = []
            self.set_info(None)
            self.player.set_base("sleeping")
            self.go_home()
        else:
            self.player.set_base(self.ambient())
        self.refresh_house()
        self.update_ambient()

    def keep_on_top(self):
        """Other always-on-top windows (taskbar, overlays) can push ours down; put them back in order."""
        if sys.platform != "win32" or not self.cfg.get("on_top", True) or self.hidden_for_game():
            return
        import ctypes
        from ctypes import wintypes
        swp = ctypes.windll.user32.SetWindowPos
        swp.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                        wintypes.UINT]
        order = [self.house] + [t for t in ([self.ball] + list(self.snacks)) if t is not None] +                 [self.view, self.badge, self.bubble]
        flags = 0x0001 | 0x0002 | 0x0010 | 0x0200
        for w in order:
            try:
                if w.isVisible():
                    swp(int(w.winId()), wintypes.HWND(-1), 0, 0, 0, 0, flags)
            except RuntimeError:
                pass

    def set_on_top(self, on):
        for w in (self.view, self.bubble, self.house, self.badge):
            visible = w.isVisible()
            w.setWindowFlag(Qt.WindowStaysOnTopHint, on)
            if visible:
                w.show()
        self.view.raise_()
        self.register_hotkeys()

    # ------------------------------------------------------------ debug (SMELLYFISH_DEBUG=1)
    def on_debug(self, cmd):
        kind, p = cmd
        if kind == "ui":
            from smellyfish.ui.gallery import AchievementsWindow, ReminderDialog
            win = {"settings": lambda: self._open("settings_win", SettingsWindow),
                   "gallery": lambda: self._open("gallery_win", GalleryWindow),
                   "history": lambda: self._open("history_win", HistoryWindow),
                   "discord": lambda: self._open("discord_win", DiscordSetup),
                   "achievements": lambda: self._open("achievements_win", AchievementsWindow),
                   "todo": lambda: self._open("todo_win", TodoWindow),
                   "changelog": lambda: self._open("changelog_win", ChangelogWindow),
                   "reminder": lambda: ReminderDialog(self)}[p["name"]]()
            win.show()
            QTimer.singleShot(600, lambda: (win.grab().save(p["path"]), win.close()))
        if kind == "trash":
            if p.get("emptied"):
                old, self.trash.state = self.trash.state, (0, 0)
                return self.on_trash(old, (0, 0))
            if p.get("state"):
                self.trash.state = tuple(p["state"])
            self.maybe_report_trash(force=True)
        elif kind == "stroke":
            from PySide6.QtCore import QPoint as P
            p0 = self.pix
            y = self.y + ((sprite.BY + 2) if p.get("zone") == "head" else (sprite.BY + 10)) * p0
            self.last_stroke = 0
            for i in range(10):
                x = self.x + (BODY_X0 + (3 if i % 2 else 11)) * p0
                self.check_stroke(P(round(x), round(y)), time.time() + i * 0.1)
        elif kind == "setting":
            self.apply_setting(p["key"], p["value"])
        if kind == "click":
            v = p.get("value")
            self.click_value(tuple(v) if isinstance(v, list) else v)
        elif kind == "snap":
            path = p.get("path", "snap.png")
            self.view.grab().save(path)
            for w, suffix in ((self.bubble, "_bubble"), (self.house, "_house"), (self.badge, "_badge")):
                if w.isVisible():
                    w.grab().save(path.replace(".png", suffix + ".png"))
        elif kind == "poke":
            self.poke()
        elif kind == "fling":
            self.tick.stop()
            self.phys = "rest"
            self.move_to(p.get("x", self.x), p.get("y", self.y))
            self.fall(p.get("vx", 0.0), p.get("vy", 0.0))
        elif kind == "drag":
            self.press = (QCursor.pos(), time.time())
            self.start_hang(QCursor.pos())
            QTimer.singleShot(int(p.get("ms", 600)), self.drop)
        elif kind == "home":
            self.go_home()
        elif kind == "sethome":
            self.cfg.set("home", p.get("home"))
            self.refresh_house()
        elif kind == "house":
            self.house_click(p.get("prop"))
        elif kind == "play":
            self.preview_anim(p.get("name"))
        elif kind == "focus":
            self.focus.start(p.get("phase", "focus")) if p.get("start", True) else self.focus.stop()
            if p.get("end"):
                self.focus.ends_at = time.time()
        elif kind == "dnd":
            self.apply_setting("dnd", bool(p.get("on")))
        elif kind == "hotkey":
            self.on_hotkey(p.get("action"))
        elif kind == "snack":
            self.give_snack()
        elif kind == "ball":
            self.throw_ball()
        elif kind == "mini":
            self.toggle_mini()
        elif kind == "clip":
            self.last_clip = 0
            QGuiApplication.clipboard().setText(p.get("text", "hello"))
            self.last_clip = 0
            self.on_clipboard()

    def on_update_ready(self, version):
        text = f"I updated myself to version {version}. Restart now to use it?"
        self.add_history("Smellyfish", "Update", text)
        if self.hidden_for_game():
            return
        self.notice({"kind": "wait", "chip": "Update", "right": f"v{version}", "text": text,
                     "buttons": [("Restart", "update_restart", True), ("Later", "ok", False)]}, seconds=0)

    # ------------------------------------------------------------ usage limits
    def on_usage_warn(self, source, window, pct, resets, critical=False):
        when = ""
        try:
            if isinstance(resets, (int, float)):
                t = datetime.datetime.fromtimestamp(float(resets))
            elif isinstance(resets, str) and resets:
                t = datetime.datetime.fromisoformat(resets.replace("Z", "+00:00")).astimezone()
            else:
                t = None
            if t is not None:
                fmt = "%H:%M" if t.date() == datetime.date.today() else "%a %H:%M"
                when = f" It resets {t.strftime(fmt)}."
        except Exception:
            pass
        text = f"{pct:.0f} % of your {window} {source} limit is used.{when}"
        chip = "Limit almost reached!" if critical else "Usage"
        if critical:
            text += " Wrap up or save your work soon."
        if self.quiet_mode():
            return self.missed(source, chip, text)
        self.add_history(source, chip, text)
        if self.interactive:
            return
        self.set_info({"kind": "critical" if critical else "wait", "chip": chip, "right": source, "text": text,
                       "critical": critical})
        if critical:
            self.done_timer.stop()
            self.notify_sound("alarm")
        else:
            self.done_timer.start(DONE_MS)
            self.notify_sound("warn")
        self.player.once("warn")

    # ------------------------------------------------------------ recycle bin
    def on_trash(self, old, new):
        size, count = new
        if count == 0:
            if self.cfg.get("trash_since"):
                self.cfg.set("trash_since", None)
            if old and old[1] > 0:
                if self.trash_visit or (self.info and self.info.get("trash")):
                    self.set_info(None)
                    self.end_trash_visit()
                self.bump("trash_emptied")
                if not self.quiet_mode() and self.phys == "rest" and not self.hanging:
                    self.player.once("sweep")
            return
        if not self.cfg.get("trash_since"):
            self.cfg.set("trash_since", time.time())
        self.maybe_report_trash()

    def trash_full(self):
        st = self.trash.state
        if not st or not st[1]:
            return False
        size, _count = st
        since = float(self.cfg.get("trash_since") or time.time())
        return (size >= float(self.cfg.get("trash_gb") or 2) * 1e9
                or time.time() - since >= float(self.cfg.get("trash_days") or 7) * 86400)

    def trash_text(self):
        size, count = self.trash.state
        gb = size / 1e9
        amount = f"{gb:.1f} GB" if gb >= 0.1 else f"{size / 1e6:.0f} MB"
        days = int((time.time() - float(self.cfg.get("trash_since") or time.time())) // 86400)
        age = f" It has been full for {days} days." if days >= 2 else ""
        return amount, f"The recycle bin holds {count} items ({amount}).{age} Empty it?"

    def maybe_report_trash(self, force=False):
        if not force:
            if not self.cfg.get("trash_watch") or not self.trash_full():
                return
            if time.time() - float(self.cfg.get("trash_reported_at") or 0) < 4 * 3600:
                return
            if (self.quiet_mode() or self.interactive or self.info or self.player.busy or self.hanging
                    or self.player.base not in AMBIENT or self.phys != "rest" or self.plan or self.homing
                    or self.cfg.get("mini") or self.fetch is not None or self.trash_visit
                    or time.time() < self.chase_until):
                return
        if not self.trash.state or not self.trash.state[1]:
            return
        self.cfg.set("trash_reported_at", time.time())
        spot = None
        try:
            rect = recyclebin.icon_rect()
            if rect and recyclebin.icon_visible(rect, self.own_hwnds()) and self.bounds().contains(
                    QPoint(round((rect[0] + rect[2]) / 2), round((rect[1] + rect[3]) / 2))):
                room = (HALF_W + 2) * self.pix
                b = self.bounds()
                tx = rect[0] - room if rect[0] - room - HALF_W * self.pix > b.left() else rect[2] + room
                spot = (tx, rect[3])
        except Exception:
            spot = None
        if spot is None or not self.cfg["gravity"]:
            self.trash_visit = "there"
            return self.trash_report()
        self.trash_visit = "going"
        self.anchor_cx = None
        self.start_swim(*spot)

    def trash_report(self):
        if not self.trash_visit or not self.trash.state:
            return
        amount, text = self.trash_text()
        self.add_history("Smellyfish", "Recycle bin", text)
        self.player.once("trash_full")
        self.set_info({"kind": "wait", "chip": "Recycle bin", "right": amount, "text": text, "trash": True,
                       "buttons": [("Empty it", "trash_empty", True), ("Later", "trash_later", False)]})
        QTimer.singleShot(30000, self.trash_timeout)

    def trash_timeout(self):
        if self.info and self.info.get("trash"):
            self.set_info(None)
        self.end_trash_visit()

    def end_trash_visit(self):
        if self.trash_visit:
            self.trash_visit = None
            if self.phys == "rest" and self.cfg["gravity"]:
                QTimer.singleShot(600, self.check_perch)

    def empty_trash(self):
        import threading

        def run():
            import ctypes
            try:
                ctypes.windll.ole32.CoInitialize(None)
            except Exception:
                pass
            try:
                recyclebin.empty(None)
            finally:
                self.trash.poll_soon.emit()

        threading.Thread(target=run, daemon=True).start()

    def shutdown(self):
        self.presence.stop()
        self.lan.leave()
        self.guests.clear()
        self.llm.shutdown()
        self.counter.stop()
        self.flush_presses()
        self.life.save()
        self.server.stop()
        self.beats.stop()
        self.hotkeys.unregister()
        if self.phys == "rest":
            self.save_position()


class RecycleWatchProxy(recyclebin.RecycleWatch):
    def __init__(self, app):
        super().__init__()
        self.changed.connect(app.on_trash)
        self.poll_soon.connect(self.poll)


_INSTANCE_LOCK = None


def hold_instance_lock():
    """One running Smellyfish per profile, enforced with an OS file lock held for the whole run."""
    global _INSTANCE_LOCK
    os.makedirs(paths.HOME_DIR, exist_ok=True)
    f = open(os.path.join(paths.HOME_DIR, "instance.lock"), "a+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return False
    _INSTANCE_LOCK = f
    return True


def already_running():
    """Ask the local server before starting, so two instances never fight over the settings."""
    import socket
    from smellyfish.integrations.server import PORT
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5) as sock:
            sock.sendall(b"GET /health HTTP/1.0" + bytes([13, 10, 13, 10]))
            return b"smellyfish" in sock.recv(512)
    except OSError:
        return False


def boot_note(text):
    """Tiny log in %TEMP% written before anything else, to see why a start ended early."""
    try:
        import tempfile
        with open(os.path.join(tempfile.gettempdir(), "smellyfish-boot.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid {os.getpid()} {text}" + chr(10))
    except OSError:
        pass


def main():
    boot_note(f"boot exe={sys.executable} cwd={os.getcwd()} home={paths.HOME_DIR} "
              f"env_home={os.environ.get('SMELLYFISH_HOME')!r} args={sys.argv[1:]}")
    if "--relay" in sys.argv:
        from smellyfish.integrations import hook_relay
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--relay"]
        hook_relay.main()
        return 0
    if os.environ.pop("SMELLYFISH_RESTART", None):
        for _ in range(40):
            if not already_running():
                break
            time.sleep(0.25)
    for _ in range(24):
        if not already_running():
            break
        time.sleep(0.25)
    else:
        boot_note("exit: another Smellyfish answers on the port")
        return 0
    for _ in range(40):
        if hold_instance_lock():
            break
        time.sleep(0.25)
    else:
        boot_note("exit: profile is locked by another Smellyfish")
        return 0
    boot_note("running")
    from smellyfish import logs
    logs.setup()
    import logging
    logging.getLogger("smellyfish").info("start v%s pid %s exe %s", __version__, os.getpid(), sys.executable)
    paths.ensure_relay()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = Smellyfish()
    app.setWindowIcon(pet.tray_icon())
    try:
        pet.server.start()
    except OSError:
        print("Smellyfish is already running (port in use).")
        return 1
    try:
        if paths.FROZEN and not os.environ.get("SMELLYFISH_HOME") and install_hooks.statusline_stale():
            install_hooks.apply_statusline(True)
    except Exception:
        pass
    for scope in ("user", "codex"):
        try:
            if (paths.FROZEN and not os.environ.get("SMELLYFISH_HOME") and install_hooks.is_installed(scope)
                    and install_hooks.needs_update(scope)):
                install_hooks.apply(scope, True)
        except Exception:
            pass
    app.aboutToQuit.connect(pet.shutdown)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
