"""Animation designer: build, edit and preview Smellyfish animations and export them as sprite.py code.

Run from the project root:  python designer/animation_designer.py
"""
import copy
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSpinBox, QSplitter, QTabBar, QToolButton, QVBoxLayout, QWidget)

from smellyfish.art import sprite
from smellyfish.art.sprite import BX, CH, CW, PAL, Pose, layers

SEGMENTS = ("intro", "loop", "outro")
DEFAULT = Pose()
FIELD_KEYS = [k for k in DEFAULT.__dict__ if k not in ("parts", "wear")]
TUPLE_KEYS = ("laptop", "down", "tp", "arm_f")
MIRROR_C = 2 * (BX + 8) - 1
SAVE_DIR = os.path.join(ROOT, "dev", "designer")

EYES = ["open", "blink", "happy", "sleep", "wide", "angry", "x", "none"]
TENTS = ["straight", "tuck", "spread", "swing_l", "swing_r", "long", "left", "right"]
TPS = list(sprite.TP)
ARMS_F = list(sprite.F_ARMS)
ARMS_S = list(sprite.S_ARM)
LAPTOPS = [None] + list(sprite.LAPTOP)
HEADSETS = [None, "mic", "phones"]
MOUTHS = [None, "small", "big"]
TINTS = [None] + list(sprite.TINTS)

BG = {"Dark": (38, 32, 52), "Light": (238, 236, 244), "White": (255, 255, 255), "Green": (40, 90, 60)}


def _tuple(key, v):
    if v is None:
        return None
    return tuple(v) if key in TUPLE_KEYS else v


class Frame:
    def __init__(self, fields=None, overlay=None, ms=120):
        self.fields = {k: DEFAULT.__dict__[k] for k in FIELD_KEYS}
        self.fields.update(fields or {})
        self.overlay = dict(overlay or {})
        self.ms = ms

    def pose(self):
        return Pose(**self.fields)

    def copy(self):
        return Frame(self.fields, self.overlay, self.ms)

    def to_dict(self):
        return {"fields": {k: list(v) if isinstance(v, tuple) else v for k, v in self.fields.items()},
                "overlay": [[x, y, c] for (x, y), c in sorted(self.overlay.items())], "ms": self.ms}

    @staticmethod
    def from_dict(d):
        fields = {k: _tuple(k, v) for k, v in d.get("fields", {}).items() if k in FIELD_KEYS}
        overlay = {(x, y): c for x, y, c in d.get("overlay", []) if c in PAL}
        return Frame(fields, overlay, int(d.get("ms", 120)))

    @staticmethod
    def from_pose(p, ms):
        f = Frame({k: copy.copy(p.__dict__[k]) for k in FIELD_KEYS if k in p.__dict__}, ms=ms)
        for rows, x0, y0 in list(p.wear) + list(p.parts):
            for x, y, c in sprite.sprite_px(rows, x0, y0):
                if p.lift:
                    y += p.lift
                if p.flip:
                    x = 2 * (BX + 8) - x
                f.overlay[(x, y)] = c
        return f

    def pixels(self):
        try:
            px = list(layers(self.pose()))
        except Exception:
            px = []
        return px + [(x, y, c) for (x, y), c in self.overlay.items()]

    def out_of_canvas(self):
        return any(not (0 <= x < CW and 0 <= y < CH) for x, y, _c in self.pixels())


class Project:
    def __init__(self, name="my_animation"):
        self.name = name
        self.segments = {s: [] for s in SEGMENTS}

    def to_dict(self):
        return {"name": self.name, "segments": {s: [f.to_dict() for f in fr] for s, fr in self.segments.items()}}

    @staticmethod
    def from_dict(d):
        p = Project(d.get("name", "my_animation"))
        for s in SEGMENTS:
            p.segments[s] = [Frame.from_dict(f) for f in d.get("segments", {}).get(s, [])]
        return p

    @staticmethod
    def from_animation(name, anim):
        p = Project(name)
        for s in SEGMENTS:
            p.segments[s] = [Frame.from_pose(pose, ms) for pose, ms in anim.get(s, [])]
        return p


# ------------------------------------------------------------------ rendering
def palette_for(skin):
    sk = sprite.SKINS.get(skin)
    return dict(PAL, **sk) if sk else PAL


def paint_pixels(painter, pixels, scale, pal=PAL, ox=0, oy=0):
    for x, y, c in pixels:
        if 0 <= x < CW and 0 <= y < CH and c in pal:
            painter.fillRect(ox + x * scale, oy + y * scale, scale, scale, QColor(*pal[c]))


def frame_pixmap(frame, scale, bg=None, pal=PAL):
    pm = QPixmap(CW * scale, CH * scale)
    pm.fill(QColor(*bg) if bg else Qt.transparent)
    p = QPainter(pm)
    paint_pixels(p, frame.pixels(), scale, pal)
    p.end()
    return pm


# ------------------------------------------------------------------ code export
def ident(name):
    s = re.sub(r"\W", "_", name.strip().lower())
    if not s or s[0].isdigit():
        s = "anim_" + s
    return s


def _lit(v):
    if v is None or isinstance(v, (bool, int)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, (tuple, list)):
        body = ", ".join(_lit(i) for i in v)
        return f"({body},)" if len(v) == 1 else f"({body})"
    return repr(v)


def _call(head, args, indent):
    text = head + ", ".join(args) + ")"
    if len(text) + indent <= 100:
        return text
    lines, cur = [], head
    for i, a in enumerate(args):
        piece = a + ("," if i < len(args) - 1 else ")")
        if len(cur) + len(piece) + indent + 1 > 100 and cur.strip():
            lines.append(cur.rstrip())
            cur = " " * (len(head)) + ""
        cur += piece + " "
    lines.append(cur.rstrip())
    return ("\n" + " " * indent).join(lines)


def export_code(project):
    fn = ident(project.name)
    props, prop_names = [], {}

    def prop_for(overlay, fields):
        lift, flip = fields["lift"], fields["flip"]
        overlay = {((2 * (BX + 8) - x) if flip else x, y - lift): c for (x, y), c in overlay.items()}
        xs = [x for x, _ in overlay]
        ys = [y for _, y in overlay]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        rows = tuple("".join(overlay.get((x, y), ".") for x in range(x0, x1 + 1)) for y in range(y0, y1 + 1))
        if rows not in prop_names:
            prop_names[rows] = f"{fn.upper()}_{len(prop_names) + 1}"
            props.append((prop_names[rows], rows))
        return prop_names[rows], x0, y0

    blocks = {}
    for seg in SEGMENTS:
        lines = []
        for f in project.segments[seg]:
            args = [f"{k}={_lit(f.fields[k])}" for k in FIELD_KEYS if f.fields[k] != DEFAULT.__dict__[k]]
            if f.overlay:
                n, x0, y0 = prop_for(f.overlay, f.fields)
                args.append(f"parts=[({n}, {x0}, {y0})]")
            lines.append(f"        ({_call('Pose(', args, 10)}, {f.ms}),")
        blocks[seg] = lines

    out = [f'# Smellyfish animation "{project.name}"', "from smellyfish.art.sprite import Pose", ""]
    for name, rows in props:
        out.append(f"{name} = [")
        out += [f'    "{r}",' for r in rows]
        out += ["]", ""]
    out.append(f"def {fn}():")
    for seg in SEGMENTS:
        if seg == "loop" or blocks[seg]:
            out.append(f"    {seg} = [")
            out += blocks[seg]
            out.append("    ]")
    segs = ", ".join(f'"{s}": {s}' for s in SEGMENTS if s == "loop" or blocks[s])
    out += [f"    return {{{segs}}}", "", f'# "{fn}": {fn},', ""]
    return "\n".join(out)


# ------------------------------------------------------------------ pose form
class PoseForm(QWidget):
    edited = Signal()

    def __init__(self):
        super().__init__()
        self.frame = None
        self.loading = False
        self.before = lambda: None
        self.io = {}
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight)

        def row(label, widget):
            form.addRow(label, widget)

        def check(key, label):
            w = QCheckBox()
            w.toggled.connect(lambda _v, k=key: self._write(k))
            self.io[key] = (w.isChecked, w.setChecked)
            row(label, w)

        def choice(key, label, values, names=None):
            w = QComboBox()
            w.addItems(names or [str(v) for v in values])
            w.currentIndexChanged.connect(lambda _i, k=key: self._write(k))

            def get():
                return values[w.currentIndex()]

            def put(v):
                if v not in values:
                    values.append(v)
                    w.addItem(str(v))
                w.setCurrentIndex(values.index(v))
            self.io[key] = (get, put)
            row(label, w)

        def spin(key, label, lo=-12, hi=12):
            w = QSpinBox()
            w.setRange(lo, hi)
            w.valueChanged.connect(lambda _v, k=key: self._write(k))
            self.io[key] = (w.value, w.setValue)
            row(label, w)

        def pair(key, label, values):
            box, ws = QHBoxLayout(), []
            for _i in range(2):
                w = QComboBox()
                w.addItems(values)
                w.currentIndexChanged.connect(lambda _i2, k=key: self._write(k))
                ws.append(w)
                box.addWidget(w)

            def put(v):
                for w, x in zip(ws, v):
                    if x not in values:
                        values.append(x)
                        for o in ws:
                            o.addItem(x)
                    w.setCurrentIndex(values.index(x))
            self.io[key] = (lambda: tuple(w.currentText() for w in ws), put)
            form.addRow(label, box)

        check("side", "Side view")
        check("flip", "Mirror body")
        spin("dx", "Shift x")
        spin("dy", "Shift y")
        spin("lift", "Lift (all)")
        choice("eyes", "Eyes", EYES)
        spin("ex", "Eyes x", -3, 3)
        spin("ey", "Eyes y", -3, 3)
        choice("arm", "Arm (side)", ARMS_S)
        pair("arm_f", "Arms (front)", ARMS_F)
        choice("tent", "Tentacles", TENTS)
        check("curvy", "Wavy tentacles")
        self.tp = [QComboBox() for _ in range(4)]
        tpbox = QHBoxLayout()
        for w in self.tp:
            w.addItems(TPS)
            w.currentIndexChanged.connect(lambda _i: self._write("tp"))
            tpbox.addWidget(w)

        def tp_put(v):
            for w, x in zip(self.tp, v):
                w.setCurrentIndex(TPS.index(x) if x in TPS else 0)
        self.io["tp"] = (lambda: tuple(w.currentText() for w in self.tp), tp_put)
        form.addRow("Tentacle shapes", tpbox)
        check("typing", "Typing (side)")
        self.down = QLineEdit()
        self.down.setPlaceholderText("pressed keys, e.g. 3,5")
        self.down.textChanged.connect(lambda _t: self._write("down"))

        def down_get():
            return tuple(int(t) for t in re.findall(r"-?\d+", self.down.text()))
        self.io["down"] = (down_get, lambda v: self.down.setText(",".join(str(i) for i in v)))
        row("Keys down", self.down)
        self.lap = QComboBox()
        self.lap.addItems(["none"] + LAPTOPS[1:])
        self.lx, self.ly = QSpinBox(), QSpinBox()
        for s in (self.lx, self.ly):
            s.setRange(-20, 30)
            s.valueChanged.connect(lambda _v: self._write("laptop"))
        self.lap.currentIndexChanged.connect(lambda _i: self._write("laptop"))
        lb = QHBoxLayout()
        for w in (self.lap, self.lx, self.ly):
            lb.addWidget(w)

        def lap_get():
            return None if self.lap.currentIndex() == 0 else (self.lap.currentText(), self.lx.value(), self.ly.value())

        def lap_put(v):
            self.lap.setCurrentIndex(0 if not v else LAPTOPS.index(v[0]))
            self.lx.setValue(v[1] if v else sprite.LAP_X)
            self.ly.setValue(v[2] if v else sprite.LAP_Y)
        self.io["laptop"] = (lap_get, lap_put)
        form.addRow("Laptop", lb)
        check("blush", "Blush")
        check("squash", "Squash")
        check("cap", "Cap")
        check("band", "Headband")
        choice("headset", "Headset", HEADSETS)
        choice("mouth", "Mouth", MOUTHS)
        choice("tint", "Tint", TINTS)

    def load(self, frame):
        self.frame = frame
        self.loading = True
        for key, (_get, put) in self.io.items():
            put(frame.fields[key])
        self.loading = False
        self.setEnabled(frame is not None)

    def _write(self, key):
        if self.loading or self.frame is None:
            return
        v = self.io[key][0]()
        if self.frame.fields[key] == v:
            return
        self.before()
        self.frame.fields[key] = v
        self.edited.emit()


# ------------------------------------------------------------------ canvas
class Canvas(QWidget):
    stroke_start = Signal()
    changed = Signal()
    picked = Signal(str)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.zoom = 14
        self.tool = "brush"
        self.mirror = False
        self.onion = True
        self.setMouseTracking(True)
        self.setFixedSize(CW * self.zoom + 1, CH * self.zoom + 1)
        self.hover = None

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(*BG["Dark"]))
        fr = self.win.frame()
        pal = palette_for(self.win.skin)
        prev = self.win.prev_frame()
        if fr is not None:
            if self.onion and prev is not None:
                p.setOpacity(0.28)
                paint_pixels(p, prev.pixels(), self.zoom, pal)
                p.setOpacity(1.0)
            paint_pixels(p, fr.pixels(), self.zoom, pal)
        p.setPen(QPen(QColor(255, 255, 255, 22)))
        for x in range(CW + 1):
            p.drawLine(x * self.zoom, 0, x * self.zoom, CH * self.zoom)
        for y in range(CH + 1):
            p.drawLine(0, y * self.zoom, CW * self.zoom, y * self.zoom)
        p.setPen(QPen(QColor(255, 255, 255, 60)))
        cx = (MIRROR_C + 1) / 2 * self.zoom
        if self.mirror:
            p.drawLine(int(cx), 0, int(cx), CH * self.zoom)
        if self.hover:
            p.setPen(QPen(QColor(255, 255, 255, 160)))
            p.drawRect(self.hover[0] * self.zoom, self.hover[1] * self.zoom, self.zoom, self.zoom)

    def cell(self, e):
        x, y = int(e.position().x() // self.zoom), int(e.position().y() // self.zoom)
        return (x, y) if 0 <= x < CW and 0 <= y < CH else None

    def _apply(self, e, erase):
        fr, c = self.win.frame(), self.cell(e)
        if fr is None or c is None:
            return
        tool = "erase" if erase else self.tool
        if tool == "pick":
            for x, y, col in reversed(fr.pixels()):
                if (x, y) == c:
                    self.picked.emit(col)
                    break
            return
        cells = [c] + ([(MIRROR_C - c[0], c[1])] if self.mirror else [])
        for cell in cells:
            if not 0 <= cell[0] < CW:
                continue
            if tool == "erase":
                fr.overlay.pop(cell, None)
            elif tool == "brush":
                fr.overlay[cell] = self.win.color
        self.changed.emit()

    def mousePressEvent(self, e):
        if self.tool == "off" or self.win.frame() is None:
            return
        right = e.button() == Qt.RightButton
        if self.tool != "pick" or right:
            self.stroke_start.emit()
        self._apply(e, right)

    def mouseMoveEvent(self, e):
        self.hover = self.cell(e)
        if e.buttons() and self.tool in ("brush", "erase"):
            self._apply(e, e.buttons() & Qt.RightButton)
        self.update()

    def leaveEvent(self, _e):
        self.hover = None
        self.update()


# ------------------------------------------------------------------ main window
class Designer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smellyfish Animation Designer")
        self.project = Project()
        self.seg = "loop"
        self.idx = -1
        self.color = "W"
        self.skin = "lavender"
        self.path = None
        self.dirty = False
        self.undo, self.redo = [], []
        self.timer = QTimer(self, singleShot=True, timeout=self._tick)
        self.gen = None
        self.project.segments["loop"].append(Frame())
        self.idx = 0

        self.canvas = Canvas(self)
        self.canvas.stroke_start.connect(self.push_undo)
        self.canvas.changed.connect(self.pixels_changed)
        self.canvas.picked.connect(self.set_color)
        self.form = PoseForm()
        self.form.before = self.push_undo
        self.form.edited.connect(self.pixels_changed)

        self.setCentralWidget(self.build())
        self.build_toolbar()
        self.status = QLabel()
        self.statusBar().addWidget(self.status)
        for key, fn in (("Ctrl+Z", self.do_undo), ("Ctrl+Y", self.do_redo), ("Ctrl+Shift+Z", self.do_redo),
                        ("Ctrl+S", self.save), ("Ctrl+D", self.dup_frame), ("Space", self.toggle_play)):
            QShortcut(QKeySequence(key), self, activated=fn)
        self.refresh_all()
        self.resize(1360, 840)

    # ---- layout
    def build(self):
        split = QSplitter()

        left = QWidget()
        lv = QVBoxLayout(left)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name"))
        self.name_edit = QLineEdit(self.project.name)
        self.name_edit.textEdited.connect(self.rename)
        name_row.addWidget(self.name_edit)
        lv.addLayout(name_row)
        self.tabs = QTabBar()
        for s in SEGMENTS:
            self.tabs.addTab(s.capitalize())
        self.tabs.setCurrentIndex(SEGMENTS.index(self.seg))
        self.tabs.currentChanged.connect(self.set_segment)
        lv.addWidget(self.tabs)
        self.list = QListWidget()
        self.list.setIconSize(QSize(CW * 2, CH * 2))
        self.list.currentRowChanged.connect(self.select_row)
        lv.addWidget(self.list, 1)
        grid = QGridLayout()
        for i, (label, fn) in enumerate((("Add", self.add_frame), ("Duplicate", self.dup_frame),
                                         ("Delete", self.del_frame), ("Up", lambda: self.move_frame(-1)),
                                         ("Down", lambda: self.move_frame(1)))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            grid.addWidget(b, i // 3, i % 3)
        lv.addLayout(grid)
        dur = QHBoxLayout()
        dur.addWidget(QLabel("Duration (ms)"))
        self.ms = QSpinBox()
        self.ms.setRange(10, 10000)
        self.ms.setSingleStep(10)
        self.ms.valueChanged.connect(self.set_ms)
        dur.addWidget(self.ms)
        lv.addLayout(dur)
        split.addWidget(left)

        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.addWidget(self.canvas, 0, Qt.AlignCenter)
        tools = QHBoxLayout()
        self.tool_group = QButtonGroup(self)
        for key, label in (("brush", "Brush"), ("erase", "Eraser"), ("pick", "Pick"), ("off", "Look only")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key == "brush")
            b.clicked.connect(lambda _c, k=key: setattr(self.canvas, "tool", k))
            self.tool_group.addButton(b)
            tools.addWidget(b)
        mirror = QCheckBox("Mirror")
        mirror.toggled.connect(self.set_mirror)
        onion = QCheckBox("Previous frame")
        onion.setChecked(True)
        onion.toggled.connect(self.set_onion)
        tools.addWidget(mirror)
        tools.addWidget(onion)
        mv.addLayout(tools)
        shift = QHBoxLayout()
        shift.addWidget(QLabel("Move pixels"))
        for label, dx, dy in (("<", -1, 0), (">", 1, 0), ("^", 0, -1), ("v", 0, 1)):
            b = QToolButton()
            b.setText(label)
            b.clicked.connect(lambda _c, a=dx, c=dy: self.shift_pixels(a, c))
            shift.addWidget(b)
        clear = QPushButton("Clear pixels")
        clear.clicked.connect(self.clear_pixels)
        prev = QPushButton("Copy pixels from previous")
        prev.clicked.connect(self.copy_prev_pixels)
        shift.addWidget(clear)
        shift.addWidget(prev)
        shift.addStretch(1)
        mv.addLayout(shift)
        pal = QGridLayout()
        self.swatches = {}
        for i, key in enumerate(PAL):
            b = QPushButton()
            b.setFixedSize(26, 26)
            b.setToolTip(key)
            b.clicked.connect(lambda _c, k=key: self.set_color(k))
            pal.addWidget(b, i // 14, i % 14)
            self.swatches[key] = b
        mv.addLayout(pal)
        self.color_label = QLabel()
        mv.addWidget(self.color_label)
        mv.addStretch(1)
        split.addWidget(mid)

        right = QWidget()
        rv = QVBoxLayout(right)
        box = QGroupBox("Preview")
        bv = QVBoxLayout(box)
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumHeight(CH * 8 + 10)
        bv.addWidget(self.view)
        pr = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_play)
        outro = QPushButton("Play outro")
        outro.clicked.connect(self.play_outro)
        pr.addWidget(self.play_btn)
        pr.addWidget(outro)
        bv.addLayout(pr)
        opts = QHBoxLayout()
        self.zoom = QSpinBox()
        self.zoom.setRange(2, 14)
        self.zoom.setValue(8)
        self.zoom.valueChanged.connect(self.show_preview)
        self.bg = QComboBox()
        self.bg.addItems(list(BG))
        self.bg.currentIndexChanged.connect(self.show_preview)
        self.skin_box = QComboBox()
        self.skin_box.addItems(list(sprite.SKINS))
        self.skin_box.currentTextChanged.connect(self.set_skin)
        for lab, w in (("Zoom", self.zoom), ("Background", self.bg), ("Color", self.skin_box)):
            opts.addWidget(QLabel(lab))
            opts.addWidget(w)
        bv.addLayout(opts)
        rv.addWidget(box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        rv.addWidget(scroll, 1)
        split.addWidget(right)
        split.setSizes([250, 520, 440])
        return split

    def build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        for label, fn in (("New", self.new_project), ("Open", self.open_project), ("Save", self.save),
                          ("Save as", self.save_as), ("Import built-in", self.import_builtin),
                          ("Export code", self.export_file), ("Copy code", self.copy_code),
                          ("Undo", self.do_undo), ("Redo", self.do_redo)):
            tb.addAction(label, fn)

    # ---- state helpers
    def frames(self):
        return self.project.segments[self.seg]

    def frame(self):
        fr = self.frames()
        return fr[self.idx] if 0 <= self.idx < len(fr) else None

    def prev_frame(self):
        fr = self.frames()
        return fr[self.idx - 1] if 0 < self.idx < len(fr) else None

    def snapshot(self):
        return json.dumps({"p": self.project.to_dict(), "seg": self.seg, "idx": self.idx})

    def push_undo(self):
        self.undo.append(self.snapshot())
        del self.undo[:-150]
        self.redo.clear()
        self.dirty = True

    def restore(self, snap):
        d = json.loads(snap)
        self.project = Project.from_dict(d["p"])
        self.seg, self.idx = d["seg"], d["idx"]
        self.name_edit.setText(self.project.name)
        self.refresh_all()

    def do_undo(self):
        if self.undo:
            self.redo.append(self.snapshot())
            self.restore(self.undo.pop())

    def do_redo(self):
        if self.redo:
            self.undo.append(self.snapshot())
            self.restore(self.redo.pop())

    # ---- refresh
    def refresh_all(self):
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(SEGMENTS.index(self.seg))
        for i, s in enumerate(SEGMENTS):
            self.tabs.setTabText(i, f"{s.capitalize()} ({len(self.project.segments[s])})")
        self.tabs.blockSignals(False)
        self.fill_list()
        self.load_frame()
        self.refresh_swatches()

    def fill_list(self):
        self.list.blockSignals(True)
        self.list.clear()
        pal = palette_for(self.skin)
        for i, f in enumerate(self.frames()):
            it = QListWidgetItem(QIcon(frame_pixmap(f, 2, BG["Dark"], pal)), f"{i + 1}   {f.ms} ms")
            if f.out_of_canvas():
                it.setForeground(QColor(220, 70, 70))
            self.list.addItem(it)
        self.idx = min(self.idx, len(self.frames()) - 1)
        self.list.setCurrentRow(self.idx)
        self.list.blockSignals(False)

    def load_frame(self):
        fr = self.frame()
        self.form.load(fr) if fr else self.form.setEnabled(False)
        self.ms.blockSignals(True)
        self.ms.setValue(fr.ms if fr else 120)
        self.ms.blockSignals(False)
        self.ms.setEnabled(fr is not None)
        self.canvas.update()
        self.update_status()
        if not self.gen:
            self.show_preview()

    def pixels_changed(self):
        self.dirty = True
        self.canvas.update()
        it = self.list.item(self.idx)
        fr = self.frame()
        if it and fr:
            it.setIcon(QIcon(frame_pixmap(fr, 2, BG["Dark"], palette_for(self.skin))))
            it.setForeground(QColor(220, 70, 70) if fr.out_of_canvas() else self.list.palette().text())
        self.update_status()
        if not self.gen:
            self.show_preview()

    def update_status(self):
        bad = [f"{s} {i + 1}" for s in SEGMENTS for i, f in enumerate(self.project.segments[s]) if f.out_of_canvas()]
        total = sum(f.ms for s in SEGMENTS for f in self.project.segments[s])
        text = f"{total} ms total"
        if bad:
            text += "   |   pixels outside the 34x28 canvas: " + ", ".join(bad[:6])
        self.status.setText(text)

    def refresh_swatches(self):
        for key, b in self.swatches.items():
            r, g, bl = palette_for(self.skin)[key]
            border = "#fff" if key == self.color else "#555"
            b.setStyleSheet(f"background: rgb({r},{g},{bl}); border: 2px solid {border};")
        self.color_label.setText(f"Color: {self.color}")

    def set_color(self, key):
        self.color = key
        self.refresh_swatches()

    def set_skin(self, name):
        self.skin = name
        self.refresh_swatches()
        self.fill_list()
        self.canvas.update()
        self.show_preview()

    def set_mirror(self, on):
        self.canvas.mirror = on
        self.canvas.update()

    def set_onion(self, on):
        self.canvas.onion = on
        self.canvas.update()

    # ---- frame / segment ops
    def rename(self, text):
        self.project.name = text
        self.dirty = True

    def set_segment(self, i):
        self.stop()
        self.seg = SEGMENTS[i]
        self.idx = 0 if self.frames() else -1
        self.fill_list()
        self.load_frame()

    def select_row(self, row):
        if row < 0:
            return
        self.idx = row
        self.load_frame()

    def add_frame(self):
        self.push_undo()
        self.frames().append(Frame())
        self.idx = len(self.frames()) - 1
        self.refresh_all()

    def dup_frame(self):
        fr = self.frame()
        if not fr:
            return
        self.push_undo()
        self.frames().insert(self.idx + 1, fr.copy())
        self.idx += 1
        self.refresh_all()

    def del_frame(self):
        if not self.frame():
            return
        self.push_undo()
        del self.frames()[self.idx]
        self.idx = min(self.idx, len(self.frames()) - 1)
        self.refresh_all()

    def move_frame(self, d):
        j = self.idx + d
        fr = self.frames()
        if not self.frame() or not 0 <= j < len(fr):
            return
        self.push_undo()
        fr[self.idx], fr[j] = fr[j], fr[self.idx]
        self.idx = j
        self.refresh_all()

    def set_ms(self, v):
        fr = self.frame()
        if fr and fr.ms != v:
            self.push_undo()
            fr.ms = v
            self.list.item(self.idx).setText(f"{self.idx + 1}   {v} ms")
            self.update_status()

    def shift_pixels(self, dx, dy):
        fr = self.frame()
        if not fr or not fr.overlay:
            return
        self.push_undo()
        fr.overlay = {(x + dx, y + dy): c for (x, y), c in fr.overlay.items()
                      if 0 <= x + dx < CW and 0 <= y + dy < CH}
        self.pixels_changed()

    def clear_pixels(self):
        fr = self.frame()
        if fr and fr.overlay:
            self.push_undo()
            fr.overlay = {}
            self.pixels_changed()

    def copy_prev_pixels(self):
        fr, prev = self.frame(), self.prev_frame()
        if fr and prev:
            self.push_undo()
            fr.overlay = dict(prev.overlay)
            self.pixels_changed()

    # ---- preview
    def show_preview(self, frame=None):
        frame = frame if isinstance(frame, Frame) else self.frame()
        if frame is None:
            self.view.clear()
            return
        self.view.setPixmap(frame_pixmap(frame, self.zoom.value(), BG[self.bg.currentText()],
                                         palette_for(self.skin)))

    def _sequence(self, outro_only=False):
        s = self.project.segments
        if outro_only:
            yield from s["outro"]
            return
        yield from s["intro"]
        if s["loop"]:
            while True:
                yield from s["loop"]

    def start(self, outro_only=False):
        self.stop()
        self.gen = self._sequence(outro_only)
        self.play_btn.setText("Stop")
        self._tick()

    def _tick(self):
        if not self.gen:
            return
        fr = next(self.gen, None)
        if fr is None:
            self.stop(keep_last=True)
            return
        self.show_preview(fr)
        self.timer.start(max(10, fr.ms))

    def stop(self, keep_last=False):
        self.timer.stop()
        self.gen = None
        self.play_btn.setText("Play")
        if not keep_last:
            self.show_preview()

    def toggle_play(self):
        self.stop() if self.gen else self.start()

    def play_outro(self):
        self.start(outro_only=True)

    # ---- files
    def confirm_discard(self):
        if not self.dirty:
            return True
        r = QMessageBox.question(self, "Unsaved changes", "Discard unsaved changes?")
        return r == QMessageBox.Yes

    def new_project(self):
        if not self.confirm_discard():
            return
        self.stop()
        self.project = Project()
        self.project.segments["loop"].append(Frame())
        self.seg, self.idx, self.path, self.dirty = "loop", 0, None, False
        self.undo.clear()
        self.redo.clear()
        self.name_edit.setText(self.project.name)
        self.refresh_all()

    def default_dir(self):
        return SAVE_DIR if os.path.isdir(SAVE_DIR) else (os.path.join(ROOT, "dev") if os.path.isdir(
            os.path.join(ROOT, "dev")) else ROOT)

    def open_project(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", self.default_dir(), "Designer project (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                self.project = Project.from_dict(json.load(f))
        except (OSError, ValueError, KeyError, TypeError) as e:
            QMessageBox.warning(self, "Open", f"Could not open the file:\n{e}")
            return
        self.stop()
        self.path, self.dirty = path, False
        self.seg = "loop"
        self.idx = 0 if self.frames() else -1
        self.undo.clear()
        self.redo.clear()
        self.name_edit.setText(self.project.name)
        self.refresh_all()

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.project.to_dict(), f)
        except OSError as e:
            QMessageBox.warning(self, "Save", f"Could not save:\n{e}")
            return
        self.dirty = False
        self.statusBar().showMessage(f"Saved {self.path}", 3000)

    def save_as(self):
        if os.path.isdir(os.path.join(ROOT, "dev")):
            os.makedirs(SAVE_DIR, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Save project",
                                              os.path.join(self.default_dir(), ident(self.project.name) + ".json"),
                                              "Designer project (*.json)")
        if path:
            self.path = path
            self.save()

    def import_builtin(self):
        names = sorted(sprite.ANIMATIONS)
        name, ok = QInputDialog.getItem(self, "Import built-in", "Animation", names, 0, False)
        if not ok or not self.confirm_discard():
            return
        self.stop()
        self.project = Project.from_animation(name, sprite.ANIMATIONS[name]())
        self.seg = "loop" if self.project.segments["loop"] else next(
            (s for s in SEGMENTS if self.project.segments[s]), "loop")
        self.idx = 0 if self.frames() else -1
        self.path, self.dirty = None, False
        self.undo.clear()
        self.redo.clear()
        self.name_edit.setText(name)
        self.refresh_all()

    def code(self):
        return export_code(self.project)

    def check_export(self):
        if not any(self.project.segments[s] for s in SEGMENTS):
            QMessageBox.information(self, "Export", "There are no frames yet.")
            return False
        if any(f.out_of_canvas() for s in SEGMENTS for f in self.project.segments[s]):
            r = QMessageBox.question(self, "Export", "Some frames have pixels outside the canvas, which the "
                                     "game cannot draw. Export anyway?")
            return r == QMessageBox.Yes
        return True

    def export_file(self):
        if not self.check_export():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export code",
                                              os.path.join(self.default_dir(), ident(self.project.name) + ".py"),
                                              "Python (*.py)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.code())
        except OSError as e:
            QMessageBox.warning(self, "Export", f"Could not write the file:\n{e}")
            return
        self.statusBar().showMessage(f"Exported {path}", 4000)

    def copy_code(self):
        if self.check_export():
            QApplication.clipboard().setText(self.code())
            self.statusBar().showMessage("Code copied to the clipboard", 3000)

    def closeEvent(self, e):
        if self.confirm_discard():
            self.stop()
            e.accept()
        else:
            e.ignore()


def main():
    app = QApplication(sys.argv)
    win = Designer()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
