"""Smellyfish sprites and animations.

Pixel art lives in text rasters: '#' body, 'L' highlight, 'D' shade, 'O' eye, '.' empty.
A Pose is turned into pixels by layers(); animations are lists of (Pose, ms) split into
intro / loop / outro segments so the app can blend states cleanly.
"""
from PIL import Image, ImageDraw

FRONT = [
    "..LLLLLL######..",
    ".LLL#########DD.",
    ".L############D.",
    ".L############D.",
    ".L############D.",
    ".L############D.",
    ".L############D.",
    ".L############D.",
    ".DDDDDDDDDDDDDD.",
]
SIDE = [
    "...LLLL####...",
    "..LLL######D..",
    ".LL#########D.",
    ".L##########D.",
    ".L##########D.",
    ".L##########D.",
    ".L##########D.",
    ".L##########D.",
    ".DDDDDDDDDDDD.",
]
CW, CH = 34, 28
BX, BY = 4, 11
FEET = BY + 12
PAL = {
    "#": (196, 146, 236), "L": (226, 192, 250), "D": (140, 96, 190), "O": (34, 22, 52),
    "g": (150, 156, 172), "G": (92, 97, 114), "k": (204, 208, 220), "K": (255, 255, 255),
    "S": (120, 200, 255), "n": (22, 24, 38), "c": (130, 230, 150), "Y": (255, 210, 80),
    "W": (255, 255, 255), "P": (240, 120, 160), "B": (90, 150, 255),
    "R": (235, 80, 90), "p": (246, 170, 200), "w": (190, 196, 214),
    "b": (150, 100, 70), "T": (196, 104, 70), "t": (226, 140, 100), "v": (70, 160, 90), "o": (160, 140, 70),
    "y": (255, 236, 150), "H": (60, 62, 80), "h": (120, 124, 146),
    "X": (232, 86, 86), "x": (250, 150, 140), "Z": (168, 48, 60), "U": (88, 101, 242),
    "q": (110, 72, 50), "e": (60, 40, 70), "a": (255, 160, 60),
}
TINTS = {"red": {"#": "X", "L": "x", "D": "Z"}, "xray": {"#": "n", "L": "n", "D": "n", "O": "n"}}

LAPTOP = {
    "open": [
        "..............Sg.",
        "..............Sg.",
        ".............Sg..",
        ".............Sg..",
        ".............Sg..",
        "............Sg...",
        "............Sg...",
        "............Sg...",
        "kkkkkkkkkkkkgg...",
        "GGGGGGGGGGGGGG...",
    ],
    "half": [
        ".................",
        ".................",
        ".................",
        ".......g.........",
        ".......Sg........",
        "........Sg.......",
        ".........Sg......",
        "..........Sg.....",
        "kkkkkkkkkkkSgg...",
        "GGGGGGGGGGGGGG...",
    ],
    "closed": [
        ".................",
        ".................",
        ".................",
        ".................",
        ".................",
        ".................",
        ".................",
        ".................",
        "gggggggggggggg...",
        "GGGGGGGGGGGGGG...",
    ],
}
KEY_ROW = 8
GLYPHS = [[".c", "c.", ".c"], ["..S", ".S.", "S.."], ["c.", ".c", "c."], ["Y.Y", ".Y.", "Y.Y"]]
CHECK = ["....c", "...c.", "c.c..", ".c..."]
CLOUD = [
    ".WWWWWWW.",
    "WWWWWWWWW",
    "WWWWWWWWW",
    "WWWWWWWWW",
    ".WWWWWWW.",
]
ASK = [
    ".WWWWW.",
    "WWOOOWW",
    "WWWWOWW",
    "WWWOOWW",
    "WWWOWWW",
    "WWWWWWW",
    "WWWOWWW",
    ".WWWWW.",
    ".WW....",
    "W......",
]
HEART = [".P.P.", "PPPPP", ".PPP.", "..P.."]
BANG = ["RR", "RR", "RR", "..", "RR"]
def checkoff():
    board = lambda n, dy=0: [(_clipboard(n), BX + 16, BY + dy)]
    arms = ("rest_l", "up_r")
    intro = [(Pose(ex=1, ey=1, arm_f=arms, parts=board(0)), 160),
             (Pose(ex=1, ey=1, arm_f=("rest_l", "wave_r"), parts=board(0)), 140),
             (Pose(ex=1, ey=1, arm_f=arms, parts=board(0)), 140),
             (Pose(ex=1, ey=1, arm_f=("rest_l", "wave_r"), parts=board(1)), 200),
             (Pose(eyes="happy", blush=True, dy=-1, tent="long", arm_f=("up_l", "up_r"),
                   parts=board(1, -1) + [(SPARKLE, BX + 14, BY - 4)]), 220),
             (Pose(eyes="happy", blush=True, arm_f=("rest_l", "up_r"),
                   parts=board(1) + [(SPARKLE, BX + 18, BY - 5)]), 260),
             (Pose(eyes="happy"), 200)]
    return {"intro": intro, "loop": []}


ZZZ = ["WWWW", "..W.", ".W..", "WWWW"]
ZZZ_DIM = ["wwww", "..w.", ".w..", "wwww"]
CAP = [
    "..........BBW...",
    "......BBBBBB....",
    "....BBBBBBBB....",
    "..WWWWWWWWWWWW..",
]
FLAG = [
    ["WGWG", "GWGW", "WGWG", "...."],
    ["WG..", "GWWG", "WGGW", "..WG"],
]

# front view (16 wide, body x1..14)
F_TENT = (3, 6, 9, 12)
F_EYES = (4, 11)
F_ARMS = {
    "rest_l": [(0, 5)], "rest_r": [(15, 5)],
    "up_l": [(0, 4), (-1, 3), (-1, 2)],
    "up_r": [(15, 4), (16, 3), (16, 2)],
    "wave_r": [(15, 4), (16, 3), (17, 3)],
    "flag_r": [(15, 4), (16, 3)],
}
F_TP = {
    "s1": [(0, 0), (1, 1), (0, 2)],
    "s2": [(0, 0), (-1, 1), (0, 2)],
    "hang": [(0, 0), (0, 1), (0, 2)],
}

# side view, facing right (14 wide, body x1..12)
S_TENT = (2, 5, 8, 11)
S_EYES = (6, 10)
S_ARM = {"rest": [(13, 5)]}
LAP_X, LAP_Y = 2, 6

TP = {
    "s1": [(0, 0), (1, 1), (1, 2), (0, 3)],
    "s2": [(0, 0), (-1, 1), (-1, 2), (0, 3)],
    "hang": [(0, 0), (0, 1), (0, 2), (1, 3)],
    "hook": [(0, 0), (0, 1), (1, 2), (2, 2)],
    "press": [(0, 0), (1, 1), (1, 2), (1, 3), (1, 4)],
    "press2": [(0, 0), (-1, 1), (0, 2), (1, 3), (1, 4)],
}
WAVE = ("s1", "hang", "s2", "hang")


def wave(t):
    return tuple(WAVE[(t + k) % 4] for k in range(4))


class Pose:
    def __init__(self, **kw):
        self.side = False
        self.dx, self.dy = 0, 0
        self.eyes, self.ex, self.ey = "open", 0, 0
        self.arm = "rest"
        self.tent = "straight"
        self.arm_f = ("rest_l", "rest_r")
        self.curvy = False
        self.typing = False
        self.down = ()
        self.tp = ("hang",) * 4
        self.tent_px = None
        self.laptop = None
        self.blush = False
        self.squash = False
        self.cap = False
        self.lift = 0
        self.headset = None
        self.tint = None
        self.mouth = None
        self.band = False
        self.flip = False
        self.parts = []
        self.wear = []
        self.__dict__.update(kw)

    def but(self, **kw):
        p = Pose(**self.__dict__)
        p.parts = list(self.parts)
        p.wear = list(self.wear)
        p.__dict__.update(kw)
        return p


def sprite_px(rows, x0, y0):
    return [(x0 + x, y0 + y, c) for y, r in enumerate(rows) for x, c in enumerate(r) if c != "."]


def strand(x, kind, rows=3, root=9):
    out = 1 if x >= 8 else -1
    if kind == "tuck" and x in (2, 3, 11, 12):
        x -= out
    if kind == "spread":
        return [(x, root), (x + out, root + 1), (x + out, root + 2)]
    if kind in ("swing_l", "swing_r"):
        s = -1 if kind == "swing_l" else 1
        return [(x, root), (x, root + 1), (x + s, root + 2), (x + s, root + 3)]
    if kind == "long":
        rows = 4
    shift = {"left": -1, "right": 1}.get(kind, 0)
    return [(x, root + r) for r in range(rows - 1)] + [(x + shift, root + rows - 1)]


def eye_px(p, anchors):
    lx, rx = anchors[0] + p.ex, anchors[1] + p.ex
    y = 4 + p.ey
    if p.eyes == "open":
        return [(lx, y), (lx, y + 1), (rx, y), (rx, y + 1)]
    if p.eyes == "blink":
        return [(lx, y + 1), (rx, y + 1)]
    if p.eyes == "happy":
        return [(lx, y), (lx - 1, y + 1), (lx + 1, y + 1), (rx, y), (rx - 1, y + 1), (rx + 1, y + 1)]
    if p.eyes == "sleep":
        return [(lx - 1, y + 1), (lx, y + 1), (rx, y + 1), (rx + 1, y + 1)]
    if p.eyes == "wide":
        return [(lx, y - 1), (lx, y), (lx, y + 1), (rx, y - 1), (rx, y), (rx, y + 1)]
    if p.eyes == "angry":
        return [(lx, y), (lx, y + 1), (rx, y), (rx, y + 1), (lx - 1, y - 2), (lx, y - 1), (rx + 1, y - 2),
                (rx, y - 1)]
    if p.eyes == "x":
        return [(e + a, y + b) for e in (lx, rx) for a, b in ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1))]
    return []


def tent_offsets(p):
    """The four front-view tentacles of a pose as pixel offsets from their roots (for easing the simulation)."""
    out = []
    for k, x in enumerate(F_TENT):
        if p.curvy and p.tent == "straight":
            out.append(list(F_TP.get(p.tp[k], F_TP["hang"])))
        else:
            out.append([(a - x, b - 9) for a, b in strand(x, p.tent)])
    return out


def layers(p):
    """All pixels of a pose as (x, y, colour key), in draw order."""
    out = []
    if p.laptop:
        lap = list(LAPTOP[p.laptop[0]])
        for x in p.down:
            k = x + 1 + p.dx - p.laptop[1]
            if 0 <= k < 12:
                lap[KEY_ROW] = lap[KEY_ROW][:k] + "K" + lap[KEY_ROW][k + 1:]
        out += sprite_px(lap, BX + 1 + p.laptop[1], BY + p.laptop[2])

    if p.side:
        ox, oy = BX + 1 + p.dx, BY + p.dy
        for k, x in enumerate(S_TENT):
            if p.typing:
                name = p.tp[k] if p.tp[k].startswith("press") or x not in p.down else "press"
                pts = [(x + a, 9 + b) for a, b in TP[name]]
                if name.startswith("press") and p.dy < 0:
                    pts.append((pts[-1][0], pts[-1][1] - p.dy))
            else:
                pts = strand(x, p.tent)
            out += [(ox + a, oy + b, "D" if i == len(pts) - 1 else "#") for i, (a, b) in enumerate(pts)]
        out += sprite_px(SIDE, ox, oy)
        out += [(ox + x, oy + y, "O") for x, y in eye_px(p, S_EYES)]
        if p.band:
            out += [(ox + x, oy + 2, "R") for x in range(2, 13)] + [(ox + 1, oy + 1, "R"), (ox, oy + 3, "R")]
        if p.headset:
            out += sprite_px(SIDE_HEADSET if p.headset == "mic" else SIDE_HEADPHONES, ox, oy - 1)
        out += [(ox + x, oy + y, "#") for x, y in S_ARM[p.arm]]
    else:
        ox, oy = BX + p.dx, BY + p.dy
        body, root = FRONT, 9
        if p.squash:
            body, root, oy = FRONT[:6] + FRONT[7:], 8, oy + 1
        for k, x in enumerate(F_TENT):
            if p.tent_px:
                pts = [(x + a, root + b) for a, b in p.tent_px[k]]
            elif p.curvy and p.tent == "straight":
                pts = [(x + a, root + b) for a, b in F_TP.get(p.tp[k], F_TP["hang"])]
            else:
                pts = strand(x, p.tent, root=root)
            out += [(ox + a, oy + b, "D" if i == len(pts) - 1 else "#") for i, (a, b) in enumerate(pts)]
        out += sprite_px(body, ox, oy)
        if p.blush:
            out += [(ox + x, oy + 6, "p") for x in (2, 3, 12, 13)]
        out += [(ox + x, oy + y, "O") for x, y in eye_px(p, F_EYES)]
        if p.cap:
            out += sprite_px(CAP, ox, oy - 3)
        if p.band:
            out += [(ox + x, oy + 2, "R") for x in range(2, 14)] + [(ox + 14, oy + 2, "R"), (ox + 15, oy + 3, "R"),
                                                                   (ox + 15, oy + 1, "R")]
        if p.mouth:
            rows = 3 if p.mouth == "big" else 2
            out += [(ox + x, oy + 7 + y, "O") for x in (7, 8) for y in range(rows)]
        if p.headset:
            out += sprite_px(HEADSET if p.headset == "mic" else HEADPHONES, ox, oy - 1)
        out += [(ox + x, oy + y, "L") for x, y in F_ARMS[p.arm_f[0]]]
        out += [(ox + x, oy + y, "#") for x, y in F_ARMS[p.arm_f[1]]]

    n_body = len(out)
    for spr, x, y in p.wear:
        out += sprite_px(spr, x, y)
    for spr, x, y in p.parts:
        out += sprite_px(spr, x, y)
    if p.tint:
        t = TINTS[p.tint]
        out = [(x, y, t.get(c, c)) if i < n_body else (x, y, c) for i, (x, y, c) in enumerate(out)]
    if p.lift:
        out = [(x, y + p.lift, c) for x, y, c in out]
    if p.flip:
        out = [(2 * (BX + 8) - x, y, c) for x, y, c in out]
    return out


def render(p, scale=1, bg=None, pal=None):
    """Pose -> PIL image. bg=None gives a transparent RGBA image; pal overrides colours (skins)."""
    colors = dict(PAL, **pal) if pal else PAL
    img = Image.new("RGBA" if bg is None else "RGB", (CW * scale, CH * scale), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, c in layers(p):
        assert 0 <= x < CW and 0 <= y < CH, f"pixel out of canvas: {(x, y, c)}"
        d.rectangle([x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1], fill=colors[c])
    return img


SKINS = {
    "lavender": None,
    "pink": {"#": (246, 150, 190), "L": (255, 205, 225), "D": (196, 96, 146)},
    "blue": {"#": (120, 170, 240), "L": (185, 215, 255), "D": (70, 110, 190)},
    "mint": {"#": (120, 215, 175), "L": (195, 250, 222), "D": (60, 155, 125)},
    "peach": {"#": (250, 170, 120), "L": (255, 218, 185), "D": (205, 118, 78)},
    "night": {"#": (96, 94, 156), "L": (140, 140, 204), "D": (60, 58, 108)},
    "lemon": {"#": (245, 215, 100), "L": (255, 240, 170), "D": (200, 160, 60)},
    "snow": {"#": (220, 225, 240), "L": (246, 248, 255), "D": (156, 165, 200)},
}


def skin_from_color(rgb):
    r, g, b = rgb
    light = tuple(int(c + (255 - c) * 0.45) for c in rgb)
    dark = tuple(int(c * 0.68) for c in rgb)
    return {"#": (r, g, b), "L": light, "D": dark}


# ---------------------------------------------------------------- idle
def idle():
    b = Pose()
    loop = [
        (b, 420),
        (b.but(tent="tuck"), 160),
        (b.but(dy=-1, tent="long"), 70),
        (b.but(dy=-2, tent="long"), 70),
        (b.but(dy=-3, tent="long"), 110),
        (b.but(dy=-3), 260),
        (b.but(dy=-3, eyes="blink"), 90),
        (b.but(dy=-3), 200),
        (b.but(dy=-2, tent="left"), 300),
        (b.but(dy=-1, tent="left"), 300),
        (b.but(dy=-1), 260),
        (b.but(dy=0, tent="right"), 300),
        (b.but(dy=0), 260),
    ]
    return {"loop": loop}


# ---------------------------------------------------------------- working (laptop)
def working():
    intro, loop, outro = [], [], []
    intro.append((Pose(ex=1), 200))
    side = Pose(side=True)
    intro.append((side.but(eyes="blink"), 90))
    intro.append((side, 200))
    look = side.but(ex=-1, ey=1)
    intro.append((look, 220))
    path = [(0, -3), (0, -1), (1, 1), (1, 3), (LAP_X + 1, LAP_Y), (LAP_X, LAP_Y)]
    for i, (x, y) in enumerate(path):
        intro.append((look.but(laptop=("closed", x, y), tent="right" if i else "tuck", ex=0,
                               lift=(-1, -2, -3, -4, -4, -4)[i]), (120, 80, 80, 80, 80, 160)[i]))
    seat = side.but(laptop=("closed", LAP_X, LAP_Y), typing=True, ey=1, lift=-4)
    intro.append((seat, 180))
    for st_, ms in (("half", 70), ("open", 120)):
        intro.append((seat.but(laptop=(st_, LAP_X, LAP_Y)), ms))
    work = seat.but(laptop=("open", LAP_X, LAP_Y), ey=0, ex=1)
    intro.append((work.but(tp=wave(0)), 160))
    intro.append((work.but(tp=wave(1)), 140))

    chords = [(11,), (2,), (8,), (5,), (11, 2), (8,), (5,), (2,), (11,), (5, 8), (2,), (11,)]
    gx, gy = BX + 1 + LAP_X + 15, BY + LAP_Y - 5
    st = {"i": 0, "parts": []}

    def tick():
        out = [(spr, x, y - age // 2) for spr, x, y, age in st["parts"]]
        st["parts"] = [[spr, x, y, age + 1] for spr, x, y, age in st["parts"] if age + 1 < 7]
        return out

    def burst(n):
        for _ in range(n):
            i = st["i"]
            ch = chords[i % len(chords)]
            if i % 3 == 1:
                st["parts"].append([GLYPHS[(i // 3) % 4], gx + (i // 3) % 2, gy, 0])
            st["i"] += 1
            dy = -1 if (i // 2) % 2 else 0
            rest = wave(2 * i)
            tp = tuple(("press", "press2")[(i + k) % 2] if x in ch else rest[k] for k, x in enumerate(S_TENT))
            loop.append((work.but(dy=dy, down=ch, tp=tp, parts=tick()), 55))
            loop.append((work.but(dy=dy, tp=wave(2 * i + 1), parts=tick()), 40))

    burst(12)
    loop += [(work.but(tp=wave(0), parts=tick()), 140), (work.but(tp=wave(1), parts=tick()), 140),
             (work.but(tp=wave(2), eyes="blink", parts=tick()), 90), (work.but(tp=wave(2), parts=tick()), 120),
             (work.but(tp=wave(3), ex=0, ey=-1, parts=tick()), 200),
             (work.but(tp=wave(0), ex=0, ey=-1, parts=tick()), 200), (work.but(tp=wave(1), parts=tick()), 160)]
    burst(10)
    for t in range(8):
        loop.append((work.but(tp=wave(t // 2), parts=tick()), 150))

    outro.append((work.but(tp=("hook",) * 4), 90))
    outro.append((work.but(dy=-2, tp=("hook",) * 4), 180))
    outro.append((work.but(down=S_TENT, tp=("press",) * 4), 120))
    happy = work.but(eyes="happy", ex=0, tp=wave(0))
    for i in range(3):
        outro.append((happy.but(tp=wave(i), parts=[(CHECK, gx - 3, gy - (1 if i >= 2 else 0))]), 120))
    for st_, ms in (("half", 70), ("closed", 110)):
        outro.append((happy.but(laptop=(st_, LAP_X, LAP_Y)), ms))
    stow = happy.but(typing=False)
    for i, (x, y) in enumerate(reversed(path[:-1])):
        outro.append((stow.but(laptop=("closed", x, y), tent="left" if i < 4 else "tuck", lift=-4 + i), 70))
    outro.append((stow.but(laptop=None, lift=0), 140))
    outro.append((Pose(eyes="happy"), 200))
    outro.append((Pose(), 160))
    return {"intro": intro, "loop": loop, "outro": outro}


# ---------------------------------------------------------------- thinking
def thinking():
    loop = []
    base = Pose(curvy=True, ex=1, ey=-1)
    cx, cy = 20, BY - 7
    trail = [(["W"], 17, BY - 1), (["WW", "WW"], 18, BY - 3)]
    dots = [0, 1, 2, 3, 3]
    for t in range(10):
        n = dots[t % 5]
        cloud = [(CLOUD, cx, cy)] + [(["B"], cx + 2 + 2 * k, cy + 2) for k in range(n)]
        p = base.but(tp=wave(t), parts=trail + cloud, dy=-1 if 4 <= t < 9 else 0)
        if t == 7:
            p = p.but(ex=0)
        loop.append((p, 280))
        if t == 2:
            loop.append((p.but(eyes="blink"), 90))
    return {"intro": [(Pose(curvy=True, ex=1, ey=-1, parts=[(["W"], 17, BY - 1)]), 120)], "loop": loop}


def load_bar(n):
    return ["wwwwwwwwwww", "w" + "c" * n + "." * (9 - n) + "w", "wwwwwwwwwww"]


def ponder():
    """Waiting for the local model to wake up: thought cloud with cycling dots and a loading bar."""
    loop = []
    base = Pose(curvy=True, ex=1, ey=-1)
    cx, cy = 20, BY - 7
    trail = [(["W"], 17, BY - 1), (["WW", "WW"], 18, BY - 3)]
    for t in range(12):
        n = t % 4
        cloud = [(CLOUD, cx, cy)] + [(["B"], cx + 2 + 2 * k, cy + 2) for k in range(n)]
        bar = (load_bar(min(9, t + 1 if t < 9 else 9)), 22, BY + 6)
        loop.append((base.but(tp=wave(t), parts=trail + cloud + [bar], dy=-1 if t % 6 >= 3 else 0), 260))
    return {"intro": [(Pose(curvy=True, ex=1, ey=-1, parts=[(["W"], 17, BY - 1)]), 120)], "loop": loop}


# ---------------------------------------------------------------- question / needs attention
def question(mark=False):
    bub = (lambda off=0: [(ASK, 21, BY - 6 + off)]) if mark else (lambda off=0: [])
    base = Pose(parts=bub())
    intro = [(base, 120)]
    for dy, tent, arm, ms in ((0, "tuck", "rest_r", 110), (-1, "long", "up_r", 60), (-2, "long", "up_r", 60),
                              (-3, "straight", "up_r", 140), (-2, "straight", "up_r", 80),
                              (-1, "straight", "up_r", 70), (0, "tuck", "up_r", 110)):
        intro.append((base.but(dy=dy, tent=tent, arm_f=("rest_l", arm)), ms))
    loop = []
    for i in range(6):
        loop.append((base.but(arm_f=("rest_l", ("wave_r", "up_r")[i % 2]), parts=bub(-(i % 2))), 170))
    loop += [(base.but(arm_f=("rest_l", "up_r")), 400), (base.but(arm_f=("rest_l", "up_r"), eyes="blink"), 90),
             (base.but(arm_f=("rest_l", "up_r")), 600)]
    outro = [(base.but(), 160)]
    return {"intro": intro, "loop": loop, "outro": outro}


# ---------------------------------------------------------------- done
CONFETTI = [(-2, -3, "P"), (-1, -4, "Y"), (1, -4, "c"), (2, -3, "S"), (-3, -1, "Y"), (3, -2, "P"),
            (0, -5, "S"), (-2, -5, "c"), (2, -5, "Y"), (4, -4, "c")]


def done():
    intro, loop = [], []
    happy = Pose(eyes="happy")

    def flag(oy, k):
        return [(FLAG[k], BX + 18, oy - 3), (["g"] * 8, BX + 17, oy - 3)]

    intro.append((happy.but(tent="tuck"), 130))
    sx, sy = BX + 8, BY - 1
    conf = []

    def tick():
        out = []
        for c in conf:
            x0, y0, vx, vy, col, age = c
            x = x0 + vx * age // 2
            y = y0 + vy * age // 2 + (age * age) // 6
            if 0 <= x < CW and 0 <= y < CH:
                out.append(([col], x, y))
            c[5] += 1
        return out

    seq = [(-2, "long", 60), (-4, "long", 80), (-4, "straight", 150), (-3, "straight", 70),
           (-1, "straight", 60), (0, "tuck", 120), (0, "straight", 160)]
    for i, (dy, tent, ms) in enumerate(seq):
        if i == 2:
            conf.extend([[sx, sy - 2, vx, vy, col, 3] for vx, vy, col in CONFETTI])
        intro.append((happy.but(dy=dy, tent=tent, arm_f=("up_l", "flag_r"), parts=flag(BY + dy, 0) + tick()), ms))
    for i in range(8):
        intro.append((happy.but(curvy=True, tp=wave(i // 2), arm_f=("up_l", "flag_r"),
                                parts=flag(BY, i % 2) + tick()), 170))
    for i in range(8):
        loop.append((happy.but(curvy=True, tp=wave(i // 2), arm_f=("up_l", "flag_r"), parts=flag(BY, i % 2)), 170))
    loop.append((happy.but(curvy=True, tp=wave(0), arm_f=("up_l", "flag_r"), parts=flag(BY, 0)), 500))
    outro = [(happy.but(curvy=True, tp=wave(0)), 250), (Pose(), 200)]
    return {"intro": intro, "loop": loop, "outro": outro}


# ---------------------------------------------------------------- sleeping
def sleeping():
    intro = [(Pose(eyes="blink"), 260), (Pose(), 300), (Pose(eyes="blink"), 400), (Pose(eyes="sleep"), 300),
             (Pose(eyes="sleep", cap=True, dy=-1), 90), (Pose(eyes="sleep", cap=True), 400)]
    loop = []
    zs = []
    for t in range(12):
        if t % 4 == 0:
            zs.append([BX + 14, BY - 3, 0])
        parts = []
        for z in zs:
            x, y, age = z
            parts.append((ZZZ if age < 3 else ZZZ_DIM, x + age // 2, y - age))
            z[2] += 1
        zs[:] = [z for z in zs if z[1] - z[2] >= 0 and z[2] < 6]
        dy = -1 if t % 4 in (1, 2) else 0
        loop.append((Pose(eyes="sleep", cap=True, dy=dy, curvy=True, tp=wave(t // 4), parts=parts), 450))
    outro = [(Pose(eyes="blink", cap=True), 200), (Pose(eyes="blink"), 120), (Pose(), 160),
             (Pose(tent="long", dy=-1, arm_f=("up_l", "up_r")), 220), (Pose(eyes="blink"), 90), (Pose(), 160)]
    return {"intro": intro, "loop": loop, "outro": outro}


# ---------------------------------------------------------------- error
def error():
    def bang(dy):
        return [(BANG, BX + 17, BY - 2 + dy)]

    up = ("up_l", "up_r")
    sweat = lambda t: [(["S", "S"], BX - 1, BY + 2 + t % 4), (["S", "S"], BX + 16, BY + 3 + (t + 2) % 4)]
    intro = [(Pose(eyes="wide", tent="tuck"), 90),
             (Pose(eyes="wide", dy=-2, tent="long", arm_f=up, parts=bang(-2)), 80),
             (Pose(eyes="wide", dy=-3, tent="long", arm_f=up, parts=bang(-3)), 140),
             (Pose(eyes="wide", dy=-1, arm_f=up, parts=bang(-1)), 80),
             (Pose(eyes="wide", squash=True, tent="spread", parts=bang(0)), 110),
             (Pose(eyes="wide", parts=bang(0)), 160)]
    loop = []
    for t in range(8):
        loop.append((Pose(eyes="wide" if t < 2 else "open", ey=1 if t >= 2 else 0, tent="tuck",
                          dx=(0, 1, 0, -1)[t % 4] if t < 4 else 0, parts=bang(0) + sweat(t)), 200))
    outro = [(Pose(eyes="blink"), 120), (Pose(), 160)]
    return {"intro": intro, "loop": loop, "outro": outro}


# ---------------------------------------------------------------- happy
def happy():
    hearts = []

    def tick():
        out = [(HEART, x, y - age) for x, y, age in hearts if y - age >= 0]
        for h in hearts:
            h[2] += 1
        return out

    up = ("up_l", "up_r")
    base = Pose(eyes="happy", blush=True)
    intro = [(base.but(tent="tuck"), 110), (base.but(dy=-2, tent="long", arm_f=up), 70)]
    hearts.append([BX + 17, BY - 2, 0])
    intro.append((base.but(dy=-4, tent="long", arm_f=up, parts=tick()), 140))
    intro.append((base.but(dy=-2, arm_f=up, parts=tick()), 70))
    intro.append((base.but(squash=True, tent="spread", parts=tick()), 100))
    hearts.append([BX - 3, BY, 0])
    intro.append((base.but(dy=-2, tent="long", parts=tick()), 90))
    intro.append((base.but(parts=tick()), 120))
    loop = []
    for t in range(6):
        arms = ("up_l", "rest_r") if t % 2 == 0 else ("rest_l", "up_r")
        loop.append((base.but(curvy=True, tp=wave(t), arm_f=arms, parts=tick()), 200))
    return {"intro": intro, "loop": loop, "outro": [(Pose(eyes="happy"), 200)]}


# ---------------------------------------------------------------- sad (little rain cloud)
def sad():
    low = Pose(ey=1, tent="limp")
    cloud = lambda t: [(CLOUD_SMALL, BX + 5, BY - 7)] + [(["S"], BX + 6 + (k * 2), BY - 4 + (t + k) % 3)
                                                        for k in range(3)]
    intro = [(Pose(ey=1), 300), (low.but(parts=[(CLOUD_SMALL, BX + 5, BY - 9)]), 300)]
    loop = []
    for t in range(10):
        tears = [(["S", "S"], BX + 3, BY + 6 + t % 5)] if t % 5 < 4 else []
        tears += [(["S", "S"], BX + 12, BY + 6 + (t + 2) % 5)] if (t + 2) % 5 < 4 else []
        loop.append((low.but(dy=-1 if t in (8, 9) else 0, eyes="blink" if t == 9 else "open",
                             parts=cloud(t) + tears), 260))
    return {"intro": intro, "loop": loop, "outro": [(Pose(eyes="blink"), 150), (Pose(), 200)]}


# ---------------------------------------------------------------- PC reactions
STEAM = [["w.", ".w", "w."], [".w", "w.", ".w"]]
BATTERY = ["wwwwwww.", "w.....ww", "w.....ww", "wwwwwww."]
BOLT = [".Y", "YY", "Y."]
WIFI = [".wwwwwww.", "w.......w", "..wwwww..", ".w.....w.", "...www...", "....w...."]
SLASH = ["RR.......", ".RR......", "..RR.....", "...RR....", "....RR...", ".....RR.."]
QMARK = ["WWW", "..W", ".WW", ".W.", "...", ".W."]
HI = ["W.W.WWW", "W.W..W.", "WWW..W.", "W.W..W.", "W.W.WWW"]
STAR = [".Y.", "YYY", ".Y."]


def battery(level, color):
    rows = [list(r) for r in BATTERY]
    for i in range(level):
        for r in (1, 2):
            rows[r][1 + i] = color
    return ["".join(r) for r in rows]


def hot():
    loop = []
    fans = [["..PP", ".PPP", "PPPP", "q..."], ["PPPP", ".PPP", "..PP", "q..."]]
    for t in range(8):
        steam = [(STEAM[(t + k) % 2], BX + 5 + 4 * k, BY - 3 - (t % 3)) for k in range(2)]
        drops = [(["S", "S"], BX - 1, BY + 2 + t % 4)]
        loop.append((Pose(eyes="sleep", blush=True, dy=-(t % 2), arm_f=("rest_l", "up_r"),
                          parts=steam + drops + [(fans[t % 2], BX + 16, BY + 1)]), 150))
    return {"intro": [(Pose(eyes="wide"), 200)], "loop": loop, "outro": [(Pose(), 150)]}


def battery_low():
    loop = []
    for t in range(8):
        bar = "R" if t % 2 == 0 else "."
        loop.append((Pose(ey=1, tent="limp", eyes="blink" if t == 5 else "open",
                          parts=[(battery(1, bar), BX + 17, BY + 1)]), 350))
    return {"intro": [(Pose(ey=1), 200)], "loop": loop, "outro": [(Pose(), 150)]}


def charging():
    intro = []
    for lvl in range(1, 6):
        intro.append((Pose(eyes="happy", parts=[(battery(lvl, "c"), BX + 17, BY + 1), (BOLT, BX + 19, BY - 3)]), 180))
    intro.append((Pose(eyes="happy", tent="tuck", parts=[(battery(5, "c"), BX + 17, BY + 1)]), 100))
    intro.append((Pose(eyes="happy", dy=-2, tent="long", arm_f=("up_l", "up_r")), 120))
    intro.append((Pose(eyes="happy"), 200))
    return {"intro": intro, "loop": []}


PLUG = ["...hh", "qqHHH", "...hh"]
BOLT_L = ["..Y", ".Y.", "YY.", ".YY", ".Y."]
SKULL = [
    "...WWWWWWWWWW...",
    "..WWWWWWWWWWWW..",
    ".WWWWWWWWWWWWWW.",
    ".WWnnnWWWWnnnWW.",
    ".WWnnnWWWWnnnWW.",
    ".WWWWWWnnWWWWWW.",
    "..WWWWWWWWWWWW..",
    "...WnWnWnWnWnW..",
    "................",
    "...W..W..W..W...",
    "...W..W..W..W...",
    "...W..W..W..W...",
]


def zap():
    intro = []
    for i in range(4):
        intro.append((Pose(eyes="wide", ey=-1, tent="tuck" if i > 1 else "straight",
                           parts=[(PLUG, BX + 24 - i * 2, BY + 4)]), 150))
    for t in range(10):
        bones = t % 2 == 0
        jitter = (-1, 1)[t % 2]
        sparks = [(BOLT_L, BX - 3, BY - 2 + t % 3), (BOLT, BX + 17, BY - 3 - t % 2), (BOLT_L, BX + 5 + t % 3, BY - 5)]
        parts = [(PLUG, BX + 17, BY + 4)] + sparks
        if bones:
            parts = [(SKULL, BX, BY)] + parts
        intro.append((Pose(eyes="x", dx=jitter, arm_f=("up_l", "up_r"), tent="spread", tint="xray" if bones else None,
                           parts=parts), 70))
    smoke = [(STEAM[0], BX + 4, BY - 4), (STEAM[1], BX + 9, BY - 5)]
    intro.append((Pose(eyes="x", tent="limp", tint="red", parts=smoke), 220))
    intro.append((Pose(eyes="blink", tent="limp", parts=smoke), 220))
    for lvl in range(1, 6):
        intro.append((Pose(eyes="happy", ey=1, parts=[(battery(lvl, "c"), BX + 17, BY + 1)]), 150))
    intro.append((Pose(eyes="happy", dy=-2, tent="long", arm_f=("up_l", "up_r")), 120))
    intro.append((Pose(eyes="happy"), 200))
    return {"intro": intro, "loop": []}


def offline():
    loop = []
    for t in range(8):
        parts = [(WIFI, BX + 4, BY - 8), (SLASH, BX + 4, BY - 8)]
        if t in (3, 4, 5):
            parts.append((QMARK, BX + 17, BY - 2))
        loop.append((Pose(ey=-1, ex=-1 if t < 4 else 1, curvy=True, tp=wave(t // 2), parts=parts), 320))
    return {"intro": [(Pose(ey=-1), 200)], "loop": loop, "outro": [(Pose(), 150)]}


def hello():
    up = ("rest_l", "up_r")
    intro = [(Pose(tent="tuck"), 100), (Pose(dy=-2, tent="long", eyes="happy", arm_f=up), 90),
             (Pose(dy=-2, eyes="happy", arm_f=up, parts=[(HI, BX + 18, BY - 6)]), 120),
             (Pose(eyes="happy", arm_f=up, parts=[(HI, BX + 18, BY - 6)]), 120)]
    for t in range(6):
        intro.append((Pose(eyes="happy", arm_f=("rest_l", ("wave_r", "up_r")[t % 2]),
                           parts=[(HI, BX + 18, BY - 6)]), 160))
    intro.append((Pose(eyes="happy"), 250))
    return {"intro": intro, "loop": []}


def yawn():
    up = ("up_l", "up_r")
    intro = [(Pose(eyes="blink"), 200), (Pose(eyes="sleep", dy=-1, tent="long", arm_f=up, mouth="small"), 260),
             (Pose(eyes="sleep", dy=-2, tent="long", arm_f=up, mouth="big"), 800),
             (Pose(eyes="sleep", dy=-1, tent="long", arm_f=up, mouth="small",
                   parts=[(["S"], BX + 3, BY + 5)]), 260),
             (Pose(eyes="blink", parts=[(["S"], BX + 3, BY + 7)]), 250), (Pose(), 300)]
    return {"intro": intro, "loop": []}


def dizzy():
    ring = [(0, 0), (4, -1), (8, 0), (4, 1)]
    intro = []
    for t in range(14):
        stars = [(STAR, BX + 3 + ring[(t + k * 2) % 4][0], BY - 4 + ring[(t + k * 2) % 4][1]) for k in range(2)]
        intro.append((Pose(eyes="x", dx=(0, 1, 0, -1)[t % 4] if t < 10 else 0, tent=("left", "straight", "right",
                                                                                      "straight")[t % 4],
                           parts=stars), 140))
    intro.append((Pose(eyes="blink"), 120))
    intro.append((Pose(), 200))
    return {"intro": intro, "loop": []}


def shy():
    intro = [(Pose(eyes="happy", blush=True), 200)]
    for t in range(6):
        intro.append((Pose(eyes="happy", blush=True, dx=(0, -1)[t % 2] if t < 4 else 0, curvy=True, tp=wave(t),
                           parts=[(HEART, BX + 17, BY - 2 - t // 2)] if t >= 2 else []), 180))
    intro.append((Pose(blush=True), 250))
    return {"intro": intro, "loop": []}


# ---------------------------------------------------------------- headset / music
HEADSET = [
    "...hhhhhhhhhh...",
    "..h..........h..",
    ".h............h.",
    ".h............h.",
    "HH............HH",
    "Hh............hH",
    "Hh............hH",
    "HH............HH",
    ".h..............",
    "..hhhR..........",
]
HEADPHONES = HEADSET[:8]
SIDE_HEADPHONES = [
    "...hhhhhhh....",
    "..h...........",
    "..h...........",
    "..h...........",
    ".HHH..........",
    ".HhH..........",
    ".HhH..........",
    ".HHH..........",
]
SIDE_HEADSET = SIDE_HEADPHONES + [".h............", "..hhhhR......."]
MIC_MUTED = [
    "..WWW.R",
    "..WWWR.",
    "W.WWR.W",
    "W.WRW.W",
    ".WR..W.",
    "..RWW..",
    ".R.W...",
    "R.WWW..",
]
DEAF = [
    "..WWW.R",
    ".W...R.",
    "W....RW",
    "W...R.W",
    "WW.R.WW",
    "WWR..WW",
    ".R.....",
]
WAVES = [["S.", ".S", "S."], ["..S.", "S..S", "..S."]]
NOTE = ["..YY", "..Y.", "..Y.", "YYY.", "YY.."]
NOTE2 = ["..PP", "..P.", "..P.", "PPP.", "PP.."]


def call(variant="talk"):
    loop = []
    for t in range(8):
        parts = []
        eyes, ey = "open", 0
        if variant == "talk" and t % 4 in (1, 2):
            parts.append((WAVES[t % 2], BX - 3, BY + 7))
        if variant == "muted":
            parts.append((MIC_MUTED, BX + 18, BY - 3))
            ey = 1
        if variant == "deaf":
            parts.append((DEAF, BX + 18, BY - 3))
            eyes = "sleep"
        if t == 5 and variant != "deaf":
            eyes = "blink"
        loop.append((Pose(headset="mic", eyes=eyes, ey=ey, curvy=True, tp=wave(t // 2), dy=-(t % 4 == 2),
                          parts=parts), 260))
    return {"intro": [(Pose(headset="mic", dy=-1), 140), (Pose(headset="mic"), 120)], "loop": loop,
            "outro": [(Pose(), 150)]}


def music():
    loop = []
    for t in range(8):
        notes = [(NOTE if (t // 2) % 2 == 0 else NOTE2, BX + 17 + t % 2, BY - 3 - t % 3)]
        arms = ("rest_l", "up_r") if 3 <= t < 7 else ("up_l", "rest_r")
        loop.append((Pose(eyes="happy", dy=-(t % 2), tent=("left", "straight", "right", "straight")[t // 2],
                          arm_f=arms, parts=notes), 220))
    ready = Pose(eyes="happy", arm_f=("up_l", "rest_r"))
    return {"intro": [(Pose(), 200), (ready, 120)], "loop": loop, "outro": [(ready, 100), (Pose(), 150)]}


# ---------------------------------------------------------------- idle fidgets
BUBBLE_S = [".S.", "S.S", ".S."]
BUBBLE_L = [".SS.", "S..S", "S..S", ".SS."]
BOOK = [
    ".WWWWbWWWW.",
    "WwwwWbWwwwW",
    "WWWWWbWWWWW",
    "WwwwWbWwwwW",
    "WWWWWbWWWWW",
    "bbbbbbbbbbb",
]
BOOK_FLIP = [
    "......WW...",
    ".WWWWbWWW..",
    "WwwwWbWwwW.",
    "WWWWWbWWWWW",
    "WwwwWbWwwwW",
    "bbbbbbbbbbb",
]
SPARKLE = ["W.W", ".W.", "W.W"]


def look_around():
    intro = [(Pose(ex=-1), 450), (Pose(ex=-1, ey=-1), 300), (Pose(), 200), (Pose(ex=1), 450),
             (Pose(ex=1, ey=1), 300), (Pose(eyes="blink"), 90), (Pose(), 200)]
    return {"intro": intro, "loop": []}


def bubbles():
    intro = [(Pose(eyes="happy", blush=True), 250)]
    bs = []
    for t in range(12):
        if t % 3 == 0:
            bs.append([BX + 15, BY + 2, 0, t % 2])
        parts = [(BUBBLE_L if big else BUBBLE_S, x + age // 3, y - age) for x, y, age, big in bs if y - age >= 0]
        for b in bs:
            b[2] += 1
        intro.append((Pose(eyes="happy", blush=t % 3 == 0, curvy=True, tp=wave(t // 2), parts=parts), 170))
    intro.append((Pose(), 200))
    return {"intro": intro, "loop": []}


def read():
    hold = ("rest_l", "up_r")
    bx, by = BX + 14, BY + 3
    intro = [(Pose(ex=1, ey=1, arm_f=hold, parts=[(BOOK, bx, by + 1)]), 250)]
    for t in range(10):
        book = BOOK_FLIP if t in (4, 8) else BOOK
        intro.append((Pose(ex=1, ey=1, arm_f=hold, eyes="blink" if t == 6 else "open",
                           dy=-1 if t in (4, 8) else 0, parts=[(book, bx, by)]), 340))
    intro.append((Pose(ex=1, arm_f=hold, parts=[(BOOK, bx, by + 1)]), 200))
    intro.append((Pose(), 200))
    return {"intro": intro, "loop": []}


def sneeze():
    up = ("up_l", "up_r")
    intro = [(Pose(eyes="sleep", ey=-1), 260), (Pose(eyes="sleep", ey=-1, dy=-1, tent="long", arm_f=up), 220),
             (Pose(eyes="sleep", dy=-2, tent="long", arm_f=up), 300),
             (Pose(eyes="sleep", squash=True, tent="spread", parts=[(SPARKLE, BX + 17, BY + 3),
                                                                     (SPARKLE, BX - 3, BY + 2)]), 140),
             (Pose(eyes="x", parts=[(SPARKLE, BX + 19, BY + 1), (SPARKLE, BX - 3, BY)]), 220),
             (Pose(eyes="blink"), 120), (Pose(), 250)]
    return {"intro": intro, "loop": []}


def bye():
    intro = [(Pose(eyes="happy", arm_f=("rest_l", "up_r")), 160)]
    for t in range(6):
        intro.append((Pose(eyes="happy", arm_f=("rest_l", ("wave_r", "up_r")[t % 2])), 150))
    intro += [(Pose(eyes="blink"), 300), (Pose(eyes="sleep"), 300)]
    return {"intro": intro, "loop": []}


# ---------------------------------------------------------------- watering the plant (plant sits to the right)
CAN = [
    "..vvv....",
    ".v...v..c",
    ".v...v.c.",
    "vvvvvvc..",
    "vcccccv..",
    "vcccccv..",
    ".vvvvv...",
]
CAN_TILT = [
    ".vvv.....",
    "v...v....",
    "v...vvv..",
    "vvvvvcvv.",
    ".vccccc.c",
    "..vcccc..",
    "...vv....",
]


def water():
    side = Pose(side=True)
    cx, cy = BX + 14, BY + 3
    intro = [(Pose(ex=1), 200), (side, 200), (side.but(parts=[(CAN, cx, cy + 1)]), 220),
             (side.but(parts=[(CAN, cx, cy)]), 200)]
    for t in range(7):
        drops = [(["S"], cx + 8 + (k % 2), cy + 6 + ((t + k * 2) % 5)) for k in range(3)]
        intro.append((side.but(eyes="happy", parts=[(CAN_TILT, cx, cy)] + drops), 150))
    intro += [(side.but(eyes="happy", parts=[(CAN, cx, cy)]), 220), (side.but(eyes="happy"), 160),
              (Pose(eyes="happy"), 300)]
    return {"intro": intro, "loop": []}


VEIN = [".R.R.", "RR.RR", ".....", "RR.RR", ".R.R."]
ENVELOPE = ["UUUUUUU", "UWUUUWU", "UUWUWUU", "UUUWUUU", "UUUUUUU"]


def angry():
    vein = lambda dy=0: [(VEIN, BX + 16, BY - 3 + dy)]
    steam = lambda t: [(STEAM[(t + k) % 2], BX + 4 + 6 * k, BY - 3 - (t % 2)) for k in range(2)]
    intro = [(Pose(eyes="angry", blush=True), 200), (Pose(eyes="angry", tint="red"), 160),
             (Pose(eyes="angry", tint="red", dy=-2, tent="long", arm_f=("up_l", "up_r"), parts=vein(-2)), 110),
             (Pose(eyes="angry", tint="red", squash=True, tent="spread", parts=vein()), 120)]
    loop = []
    for t in range(8):
        arms = ("up_l", "rest_r") if t % 2 == 0 else ("rest_l", "up_r")
        loop.append((Pose(eyes="angry", tint="red", arm_f=arms, squash=t % 4 == 3,
                          tent="spread" if t % 4 == 3 else "straight", parts=vein(-(t % 2)) + steam(t)), 160))
    outro = [(Pose(eyes="blink", blush=True), 300), (Pose(blush=True, ey=1), 400), (Pose(), 200)]
    return {"intro": intro, "loop": loop, "outro": outro}


def swim():
    loop = [(Pose(tent="tuck", eyes="happy"), 140), (Pose(tent="long", eyes="happy"), 160),
            (Pose(tent="long"), 160), (Pose(), 160)]
    return {"loop": loop}


def mail():
    intro = [(Pose(eyes="wide", parts=[(ENVELOPE, BX + 16, BY - 2)]), 200),
             (Pose(dy=-2, tent="long", eyes="wide", parts=[(ENVELOPE, BX + 16, BY - 4)]), 120),
             (Pose(eyes="happy", parts=[(ENVELOPE, BX + 16, BY - 5)]), 300)]
    for t in range(4):
        intro.append((Pose(eyes="happy", ex=1, arm_f=("rest_l", ("up_r", "wave_r")[t % 2]),
                           parts=[(ENVELOPE, BX + 16, BY - 5 - t % 2)]), 220))
    intro.append((Pose(), 200))
    return {"intro": intro, "loop": []}


# ---------------------------------------------------------------- outfits (drawn on top of front poses)
OUTFITS = {
    "santa": [
        "......xxXXXX....",
        "....xXXXXXXXXX..",
        "...xXXXXXXXXXXZW",
        "..xXXXXXXXXXXXZW",
        "..WWWWWWWWWWWWW.",
    ],
    "witch": [
        ".......ee.......",
        "......eeee......",
        ".....eeaaee.....",
        "....eeeeeeee....",
        "...eeeeeeeeee...",
        ".eeeeeeeeeeeeee.",
    ],
    "party": [
        ".......W........",
        "......YYY.......",
        ".....YPYPY......",
        "....PYPYPYP.....",
        "...YPYPYPYPY....",
    ],
    "valentine": [
        "..P.P......P.P..",
        ".PPPPP....PPPPP.",
        ".PWPPP....PWPPP.",
        "..PPP......PPP..",
        "...P........P...",
    ],
    "bunny": [
        "...WW......WW...",
        "..WpW......WpW..",
        "..WpW......WpW..",
        "..WpW......WpW..",
        "..WWW......WWW..",
    ],
    "straw": [
        ".....yyyyyy.....",
        "....yyyyyyyy....",
        "....RRRRRRRR....",
        ".oyyyyyyyyyyyyo.",
    ],
    "pumpkin": [
        ".......vv.......",
        ".....aaaaaa.....",
        "...aaeaaaaeaa...",
        "..aaaaaaaaaaaa..",
        "..aaaeaeeaeaaa..",
    ],
}


def easter(year):
    """Easter Sunday (Gregorian calendar) as (month, day)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    j, k = c // 4, c % 4
    m = (a + 11 * h) // 319
    r = (2 * e + 2 * j - k - h + m + 32) % 7
    month = (h - m + r + 90) // 25
    return month, (h - m + r + month + 19) % 32


def outfit_for(month, day, year=None):
    if month == 12 and 1 <= day <= 26:
        return "santa"
    if year:
        import datetime
        sunday = datetime.date(year, *easter(year))
        if -2 <= (datetime.date(year, month, day) - sunday).days <= 1:
            return "bunny"
    if month == 10 and day == 31:
        return "pumpkin"
    if month == 6 and 21 <= day <= 30:
        return "straw"
    if (month == 12 and day == 31) or (month == 1 and day == 1):
        return "party"
    if month == 10 and day >= 24:
        return "witch"
    if month == 2 and day in (13, 14):
        return "valentine"
    return None


def with_outfit(p, outfit):
    """Add a seasonal hat to front poses (not while wearing a cap or headset)."""
    if not outfit or p.side or p.cap or p.headset or p.band:
        return p
    rows = OUTFITS[outfit]
    oy = BY + p.dy + (1 if p.squash else 0) - len(rows) + 1
    return p.but(wear=p.wear + [(rows, BX + p.dx, oy)])


# ---------------------------------------------------------------- focus timer, limits
BELL = [["...a...", "..YYY..", ".YYYYY.", ".YYYYY.", "YYYYYYY", "...q..."],
        ["....a..", "...YYY.", "..YYYYY", ".YYYYY.", "YYYYYY.", "..q...."],
        ["..a....", ".YYY...", "YYYYY..", ".YYYYY.", ".YYYYYY", "....q.."]]


def focus():
    loop = []
    for t in range(8):
        loop.append((Pose(band=True, ey=1 if t % 4 < 2 else 0, eyes="blink" if t == 6 else "open",
                          curvy=True, tp=wave(t // 2)), 420))
    return {"intro": [(Pose(band=True, dy=-1, tent="long"), 160), (Pose(band=True), 200)], "loop": loop,
            "outro": [(Pose(), 150)]}


CLOCK = [
    ".aa...aa.",
    "aaa.q.aaa",
    "..XXXXX..",
    ".XWWeWWX.",
    ".XWWeWWX.",
    ".XWWeeWX.",
    ".XWWWWWX.",
    "..XXXXX..",
    ".X.....X.",
]
RING = [["W.", ".W", "W."], [".W", "W.", ".W"]]


def alarm():
    intro = []
    for t in range(12):
        dx = (0, -1, 0, 1)[t % 4]
        x, y = BX + 17 + dx, BY - 7
        rings = [(RING[t % 2], x - 3, y + 3), (RING[(t + 1) % 2], x + 10, y + 3)] if t % 4 in (1, 3) else []
        intro.append((Pose(eyes="wide", dy=-(t % 2), arm_f=("rest_l", "up_r"),
                           parts=[(CLOCK, x, y)] + rings), 110))
    intro += [(Pose(eyes="happy", parts=[(CLOCK, BX + 17, BY - 7)]), 300), (Pose(eyes="happy"), 200)]
    return {"intro": intro, "loop": []}


def stretch():
    up = ("up_l", "up_r")
    intro = [(Pose(eyes="happy", dy=-1, tent="long", arm_f=up), 400), (Pose(eyes="happy", dy=-2, tent="long",
                                                                            arm_f=up), 500),
             (Pose(eyes="happy", dx=-1, arm_f=("up_l", "rest_r")), 400), (Pose(eyes="happy", dx=1,
                                                                               arm_f=("rest_l", "up_r")), 400),
             (Pose(eyes="happy"), 300)]
    return {"intro": intro, "loop": []}


def exhausted():
    loop = []
    for t in range(8):
        sweat = [(["S", "S"], BX + 16, BY + 3 + t % 3)] if t < 6 else []
        loop.append((Pose(squash=True, tent="spread", eyes="sleep" if t % 4 else "x", ey=1,
                          parts=sweat + ([(ZZZ_DIM, BX + 17, BY - 4)] if t >= 4 else [])), 380))
    return {"intro": [(Pose(eyes="x"), 200), (Pose(squash=True, tent="spread", eyes="x"), 300)], "loop": loop,
            "outro": [(Pose(eyes="blink"), 200), (Pose(), 150)]}


# ---------------------------------------------------------------- climbing, eating, photos, trophies
def climb():
    p = Pose(side=True, typing=True, ex=1, ey=-1)
    loop = [(p.but(tp=("hook", "s1", "hook", "s1")), 130), (p.but(tp=("s1", "hook", "s1", "hook"), dy=-1), 130)]
    return {"loop": loop}


FISH = [".aaa.a", "aeaaaa", ".aaa.a"]
NOTE_PAPER = ["WWWW", "WwwW", "WWWW", "WwwW"]


def eat(food):
    intro = []
    for i, y in enumerate((BY - 8, BY - 5, BY - 2)):
        intro.append((Pose(eyes="wide" if i < 2 else "happy", ey=-1, arm_f=("up_l", "up_r"),
                           parts=[(food, BX + 5, y)]), 150))
    crumbs = lambda t: [(["a" if food is FISH else "W"], BX + 3 + (t * 5) % 10, BY + 8 + t % 3)]
    for t in range(6):
        intro.append((Pose(eyes="happy", blush=True, mouth="big" if t % 2 == 0 else "small", dy=-(t % 2),
                           parts=crumbs(t)), 160))
    intro += [(Pose(eyes="happy", blush=True), 300), (Pose(eyes="happy"), 200)]
    return {"intro": intro, "loop": []}


CAMERA = [".HH...", "HHHHHH", "HHSSHH", "HHSSHH", "HHHHHH"]
FLASH = ["W..W..W", ".W.W.W.", "..WWW..", "WWWyWWW", "..WWW..", ".W.W.W.", "W..W..W"]


def camera():
    cam = lambda: [(CAMERA, BX + 15, BY + 2)]
    intro = [(Pose(ex=1, arm_f=("rest_l", "up_r"), parts=cam()), 250),
             (Pose(eyes="sleep", arm_f=("rest_l", "up_r"), parts=cam() + [(FLASH, BX + 16, BY - 5)]), 110),
             (Pose(eyes="blink", arm_f=("rest_l", "up_r"), parts=cam()), 150),
             (Pose(eyes="happy", blush=True, arm_f=("up_l", "up_r")), 400), (Pose(eyes="happy"), 200)]
    return {"intro": intro, "loop": []}


TROPHY = ["YYYYYYY", "Y.YYY.Y", ".YYYYY.", "..YYY..", "...Y...", "..qqq.."]


def trophy():
    up = ("up_l", "up_r")
    t_at = lambda dy: [(TROPHY, BX + 4, BY - 7 + dy)]
    intro = [(Pose(eyes="happy", arm_f=up, parts=t_at(0)), 200),
             (Pose(eyes="happy", tent="tuck", arm_f=up, parts=t_at(0)), 100),
             (Pose(eyes="happy", dy=-2, tent="long", arm_f=up, parts=t_at(-2) + [(SPARKLE, BX - 2, BY - 6)]), 160),
             (Pose(eyes="happy", arm_f=up, parts=t_at(0) + [(SPARKLE, BX + 14, BY - 6)]), 200)]
    for t in range(4):
        intro.append((Pose(eyes="happy", blush=True, arm_f=up, dy=-(t % 2), parts=t_at(-(t % 2))), 180))
    intro.append((Pose(eyes="happy"), 250))
    return {"intro": intro, "loop": []}


def tug():
    """Mini mode, being pulled out of the screen edge: it holds on and strains against it."""
    p = Pose(side=True, flip=True, eyes="angry", tent="spread")
    return {"loop": [(p, 140), (p.but(dx=-1, eyes="wide"), 120), (p.but(eyes="angry", dy=-1), 140),
                     (p.but(dx=-1, eyes="wide"), 120)]}


def peek():
    p = Pose(side=True, flip=True, ex=1)
    loop = [(p, 1800), (p.but(eyes="blink"), 120), (p, 1400), (p.but(ey=-1), 700), (p.but(dx=-1), 900), (p, 600)]
    return {"loop": loop}


BALL = [".XXXX.", "XWXXXX", "XXXXXX", "XXXXXZ", "XXXXZZ", ".XZZZ."]


def carry():
    p = Pose(eyes="happy", arm_f=("rest_l", "up_r"), parts=[(BALL, BX + 14, BY + 1)])
    return {"loop": [(p, 300), (p.but(dy=-1), 300)]}


# ---------------------------------------------------------------- weather accessories (front poses only)
SCARF = [
    ".xxxxxxxxxxxxxx.",
    ".XXWXXXWXXXWXXX.",
    ".ZZZZZZZZZZZZZZ.",
    "............XWZ.",
    "............XXZ.",
    "............Z.Z.",
]
SCARF_SIDE = [
    ".xxxxxxxxxxxx.",
    ".XXWXXXWXXXXX.",
    ".ZZZZZZZZZZZZ.",
    "XWZ...........",
    "XXZ...........",
    "Z.Z...........",
]
SHADES = [
    "..HHHHH..HHHHH..",
    "..HhnnHHHHhnnH..",
    "..HnnnH..HnnnH..",
    "..HHHHH..HHHHH..",
]
SHADES_SIDE = [
    "....HHHHHHHHH.",
    "....HhnnHhnnH.",
    "....HnnnHnnnH.",
    "....HHHHHHHHH.",
]
RAIN = [(([".....BBBBBB.....", "...BBBBBBBBBB...", ".BBBBBBBBBBBBBB.", "BWBWBWBWBWBWBWBW",
           ".......q........", ".......q........"]), 0, -6)]
WEATHER = {
    "sun": [(SHADES, 0, 3)],
    "rain": RAIN,
    "cold": [(SCARF, 0, 6)],
    "snow": [(SCARF, 0, 6), (["W.....W....W", "...W.....W..", ".W.....W...."], 2, -7)],
    "storm": RAIN,
}


def with_gear(p, headset=None, band=False, sweat=False):
    """Things the pet keeps wearing whatever it does: call headset, music headphones, focus band, sweat."""
    if p.cap:
        return p
    kw = {}
    if headset and not p.headset:
        kw["headset"] = headset
    if band and not p.band:
        kw["band"] = True
    if sweat:
        x = BX + p.dx + (0 if p.side else -1)
        kw["wear"] = p.wear + [(["S", "S"], x, BY + p.dy + 2)]
    return p.but(**kw) if kw else p


SCARF_INV = [
    "............Z.Z.",
    "............XWZ.",
    "............XXZ.",
    "............XWZ.",
    ".ZZZZZZZZZZZZZZ.",
    ".XXWXXXWXXXWXXX.",
    ".xxxxxxxxxxxxxx.",
]
WEATHER_INV = dict(WEATHER, cold=[(SCARF_INV, 0, 2)], snow=[(SCARF_INV, 0, 2), WEATHER["snow"][1]])

WEATHER_SIDE = {
    "sun": [(SHADES_SIDE, 0, 3)],
    "rain": WEATHER["rain"],
    "storm": WEATHER["rain"],
    "cold": [(SCARF_SIDE, 0, 6)],
    "snow": [(SCARF_SIDE, 0, 6), WEATHER["snow"][1]],
}


def with_weather(p, kind, inv=False):
    """Weather clothes (umbrella, sunglasses, scarf). They go with headphones and the focus band too;
    only the sleeping cap replaces them."""
    if not kind or p.cap:
        return p
    table = WEATHER_SIDE if p.side else WEATHER_INV if inv else WEATHER
    if kind not in table:
        return p
    if kind == "sun" and (p.eyes not in ("open", "blink") or p.headset == "mic"):
        return p
    oy = BY + p.dy + (1 if p.squash else 0)
    extra = [(rows, BX + p.dx + dx, oy + dy) for rows, dx, dy in table[kind]]
    return p.but(wear=p.wear + extra)


# ---------------------------------------------------------------- reminders and weather moods
STICKY = ["..R...", "YYYYYY", "YqqqqY", "YYYYYY", "YqqqYY", "YYYYYY"]
SUN = [["..Y..", "Y.Y.Y", ".YYY.", "YYYYY", ".YYY.", "Y.Y.Y", "..Y.."],
       ["Y...Y", ".YYY.", "YYYYY", "YYYYY", "YYYYY", ".YYY.", "Y...Y"]]
CLOUD_SMALL = [".www..", "wwwwww", ".wwww."]


def reminder():
    intro = []
    for t in range(10):
        up = t % 2
        intro.append((Pose(eyes="wide" if t < 3 else "happy", arm_f=("rest_l", "up_r"), dy=-up,
                           parts=[(STICKY, BX + 16, BY - 5 - up)]), 150))
    intro.append((Pose(eyes="happy"), 250))
    return {"intro": intro, "loop": []}


def rainy():
    intro = []
    for t in range(12):
        drops = [(["S"], BX + x, BY - 4 + (t * 2 + k * 3) % 12) for k, x in enumerate((-2, 17, -1, 18))]
        p = Pose(ey=-1, eyes="blink" if t == 7 else "open", curvy=True, tp=wave(t // 2), parts=drops)
        intro.append((with_weather(p, "rain"), 160))
    return {"intro": intro, "loop": []}


def sunny():
    intro = []
    for t in range(10):
        p = Pose(eyes="happy", blush=t % 4 < 2, dy=-(t % 2), curvy=True, tp=wave(t // 2),
                 parts=[(SUN[t % 2], BX + 17, BY - 7)])
        intro.append((with_weather(p.but(eyes="open"), "sun").but(eyes="open"), 200))
    return {"intro": intro, "loop": []}


def snowy():
    intro = []
    for t in range(12):
        flakes = [(["W"], BX + x, BY - 6 + (t + k * 4) % 10) for k, x in enumerate((1, 6, 11, 15))]
        p = Pose(ey=-1, mouth="small" if t % 4 in (1, 2) else None, eyes="happy" if t > 8 else "open",
                 parts=flakes)
        intro.append((with_weather(p, "cold"), 170))
    return {"intro": intro, "loop": []}


def shiver():
    intro = []
    for t in range(12):
        p = Pose(eyes="sleep", dx=(0, 1)[t % 2] if t < 9 else 0, tent="tuck" if t % 2 else "straight")
        intro.append((with_weather(p, "cold"), 110))
    return {"intro": intro, "loop": []}


def cloudy():
    intro = []
    for t in range(10):
        intro.append((Pose(ey=-1, ex=(-1, 0, 1)[min(2, t // 3)], parts=[(CLOUD_SMALL, BX - 2 + t * 2, BY - 6)]),
                      230))
    return {"intro": intro, "loop": []}


# ---------------------------------------------------------------- tool animations (Claude / Codex)
GLASS = [".www..", "wSSSw.", "wSWSw.", "wSSSw.", ".wwwq.", "....qq"]


def search():
    loop = []
    xs = [3, 6, 9, 12, 9, 6]
    for t in range(12):
        x = xs[t % len(xs)]
        loop.append((Pose(ex=(-1, 0, 0, 1, 0, 0)[t % 6], ey=1, arm_f=("rest_l", "up_r"),
                          eyes="blink" if t == 9 else "open", parts=[(GLASS, BX + x, BY + 5)]), 170))
    return {"intro": [(Pose(ey=1), 150)], "loop": loop, "outro": [(Pose(), 120)]}


def _term(n, cursor):
    rows = ["gggggggggg", "gnnnnnnnng", "gnnnnnnnng", "gnnnnnnnng", "gnnnnnnnng", "gnnnnnnnng", "gggggggggg"]
    rows = [list(r) for r in rows]
    rows[1][1] = "c"
    for i in range(min(n, 7)):
        rows[1][2 + i] = "w"
    for line in range(min(max(0, n - 7), 6) // 2):
        for i in range(2 + line * 2):
            if 1 + i < 9:
                rows[2 + line][1 + i] = "c"
    if cursor and n < 7:
        rows[1][2 + n] = "W"
    return ["".join(r) for r in rows]


def terminal():
    loop = []
    for t in range(14):
        arms = ("rest_l", ("up_r", "wave_r")[t % 2] if t < 7 else "up_r")
        loop.append((Pose(ex=1, arm_f=arms, parts=[(_term(t, t % 2 == 0), BX + 16, BY + 1)]), 150))
    return {"intro": [(Pose(ex=1, parts=[(_term(0, True), BX + 16, BY + 1)]), 200)], "loop": loop,
            "outro": [(Pose(), 120)]}


def _globe(phase):
    land = ["..c....c..", ".cc..c.cc.", "ccc.cc..cc", ".c..ccc.c.", "...c.c...."]
    mask = ["..BBB..", ".BBBBB.", "BBBBBBB", "BBBBBBB", "BBBBBBB", ".BBBBB.", "..BBB.."]
    out = []
    for y, row in enumerate(mask):
        line = ""
        for x, c in enumerate(row):
            if c == ".":
                line += "."
            else:
                src = land[(y + 1) % len(land)]
                line += "c" if src[(x + phase) % len(src)] == "c" else "B"
        out.append(line)
    return out


def browse():
    loop = []
    for t in range(10):
        loop.append((Pose(ex=1, ey=-1, arm_f=("rest_l", "up_r"), eyes="blink" if t == 7 else "open",
                          parts=[(_globe(t), BX + 16, BY - 3)]), 180))
    return {"intro": [(Pose(ex=1, ey=-1, parts=[(_globe(0), BX + 16, BY - 3)]), 150)], "loop": loop,
            "outro": [(Pose(), 120)]}


def _clipboard(done):
    rows = ["..qqq..", "bbbbbbb", "bWWWWWb", "bWWwwWb", "bWWWWWb", "bWWwwWb", "bWWWWWb", "bWWwwWb", "bbbbbbb"]
    rows = [list(r) for r in rows]
    for i in range(min(done, 3)):
        rows[3 + 2 * i][1] = "c"
        rows[3 + 2 * i][2] = "c"
    return ["".join(r) for r in rows]


def todo():
    loop = []
    for t in range(8):
        loop.append((Pose(ex=1, ey=1, arm_f=("rest_l", "up_r" if t % 2 else "wave_r"),
                          parts=[(_clipboard(t // 2), BX + 16, BY)]), 220))
    return {"intro": [(Pose(ex=1, parts=[(_clipboard(0), BX + 16, BY)]), 150)], "loop": loop,
            "outro": [(Pose(eyes="happy"), 200)]}


# ---------------------------------------------------------------- tickle, pet, recycle bin
GIGGLE = [".Y.", "YWY", ".Y."]


def tickled():
    intro = []
    up = ("up_l", "up_r")
    intro.append((Pose(eyes="happy", blush=True, arm_f=up), 90))
    for t in range(12):
        intro.append((Pose(eyes="happy", blush=True, dy=-(t % 2), tent=("left", "right")[t % 2], arm_f=up,
                           parts=[(GIGGLE, BX + (18 if t % 2 else -3), BY - 2 + t % 3)]), 90))
    intro.append((Pose(eyes="happy", blush=True, arm_f=up), 120))
    intro.append((Pose(eyes="happy", blush=True), 250))
    return {"intro": intro, "loop": []}


def petted():
    intro = [(Pose(eyes="happy", blush=True), 250)]
    for t in range(6):
        intro.append((Pose(eyes="sleep" if t % 2 else "happy", blush=True, squash=t % 2 == 1,
                           tent="spread" if t % 2 else "straight",
                           parts=[(HEART, BX + 17, BY - 3 - t // 2)] if t >= 2 else []), 260))
    intro.append((Pose(eyes="happy", blush=True), 300))
    return {"intro": intro, "loop": []}


TRASH = ["..W.W.", ".hhhhh", "hhhhhhh", ".whwhw.", ".whwhw.", ".whwhw.", "..www.."]
STINK = [["c.", ".c", "c."], [".c", "c.", ".c"]]


def trash_full():
    intro = []
    for t in range(10):
        stink = [(STINK[(t + k) % 2], BX + 19 + 2 * k, BY - 2 - (t + k) % 3) for k in range(2)]
        intro.append((Pose(ex=1, eyes="sleep" if t % 4 > 1 else "open", arm_f=("rest_l", "up_r"),
                           parts=[(TRASH, BX + 18, BY + 5)] + stink), 220))
    intro.append((Pose(ex=1, parts=[(TRASH, BX + 18, BY + 5)]), 300))
    return {"intro": intro, "loop": []}


BROOM = [["q....", ".q...", "..q..", "..aaa", ".aaaa", "aaaa."], ["....q", "...q.", "..q..", "aaa..", "aaaa.",
                                                                    ".aaaa"]]
DUST = [".ww.", "wwww", ".ww."]


def sweep():
    intro = []
    for t in range(10):
        dust = [(DUST, BX + 18 + (t % 3), BY + 9 - t % 2)] if t < 7 else []
        intro.append((Pose(eyes="happy" if t > 6 else "open", ex=1, arm_f=("rest_l", "up_r"),
                           parts=[(BROOM[t % 2], BX + 15, BY + 6)] + dust), 150))
    for t in range(4):
        intro.append((Pose(eyes="happy", blush=True, arm_f=("up_l", "up_r"),
                           parts=[(SPARKLE, BX + 17 + t % 2, BY - 3), (SPARKLE, BX - 3, BY - 1 + t % 2)]), 180))
    intro.append((Pose(eyes="happy"), 250))
    return {"intro": intro, "loop": []}


def warn():
    sign = ["...Y...", "..YRY..", "..YRY..", ".YYYYY.", ".YYRYY.", "YYYYYYY"]
    intro = []
    for t in range(8):
        intro.append((Pose(eyes="wide" if t < 2 else "open", ey=1 if t >= 2 else 0, arm_f=("rest_l", "up_r"),
                           dy=-(t % 2), parts=[(sign, BX + 16, BY - 4 - (t % 2))]), 200))
    intro.append((Pose(), 200))
    return {"intro": intro, "loop": []}


# ---------------------------------------------------------------- cooking (chef hat, flipping an egg)
CHEF_HAT = ["....wWW.WWw.....", "...WWWWWWWWWW...", "...WWWWWWWWWWw..", "....WWWWWWWWw...",
            "....wwwwwwww....", "....WWWWWWWW...."]
PAN = ["qqqhHHHHHh", "....hHHHh."]
EGG = {"up": ["WWWW", "WYYW", ".WW."], "edge": ["WWWW"], "down": [".WW.", "WWWW", "WWWW"]}


def _chef(p, pan_dy=0, egg=None, extra=()):
    oy = BY + p.dy + (1 if p.squash else 0) - len(CHEF_HAT) + 1
    px, py = BX + 15 + p.dx, BY + 6 + p.dy + pan_dy
    parts = [(PAN, px, py)]
    if egg:
        kind, h = egg
        parts.append((EGG[kind], px + 5, py - len(EGG[kind]) - h))
    return p.but(wear=p.wear + [(CHEF_HAT, BX + p.dx, oy)], parts=p.parts + parts + list(extra))


def cooking():
    hold = Pose(ex=1, arm_f=("rest_l", "up_r"))
    intro = [(_chef(Pose(ex=1), 0).but(parts=[]), 1), (_chef(hold.but(dy=-1), -1, ("up", 0)), 160),
             (_chef(hold, 0, ("up", 0)), 220)]
    intro[0] = (Pose(ex=1, eyes="blink"), 120)
    loop = []
    for t in range(2):
        steam = [(STEAM[(t + k) % 2], BX + 20 + 3 * k, BY - 1 - k) for k in range(2)]
        loop.append((_chef(hold.but(curvy=True, tp=wave(t)), 0, ("up", 0), steam), 260))
    flips = [(1, ("up", 0), 90, "open"), (-1, ("up", 3), 70, "open"), (-1, ("edge", 7), 80, "wide"),
             (0, ("down", 9), 120, "wide"), (0, ("edge", 6), 80, "open"), (0, ("up", 2), 70, "open"),
             (1, ("up", 0), 90, "open")]
    for pan_dy, egg, ms, eyes in flips:
        loop.append((_chef(hold.but(eyes=eyes, ey=-1 if egg[1] > 4 else 0, dy=-1 if pan_dy < 0 else 0),
                           pan_dy, egg), ms))
    loop.append((_chef(hold.but(eyes="happy", blush=True), 0, ("up", 0), [(SPARKLE, BX + 25, BY - 2)]), 320))
    for t in range(3):
        steam = [(STEAM[(t + k) % 2], BX + 20 + 3 * k, BY - 1 - k) for k in range(2)]
        loop.append((_chef(hold.but(curvy=True, tp=wave(t + 2), eyes="blink" if t == 2 else "open"), 0,
                           ("up", 0), steam), 240))
    return {"intro": intro, "loop": loop, "outro": [(Pose(eyes="happy"), 180), (Pose(), 120)]}


# ---------------------------------------------------------------- more idle fun
YOYO = [".R.", "RWR", ".R."]


def yoyo():
    hold = Pose(arm_f=("rest_l", "up_r"), ex=1)
    loop = []
    for t, length in enumerate((1, 3, 6, 9, 11, 9, 6, 3, 1, 1, 4, 8, 11, 8, 4, 1)):
        string = [(["q"] * length, BX + 17, BY + 1)] if length else []
        loop.append((hold.but(ey=1 if length > 6 else 0, eyes="happy" if t in (15,) else "open",
                              parts=string + [(YOYO, BX + 16, BY + 1 + length)]), 90))
    return {"intro": [(hold.but(parts=[(YOYO, BX + 16, BY + 2)]), 200)] + loop,
            "loop": [], "outro": [(Pose(eyes="happy"), 220)]}


def juggle():
    balls = [(["RR", "RR"]), (["YY", "YY"]), (["BB", "BB"])]
    arc = [(BX + 1, BY - 1), (BX + 3, BY - 5), (BX + 7, BY - 8), (BX + 11, BY - 5), (BX + 13, BY - 1),
           (BX + 9, BY - 3), (BX + 5, BY - 3)]
    intro = []
    for t in range(21):
        parts = [(balls[k], *arc[(t + k * 2) % len(arc)]) for k in range(3)]
        arms = ("up_l", "rest_r") if t % 2 == 0 else ("rest_l", "up_r")
        intro.append((Pose(arm_f=arms, ey=-1, dy=-(t % 4 == 1), parts=parts), 110))
    intro.append((Pose(eyes="happy", blush=True, arm_f=("up_l", "up_r")), 360))
    return {"intro": intro, "loop": []}


CUP = ["......", "WqqW..", "WWWWWW", "WhhW.W", "WWWWW.", ".WW..."]


def coffee():
    steam = lambda t, x, y: [(STEAM[t % 2], x + 1, y - 3)]
    held = Pose(arm_f=("rest_l", "up_r"))
    intro = [(held.but(parts=[(CUP, BX + 15, BY + 3)] + steam(0, BX + 15, BY + 3)), 400),
             (held.but(parts=[(CUP, BX + 15, BY + 3)] + steam(1, BX + 15, BY + 3)), 400),
             (held.but(ex=1, parts=[(CUP, BX + 13, BY + 3)]), 160),
             (held.but(eyes="sleep", blush=True, parts=[(CUP, BX + 11, BY + 3)]), 700),
             (held.but(eyes="sleep", blush=True, dy=-1, parts=[(CUP, BX + 11, BY + 2)]), 500),
             (held.but(eyes="happy", blush=True, parts=[(CUP, BX + 15, BY + 3)] + steam(0, BX + 15, BY + 3)), 600),
             (held.but(eyes="happy", blush=True, parts=[(CUP, BX + 15, BY + 3)] + steam(1, BX + 15, BY + 3)), 500)]
    return {"intro": intro, "loop": [], "outro": [(Pose(eyes="happy"), 200)]}


def _console(t, win=False):
    rows = ["HHHHHHHHHHH", "HnnnnnnnnnH", "HnnnnnnnnnH", "HnnnnnnnnnH", "HHHHHHHHHHH", "HRHHHHHHYHH"]
    rows = [list(r) for r in rows]
    if win:
        for x in range(3, 8):
            rows[2][x] = "Y"
    else:
        rows[3][1 + (t % 9)] = "c"
        rows[1 + (t // 3) % 3][9 - (t % 9)] = "X"
    return ["".join(r) for r in rows]


def gaming():
    play = Pose(arm_f=("up_l", "up_r"), ey=1, tent="tuck")
    intro = [(play.but(parts=[(_console(0), BX + 2, BY + 7)]), 250)]
    for t in range(18):
        intro.append((play.but(dy=-(t % 6 == 3), eyes="wide" if t in (8, 9) else "open",
                               parts=[(_console(t), BX + 2, BY + 7)]), 120))
    intro.append((play.but(eyes="happy", blush=True, parts=[(_console(0, True), BX + 2, BY + 7),
                                                             (STAR, BX + 17, BY - 2)]), 500))
    return {"intro": intro, "loop": [], "outro": [(Pose(eyes="happy"), 200)]}


PLANE = ["W....", "WWW..", "WWWWW", "..ww."]


def paper_plane():
    intro = [(Pose(arm_f=("rest_l", "up_r"), parts=[(PLANE, BX + 16, BY + 2)]), 300),
             (Pose(arm_f=("rest_l", "rest_r"), ex=1, parts=[(PLANE, BX + 17, BY + 4)]), 220),
             (Pose(arm_f=("rest_l", "up_r"), ex=1, ey=-1, dy=-1, parts=[(PLANE, BX + 18, BY + 1)]), 110)]
    for k, (x, y) in enumerate(((21, 0), (24, -2), (26, -4), (28, -5), (29, -7))):
        intro.append((Pose(ex=1, ey=-1, parts=[(PLANE, BX + x - 4, BY + y)]), 110))
    intro += [(Pose(ex=1, ey=-1), 400), (Pose(eyes="happy", blush=True, arm_f=("up_l", "up_r")), 450)]
    return {"intro": intro, "loop": []}


def _gum(r):
    size = 2 * r + 1
    out = []
    for y in range(size):
        row = ""
        for x in range(size):
            d = ((x - r) ** 2 + (y - r) ** 2) ** 0.5
            row += "P" if r - 0.6 <= d <= r + 0.4 else ("p" if d < r - 0.6 else ".")
        out.append(row)
    if r >= 2:
        out[1] = out[1][:1] + "W" + out[1][2:]
    return out


def bubblegum():
    intro = [(Pose(ey=1), 250)]
    for r in (1, 1, 2, 2, 3, 3, 4):
        intro.append((Pose(eyes="sleep" if r < 4 else "open", parts=[(_gum(r), BX + 8 - r, BY + 7 - r)]), 200))
    pop = [(["p.p.p"], BX + 6, BY + 5), (["p...p"], BX + 6, BY + 7), ([".p.p."], BX + 5, BY + 9)]
    intro += [(Pose(eyes="wide", dy=-1, parts=pop), 160), (Pose(eyes="x", blush=True, parts=pop[:2]), 260),
              (Pose(eyes="blink", blush=True), 200), (Pose(eyes="happy", blush=True), 400)]
    return {"intro": intro, "loop": []}


PAD = ["WWWWWWW", "WwwwwwW", "WWWWWWW", "WwwwwwW", "WWWWWWW", "WWWWWWW"]


def doodle():
    held = Pose(arm_f=("rest_l", "up_r"), ex=1, ey=1)
    heart = [".P.P.", "PPPPP", ".PPP.", "..P.."]
    intro = []
    for t in range(12):
        pad = [list(r) for r in PAD]
        for k in range(min(t, 6)):
            pad[1 + (k % 4)][1 + k % 5] = "R"
        intro.append((held.but(parts=[(["".join(r) for r in pad], BX + 15, BY + 4),
                                      (["Y", "Y", "q"], BX + 17 + (t % 3), BY + 1 + t % 2)]), 130))
    intro.append((Pose(eyes="happy", blush=True, arm_f=("rest_l", "up_r"),
                       parts=[(PAD, BX + 15, BY + 2), (heart, BX + 16, BY + 3)]), 700))
    return {"intro": intro, "loop": []}


# ---------------------------------------------------------------- hanging by a tentacle (drag)
GRAB_X, GRAB_LEN = 6, 7


def clothing_px(dressed):
    """Pixels a dressed front pose adds to the plain body, relative to the body origin."""
    plain = {(x, y): c for x, y, c in layers(Pose())}
    worn = {(x, y): c for x, y, c in layers(dressed)}
    return [(x - BX, y - BY, c) for (x, y), c in worn.items() if plain.get((x, y)) != c]


def hang_image(phase, pal=None, dressed=None):
    """Upside-down pet held by one tentacle, keeping its clothes. Returns (1x RGBA image, pivot (x, y))."""
    from PIL import Image
    clothes = clothing_px(dressed) if dressed is not None else []
    below = max([0] + [-y for _x, y, _c in clothes])
    w, h = 18, 9 + GRAB_LEN + below
    px = []
    px += sprite_px(FRONT, 1, 0)
    for k, x in enumerate(F_TENT):
        if x == GRAB_X:
            pts = [(x, 9 + r) for r in range(GRAB_LEN)]
        else:
            shape = F_TP[("s1", "s2", "hang")[(phase + k) % 3]]
            pts = [(x + a, 9 + b) for a, b in shape[:2 + (phase + k) % 2]]
        px += [(1 + a, b, "D" if i == len(pts) - 1 else "#") for i, (a, b) in enumerate(pts)]
    eyes = [(4, 4), (4, 5), (4, 6), (11, 4), (11, 5), (11, 6)] if phase % 6 else [(4, 5), (11, 5)]
    px += [(1 + x, y, "O") for x, y in eyes]
    arm_y = (3, 5)[phase % 2]
    px += [(0, arm_y, "L"), (16, 8 - arm_y, "#")]
    px += [(1 + x, y, c) for x, y, c in clothes if 0 <= 1 + x < w]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    colors = dict(PAL, **pal) if pal else PAL
    for x, y, c in px:
        if 0 <= h - 1 - below - y < h:
            img.putpixel((x, h - 1 - below - y), colors[c] + (255,))
    return img, (1 + GRAB_X, 0)


CAL_PAGE = ["RRRRRRR", "RWRRRWR", "WWWWWWW", "WOWOWOW", "WWWWWWW", "WOWOWWW", "WWWWWWW"]
CAL_TORN = ["WWWWWWW", "WOWOWOW", "WWWWWWW", "WOWOWWW", "WWWWWWW"]
LAP_BACK = ["GGGGGGGGGGGG", "GhhhhhhhhhhG", "GhhhhhWhhhhG", "GhhhhhhhhhhG", "GhhhhhhhhhhG", "kkkkkkkkkkkk"]


# ---------------------------------------------------------------- idle: floating / breathing
def float_idle():
    """Hovers on the spot: the bell pulses, the tentacles trail behind the slow up and down."""
    loop = []
    ys = [0, 0, -1, -1, -2, -2, -2, -1, -1, 0]
    for t, dy in enumerate(ys):
        squash = t == 0
        p = Pose(dy=dy, curvy=not squash, tp=wave(t // 2), tent="spread" if squash else "straight", squash=squash,
                 eyes="blink" if t == 6 else "open")
        loop.append((p, 140 if squash else 230))
    return {"loop": loop}


def breathe():
    """Calm breathing for long idle stretches: contract, hold, relax."""
    b = Pose()
    loop = [(b, 900), (b.but(squash=True, tent="spread"), 260), (b.but(dy=-1, tent="long"), 340),
            (b.but(dy=-1), 500), (b.but(eyes="blink", dy=-1), 110), (b.but(dy=-1), 300), (b, 700)]
    return {"loop": loop}


# ---------------------------------------------------------------- movement: a jellyfish hop
def hop_prep():
    """Contracts before pushing off."""
    f = Pose()
    return {"loop": [(f.but(squash=True, tent="spread", eyes="blink"), 110), (f.but(squash=True, tent="tuck"), 80)]}


def rise():
    """On the way up: pulses with long tentacles."""
    f = Pose(eyes="wide")
    return {"loop": [(f.but(tent="long"), 110), (f.but(tent="tuck"), 100)]}


def sink():
    """On the way down: tentacles spread like a parachute."""
    return {"loop": [(Pose(tent="spread", arm_f=("up_l", "up_r")), 160), (Pose(tent="spread"), 160)]}


# ---------------------------------------------------------------- reactions
def startle():
    up = ("up_l", "up_r")
    bang = [(BANG, BX + 18, BY - 7)]
    intro = [(Pose(), 120), (Pose(eyes="wide", dy=-3, tent="spread", arm_f=up, parts=bang), 90),
             (Pose(eyes="wide", dy=-5, tent="spread", arm_f=up, parts=bang), 140),
             (Pose(eyes="wide", dy=-3, tent="long", arm_f=up, parts=bang), 90),
             (Pose(eyes="wide", squash=True, tent="spread"), 110),
             (Pose(eyes="wide", ex=-1), 350), (Pose(eyes="wide", ex=1), 350), (Pose(eyes="blink"), 100),
             (Pose(), 250)]
    return {"intro": intro, "loop": []}


def tickled_b():
    """Rolls from side to side laughing."""
    intro = []
    for t in range(10):
        side = 1 if t % 2 else -1
        intro.append((Pose(eyes="happy", blush=True, dx=side, tent="right" if side > 0 else "left",
                           arm_f=("up_l", "up_r"),
                           parts=[(GIGGLE, BX + (19 if side < 0 else -4), BY - 3 + t % 3)]), 120))
    intro += [(Pose(eyes="happy", blush=True, squash=True, tent="spread"), 160), (Pose(eyes="happy", blush=True), 300)]
    return {"intro": intro, "loop": []}


def petted_b():
    """Leans into the hand and melts a little."""
    intro = [(Pose(eyes="happy", blush=True), 220), (Pose(eyes="sleep", blush=True, dx=-1), 300)]
    for t in range(4):
        intro.append((Pose(eyes="sleep", blush=True, dx=-1, squash=t % 2 == 0, tent="spread" if t % 2 == 0 else "straight",
                           parts=[(HEART, BX + 16, BY - 3 - t)]), 360))
    intro += [(Pose(eyes="sleep", blush=True, dx=0, squash=True, tent="spread"), 400),
              (Pose(eyes="happy", blush=True), 300)]
    return {"intro": intro, "loop": []}


def done_b():
    """Variant of 'done': a happy spin jump with stars."""
    up = ("up_l", "up_r")
    stars = lambda k: [(STAR, BX - 3 + k, BY - 3 - k), (STAR, BX + 17 - k, BY - 1 - k)]
    intro = [(Pose(eyes="happy", squash=True, tent="spread"), 110), (Pose(eyes="happy", dy=-3, tent="long", arm_f=up), 80),
             (Pose(eyes="happy", dy=-5, side=True, tent="long"), 90),
             (Pose(eyes="happy", dy=-6, side=True, flip=True, tent="long"), 90),
             (Pose(eyes="happy", dy=-5, arm_f=up, parts=stars(0)), 120),
             (Pose(eyes="happy", dy=-2, tent="spread", arm_f=up, parts=stars(1)), 120),
             (Pose(eyes="happy", squash=True, tent="spread", parts=stars(2)), 110)]
    loop = []
    for t in range(8):
        loop.append((Pose(eyes="happy", curvy=True, tp=wave(t // 2), arm_f=up if t % 4 < 2 else ("rest_l", "rest_r"),
                          parts=[(SPARKLE, BX + 16 + t % 2, BY - 4)] if t % 4 == 0 else []), 200))
    loop.append((Pose(eyes="happy", curvy=True, tp=wave(0)), 500))
    return {"intro": intro, "loop": loop, "outro": [(Pose(eyes="happy"), 200), (Pose(), 160)]}


def music_bop():
    """Bops along to the music with headphones on, eyes closed. The 'do not just dance all the time' option."""
    loop = []
    for t in range(12):
        nod = t % 2
        notes = [(NOTE if (t // 3) % 2 else NOTE2, BX + 17 + (t % 3), BY - 2 - (t % 4))] if t % 3 == 0 else []
        loop.append((Pose(headset="phones", eyes="sleep" if t % 6 < 4 else "happy", ey=nod,
                          tent=("left", "straight", "right", "straight")[(t // 2) % 4], parts=notes), 300))
    return {"intro": [(Pose(headset="phones"), 200)], "loop": loop, "outro": [(Pose(headset="phones"), 150)]}


# ---------------------------------------------------------------- new actions
def calendar_page():
    """An appointment starts: it pulls out a calendar page, reads it, gets it, tears the page off."""
    hold = ("rest_l", "up_r")
    intro = []
    path = [(BX + 19, BY + 9), (BX + 18, BY + 5), (BX + 17, BY + 2), (BX + 16, BY + 1)]
    for i, (x, y) in enumerate(path):
        intro.append((Pose(ex=1, ey=1 if i else 0, arm_f=hold, parts=[(CAL_PAGE, x, y)]), 90))
    page = [(CAL_PAGE, BX + 16, BY + 1)]
    intro += [(Pose(ex=1, ey=1, arm_f=hold, parts=page), 380), (Pose(ex=1, ey=1, eyes="blink", arm_f=hold, parts=page), 100),
              (Pose(ex=1, ey=1, arm_f=hold, parts=page), 300),
              (Pose(eyes="wide", ex=1, arm_f=hold, parts=page + [(BANG, BX + 9, BY - 7)]), 400),
              (Pose(eyes="happy", arm_f=("up_l", "up_r"), parts=[(CAL_TORN, BX + 16, BY + 3), (CAL_PAGE[:2], BX + 17, BY - 1)]), 160),
              (Pose(eyes="happy", arm_f=("up_l", "rest_r"), parts=[(CAL_TORN, BX + 16, BY + 3), (CAL_PAGE[:2], BX + 19, BY - 4)]), 160),
              (Pose(eyes="happy", parts=[(CAL_TORN, BX + 16, BY + 3), (CAL_PAGE[:2], BX + 22, BY - 7)]), 160),
              (Pose(eyes="happy", dy=-1, tent="long", parts=[(CAL_TORN, BX + 16, BY + 3)]), 140),
              (Pose(eyes="happy", parts=[(CAL_TORN, BX + 16, BY + 4)]), 300),
              (Pose(ex=1, parts=[(CAL_TORN, BX + 18, BY + 8)]), 120), (Pose(), 200)]
    return {"intro": intro, "loop": []}


def working_b():
    """Second laptop pose for 'working': front view, laptop on its lap, screen glow on the face."""
    lap = lambda dy=0: [(LAP_BACK, BX + 2, BY + 8 + dy)]
    intro = [(Pose(), 150), (Pose(ey=1, parts=[(LAP_BACK, BX + 2, BY + 11)]), 110), (Pose(ey=1, parts=lap(1)), 110),
             (Pose(ey=1, parts=lap()), 200)]
    loop = []
    for t in range(16):
        typing = t % 8 < 6
        loop.append((Pose(ey=1, ex=-1 if t == 7 else 0, tent="tuck" if typing and t % 2 else "spread",
                          dy=-(t % 2) if typing else 0, eyes="blink" if t == 15 else "open",
                          parts=lap(-(t % 2) if typing else 0)), 110 if typing else 260))
    outro = [(Pose(ey=1, eyes="happy", parts=lap()), 200), (Pose(eyes="happy", parts=[(LAP_BACK, BX + 2, BY + 11)]), 100),
             (Pose(), 160)]
    return {"intro": intro, "loop": loop, "outro": outro}


def search_b():
    """Second pose for 'search': reads a book and checks it with the magnifier."""
    hold = ("rest_l", "up_r")
    loop = []
    xs = [0, 1, 2, 3, 2, 1]
    for t in range(12):
        x = xs[t % 6]
        book = BOOK_FLIP if t == 8 else BOOK
        loop.append((Pose(ex=1, ey=1, arm_f=hold, eyes="blink" if t == 5 else "open",
                          parts=[(book, BX + 14, BY + 4), (GLASS, BX + 13 + x, BY + 2 - (t % 2))]), 200))
    return {"intro": [(Pose(ex=1, ey=1, arm_f=hold, parts=[(BOOK, BX + 14, BY + 5)]), 160)], "loop": loop,
            "outro": [(Pose(), 120)]}


# ---------------------------------------------------------------- physics poses
HELD = {s: Pose(eyes="wide", arm_f=("up_l", "up_r"), tent=t)
        for s, t in ((-1, "swing_l"), (0, "long"), (1, "swing_r"))}


def held():
    return {"loop": [(HELD[0], 400), (HELD[1], 300), (HELD[0], 300), (HELD[-1], 300)]}


def fall():
    p = Pose(eyes="wide", arm_f=("up_l", "up_r"))
    return {"loop": [(p.but(tent="tuck"), 90), (p.but(tent="spread"), 90)]}


def land():
    return {"intro": [(Pose(eyes="blink", squash=True, tent="spread"), 110),
                      (Pose(dy=-1, tent="long"), 70), (Pose(), 120)], "loop": []}


# ---------------------------------------------------------------- compacting, more tool poses
PAPER_STACK = ["WWWWWWW", "wwwwwww", "WWWWWWW", "wwwwwww", "WWWWWWW", "wwwwwww", "WWWWWWW", "wwwwwww"]
PAPER_BRICK = ["kkkkkkk", "WWWWWWW", "GGGGGGG"]


def compact():
    """The agent compresses its context: a tall pile of notes is pressed into one small brick."""
    x, floor = BX + 17, FEET - 1
    pile = lambda rows: [(PAPER_STACK[:rows], x, floor - rows + 1)]
    brick = [(PAPER_BRICK, x, floor - 2)]
    press = ("rest_l", "up_r")
    intro = [(Pose(ex=1, parts=pile(8)), 260),
             (Pose(ex=1, ey=1, arm_f=press, parts=pile(8)), 220),
             (Pose(ex=1, ey=1, eyes="sleep", arm_f=press, parts=pile(6)), 180),
             (Pose(ex=1, ey=1, eyes="sleep", arm_f=press, squash=True, parts=pile(4)), 180),
             (Pose(ex=1, ey=1, eyes="sleep", squash=True, parts=pile(3)), 180),
             (Pose(ex=1, ey=1, eyes="sleep", parts=brick), 220),
             (Pose(ex=1, ey=1, eyes="happy", parts=brick + [(SPARKLE, x + 5, floor - 6)]), 320),
             (Pose(ex=1, ey=1, eyes="happy", parts=brick + [(SPARKLE, x + 1, floor - 7)]), 320),
             (Pose(eyes="happy", parts=brick), 260)]
    return {"intro": intro, "loop": [], "outro": [(Pose(), 160)]}


def _log_window(t):
    rows = ["gggggggggggg"] + ["gnnnnnnnnnng"] * 5 + ["gggggggggggg"]
    rows = [list(r) for r in rows]
    lengths = (6, 3, 8, 5, 7, 2, 4, 8)
    for line in range(5):
        k = t // 2 + line
        if line == 4 and t % 2 == 0:
            rows[1 + line][2] = "W"
            continue
        for i in range(lengths[k % len(lengths)]):
            rows[1 + line][2 + i] = "c" if k % 3 == 0 else "w"
    return ["".join(r) for r in rows]


def terminal_b():
    """Second pose for 'terminal': watches a log scroll by in a window above its head."""
    win = lambda t: [(_log_window(t), BX + 2, BY - 9)]
    loop = []
    for t in range(12):
        loop.append((Pose(ey=-1, eyes="blink" if t == 9 else "open",
                          arm_f=("rest_l", "up_r") if t % 4 < 2 else ("rest_l", "rest_r"), parts=win(t)), 170))
    return {"intro": [(Pose(ey=-1, parts=win(0)), 200)], "loop": loop, "outro": [(Pose(), 120)]}


def _page(t):
    rows = ["ggggggggggg", "gRgYgcggggg", "gWWWWWWWWWg", "gWWWWWWWWWg", "gWWWWWWWWWg", "gWWWWWWWWWg", "gWWWWWWWWWg",
            "gWWWWWWWWWg", "ggggggggggg"]
    rows = [list(r) for r in rows]
    content = ("SSSSSSS", "", "wwwwwww", "wwwww", "", "BBB", "wwwwwww", "wwww", "", "SSSSS", "wwwwww", "www")
    for line in range(6):
        text = content[(t + line) % len(content)]
        for i, ch in enumerate(text):
            rows[2 + line][2 + i] = ch
    return ["".join(r) for r in rows]


def browse_b():
    """Second pose for 'browse': scrolls through a web page in a little browser window."""
    win = lambda t: [(_page(t), BX + 17, BY - 2)]
    loop = []
    for t in range(12):
        loop.append((Pose(ex=1, ey=(0, 0, 1, 1)[t % 4], eyes="blink" if t == 7 else "open",
                          arm_f=("rest_l", "up_r"), parts=win(t)), 200))
    return {"intro": [(Pose(ex=1, parts=win(0)), 160)], "loop": loop, "outro": [(Pose(), 120)]}


# ---------------------------------------------------------------- more idle actions
ROD = ["....q", "...q.", "..q..", ".q...", "q...."]
BOOT = ["qq..", "qq..", "qqqq", "bbbb"]


def fishing(catch=None):
    """Casts a line over the edge, waits, and pulls up a fish (or, now and then, an old boot)."""
    catch = catch or FISH
    lucky = catch is FISH
    hold = ("rest_l", "up_r")
    rod = (ROD, BX + 17, BY - 2)
    lx, top = BX + 21, BY - 1
    line = lambda n, end=("R",): [rod, (["w"] * n, lx, top), (list(end), lx - len(end[0]) // 2, top + n)]
    deep = CH - top - 2
    intro = [(Pose(ex=1, arm_f=hold, parts=[rod]), 260)]
    intro += [(Pose(ex=1, ey=1, arm_f=hold, parts=line(n)), 110) for n in (5, 10, deep)]
    for t in range(6):
        intro.append((Pose(ex=1, ey=1, arm_f=hold, eyes="blink" if t == 3 else "open",
                           parts=line(deep - (t % 2))), 430))
    intro.append((Pose(ex=1, ey=1, eyes="wide", arm_f=hold, parts=line(deep) + [(BANG, BX + 12, BY - 7)]), 260))
    intro.append((Pose(ex=1, ey=1, eyes="wide", arm_f=hold, dy=-1, parts=line(10, catch)), 150))
    intro.append((Pose(ex=1, eyes="wide", arm_f=hold, dy=-1, parts=line(4, catch)), 150))
    shown = "happy" if lucky else "sleep"
    intro.append((Pose(ex=1, eyes=shown, blush=lucky, arm_f=hold, parts=line(2, catch)), 420))
    intro.append((Pose(ex=1, eyes=shown, blush=lucky, arm_f=hold, dy=-1 if lucky else 0, parts=line(2, catch)), 420))
    return {"intro": intro, "loop": [], "outro": [(Pose(eyes=shown), 220)]}


BOARD = [".TTTTTTTTTTTT.", "..G........G.."]


def skateboard():
    """Rolls a little way along the edge on a skateboard and back again."""
    board = lambda dx: [(BOARD, BX + 1 + dx, FEET - 2)]
    out = ("up_l", "up_r")
    intro = [(Pose(ey=1, parts=board(0)), 240),
             (Pose(ey=1, dy=-4, tent="long", parts=board(0)), 120),
             (Pose(dy=-2, tent="spread", parts=board(0)), 160),
             (Pose(dy=-2, tent="spread", arm_f=out, eyes="happy", parts=board(0)), 200)]
    for dx in (2, 4, 6):
        intro.append((Pose(dy=-2, dx=dx, tent="left", arm_f=out, eyes="happy", parts=board(dx)), 130))
    intro.append((Pose(dy=-2, dx=6, tent="spread", arm_f=out, eyes="happy", parts=board(6)), 320))
    for dx in (4, 2, 0):
        intro.append((Pose(dy=-2, dx=dx, tent="right", arm_f=out, eyes="happy", parts=board(dx)), 130))
    intro.append((Pose(dy=-2, tent="spread", arm_f=out, eyes="happy", blush=True, parts=board(0)), 360))
    intro.append((Pose(dy=-2, tent="spread", eyes="happy", blush=True, parts=board(0)), 200))
    return {"intro": intro, "loop": [], "outro": [(Pose(eyes="happy"), 200)]}


TELESCOPE = [".....hH", "....hH.", "...hH..", "..hH...", ".kH....", "..q....", ".q.q...", "q...q.."]
TRAIL = ["y...", ".y..", "..Y.", "...W"]


def stargaze():
    """Late in the evening: looks through a telescope while a shooting star crosses the sky."""
    scope = (TELESCOPE, BX + 17, BY + 4)
    sky = [(BX + 1, BY - 9), (BX + 8, BY - 11), (BX + 25, BY - 6), (BX + 14, BY - 8)]
    stars = lambda t: [(["W" if (t + k) % 3 else "w"], x, y) for k, (x, y) in enumerate(sky)]
    hold = ("rest_l", "up_r")
    intro = [(Pose(ex=1, parts=[scope]), 260), (Pose(ex=1, ey=-1, arm_f=hold, parts=[scope] + stars(0)), 300)]
    for t in range(1, 7):
        intro.append((Pose(ex=1, ey=-1, arm_f=hold, eyes="blink" if t == 4 else "open",
                           parts=[scope] + stars(t)), 340))
    for k in range(4):
        intro.append((Pose(ex=(-1, 0, 1, 1)[k], ey=-1, eyes="wide", arm_f=hold,
                           parts=[scope] + stars(7 + k) + [(TRAIL, BX - 2 + k * 6, BY - 11 + k * 2)]), 120))
    intro.append((Pose(ex=1, ey=-1, eyes="happy", arm_f=hold, parts=[scope] + stars(11)), 420))
    intro.append((Pose(ex=1, ey=-1, eyes="happy", blush=True, arm_f=hold, parts=[scope] + stars(12)), 480))
    return {"intro": intro, "loop": [], "outro": [(Pose(eyes="happy"), 200)]}


# ---------------------------------------------------------------- more weather
STORM_CLOUD = ["..GGGGGG....", ".GGGGGGGGGG.", "GGGGGGGGGGGG", ".GGGGGGGGGG."]
LIGHTNING = [".YY", "YY.", "YYY", ".YY", "YY."]


def stormy():
    """Thunderstorm: a dark cloud, rain, and a flash that makes it jump."""
    intro = []
    for t in range(12):
        flash = t in (4, 9)
        drops = [(["S"], BX + x, BY - 3 + (t * 2 + k * 3) % 11) for k, x in enumerate((-2, 18, 21))]
        parts = [(STORM_CLOUD, BX + 14, BY - 9)] + drops
        if flash:
            parts.append((LIGHTNING, BX + 19, BY - 5))
        p = Pose(ey=-1, ex=1, eyes="wide" if flash or t in (5, 10) else "open", dy=-1 if flash else 0, parts=parts)
        intro.append((with_weather(p, "rain"), 170 if not flash else 110))
    return {"intro": intro, "loop": []}


FOG = ["wwwwwww..www", "..wwwwwwww.."]


def drifting(rows, x, y):
    """A prop that may hang over the left or right edge of the canvas: only the visible columns are kept."""
    lo, hi = max(0, -x), max(0, min(len(rows[0]), CW - x))
    return ([r[lo:hi] for r in rows] if hi > lo else ["."], max(0, min(x, CW - 1)), y)


def foggy():
    """Fog: grey banks drift past while it peers around."""
    intro = []
    for t in range(12):
        banks = [drifting(FOG, t * 2 - 6, BY - 5), drifting(FOG[::-1], 26 - t * 2, BY + 9),
                 drifting(FOG, t * 2 + 8, BY + 2)]
        intro.append((Pose(ex=(-1, -1, -1, 0, 1, 1, 1, 0)[t % 8], eyes="sleep" if t in (5, 6) else "open",
                           parts=banks), 240))
    return {"intro": intro, "loop": []}


LEAF = [".v", "vv", "v."]


def windy():
    """Wind: gusts streak past, a leaf flies by and it leans against it."""
    intro = [(Pose(ex=1), 160)]
    for t in range(12):
        gust = [drifting(["wwww"], 30 - (t * 5 + k * 9) % 36, BY - 4 + k * 6) for k in range(3)]
        leaf = [drifting(LEAF, 30 - t * 3, BY - 6 + (t % 3))]
        hard = 3 <= t < 9
        intro.append((Pose(ex=1, eyes="sleep" if hard else "open", dx=-1 if hard else 0,
                           tent="left" if t >= 1 else "straight", parts=gust + leaf), 150))
    intro.append((Pose(eyes="blink"), 160))
    return {"intro": intro, "loop": []}


ANIMATIONS = {"ponder": ponder, "idle": idle, "working": working, "thinking": thinking, "question": question, "done": done,
              "sleeping": sleeping, "error": error, "happy": happy, "sad": sad,
              "held": held, "fall": fall, "land": land,
              "hot": hot, "battery_low": battery_low, "charging": charging, "zap": zap, "offline": offline,
              "hello": hello, "yawn": yawn, "dizzy": dizzy, "shy": shy,
              "call": call, "call_muted": lambda: call("muted"), "call_deaf": lambda: call("deaf"),
              "music": music, "look_around": look_around, "bubbles": bubbles, "read": read,
              "sneeze": sneeze, "bye": bye, "water": water, "angry": angry, "swim": swim, "mail": mail,
              "focus": focus, "alarm": alarm, "stretch": stretch, "exhausted": exhausted,
              "climb": climb, "snack": lambda: eat(FISH), "nom": lambda: eat(NOTE_PAPER), "camera": camera,
              "trophy": trophy, "peek": peek, "carry": carry, "reminder": reminder, "rainy": rainy,
              "sunny": sunny, "snowy": snowy, "shiver": shiver, "cloudy": cloudy,
              "search": search, "terminal": terminal, "browse": browse, "todo": todo, "checkoff": checkoff, "tickled": tickled,
              "petted": petted, "trash_full": trash_full, "sweep": sweep, "warn": warn,
              "cooking": cooking, "yoyo": yoyo, "juggle": juggle, "coffee": coffee, "gaming": gaming,
              "paper_plane": paper_plane, "bubblegum": bubblegum, "doodle": doodle,
              "compact": compact, "terminal_b": terminal_b, "browse_b": browse_b, "fishing": fishing,
              "fishing_boot": lambda: fishing(BOOT), "skateboard": skateboard,
              "stargaze": stargaze, "stormy": stormy, "foggy": foggy, "windy": windy,
              "float": float_idle, "tug": tug, "breathe": breathe, "hop_prep": hop_prep, "rise": rise, "sink": sink,
              "startle": startle, "tickled_b": tickled_b, "petted_b": petted_b, "done_b": done_b,
              "music_bop": music_bop, "calendar": calendar_page, "working_b": working_b, "search_b": search_b}

# alternatives the player picks from when it starts one of these, so the same thing does not always look the same
VARIANTS = {"done": ["done", "done_b"], "tickled": ["tickled", "tickled_b"], "petted": ["petted", "petted_b"],
            "working": ["working", "working_b"], "search": ["search", "search_b"], "music": ["music", "music_bop"],
            "terminal": ["terminal", "terminal_b"], "browse": ["browse", "browse_b"],
            "fishing": ["fishing", "fishing", "fishing", "fishing_boot"]}


# how much slower the short reactions play so they can be seen without staring at the pet
SLOWER = {"look_around": 1.8, "bubbles": 1.7, "sneeze": 1.8, "yawn": 1.4, "stretch": 1.4, "yoyo": 1.9,
          "juggle": 1.8, "gaming": 1.6, "paper_plane": 1.8, "bubblegum": 1.7, "doodle": 1.7, "hello": 1.6,
          "bye": 1.6, "shy": 1.6, "dizzy": 1.4, "camera": 1.6, "mail": 1.5, "reminder": 1.4, "tickled": 1.6,
          "petted": 1.2, "trophy": 1.5, "coffee": 1.2, "read": 1.1, "water": 1.2, "snack": 1.3, "nom": 1.3,
          "happy": 1.4, "checkoff": 1.5, "zap": 1.3, "startle": 1.2, "calendar": 1.3, "tickled_b": 1.4,
          "petted_b": 1.2}


def slow_down(anim, k):
    for seg in ("intro", "loop", "outro"):
        if anim.get(seg):
            anim[seg] = [(p, max(130, int(ms * k))) for p, ms in anim[seg]]
    return anim


def build_all():
    anims = {name: fn() for name, fn in ANIMATIONS.items()}
    for name, k in SLOWER.items():
        if name in anims:
            slow_down(anims[name], k)
    return anims


def full(anim):
    return anim.get("intro", []) + anim["loop"] + anim.get("outro", [])
