"""Pixel speech bubbles with buttons, rendered with PIL.

render(spec) returns (RGBA image, hit areas). Hit areas are (x0, y0, x1, y1, value)
in image pixels. One UI unit is UNIT screen pixels. Long text makes the bubble wider;
if it still does not fit, a "Show all" link expands it (spec["expanded"]).
"""
import re

from PIL import Image, ImageDraw, ImageFont, ImageOps

UNIT = 2
WIDTH, WIDE = 168, 236
FONT = ImageFont.load_default_imagefont()
SPACE = int(FONT.getlength(" "))


def draw_text(d, pos, text, font=FONT, fill=None):
    """The bitmap font cuts off the left arm of a leading T; a leading space avoids that."""
    d.text((pos[0] - SPACE, pos[1]), " " + text, font=font, fill=fill)
LINE = 11
TAIL_H = 8

INK = (34, 22, 52)
GREY = (120, 118, 140)
PAPER = (250, 250, 252)
LAV, LAV_D = (196, 146, 236), (150, 104, 200)
SEC, SEC_D = (226, 226, 236), (180, 180, 196)
CODE_BG = (30, 32, 48)
GREEN = (130, 230, 150)
YELLOW = (255, 210, 80)
SHADOW = (14, 16, 28, 150)
CHIP = {"ask": LAV, "perm": YELLOW, "done": GREEN, "wait": LAV, "focus": (255, 160, 60), "reminder": YELLOW,
        "discord": (150, 160, 255), "todo": (130, 200, 150), "trophy": YELLOW, "critical": (255, 110, 110)}

TEXT = INK
RULE = (228, 224, 240)
OUTLINE = (110, 78, 150)
DARK = False


def set_dark(on):
    """Switches the bubble palette between light and dark."""
    global PAPER, TEXT, GREY, SEC, SEC_D, CODE_BG, RULE, DARK
    DARK = bool(on)
    if DARK:
        PAPER, TEXT, GREY = (38, 32, 54), (242, 236, 250), (168, 154, 196)
        SEC, SEC_D, CODE_BG, RULE = (70, 60, 96), (46, 38, 68), (16, 13, 24), (70, 60, 96)
    else:
        PAPER, TEXT, GREY = (250, 250, 252), INK, (120, 118, 140)
        SEC, SEC_D, CODE_BG, RULE = (226, 226, 236), (180, 180, 196), (30, 32, 48), (228, 224, 240)


TERMINAL = "__terminal__"
EXPAND = "__expand__"


def md_plain(text):
    """Takes the markdown marks out of plain prose."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    return text


def code_lines(text, maxw, limit):
    """Code lines with their indentation kept; long lines are cut with a small hanging indent."""
    out = []
    for raw in clean(text).replace("\t", "    ").split("\n"):
        line = raw.rstrip()
        while text_w(line) > maxw and len(line) > 4:
            k = len(line)
            while k > 2 and text_w(line[:k]) > maxw:
                k -= 1
            out.append(line[:k])
            line = "  " + line[k:]
        out.append(line)
    cut = len(out) > limit
    return out[:limit], cut


def clean(text):
    text = str(text).replace("…", "...").replace("—", "-").replace("–", "-")
    text = text.replace("“", '"').replace("”", '"').replace("„", '"').replace("’", "'")
    return text.encode("latin-1", "replace").decode("latin-1")


def text_w(t):
    return FONT.getbbox(t)[2] if t else 0


def wrap(text, maxw, max_lines=6):
    """Returns (lines, truncated)."""
    lines = []
    for para in clean(text).split("\n"):
        cur = ""
        for word in para.split():
            while text_w(word) > maxw:
                cut = len(word)
                while cut > 1 and text_w(word[:cut]) > maxw:
                    cut -= 1
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(word[:cut])
                word = word[cut:]
            nxt = (cur + " " + word).strip()
            if text_w(nxt) > maxw and cur:
                lines.append(cur)
                cur = word
            else:
                cur = nxt
        if cur:
            lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and text_w(last + "...") > maxw:
            last = last[:-1]
        lines[-1] = last + "..."
        return lines, True
    return lines, False


def rrect(d, x0, y0, x1, y1, fill, cut=1):
    d.rectangle([x0 + cut, y0, x1 - cut, y1], fill=fill)
    d.rectangle([x0, y0 + cut, x1, y1 - cut], fill=fill)


class Layout:
    """Draws content top-down and records button hit areas (in UI units)."""

    def __init__(self, d, x, y, w, expanded=False):
        self.d, self.x, self.y, self.w = d, x, y, w
        self.expanded = expanded
        self.truncated = False
        self.hits = []

    def limit(self, n):
        return 60 if self.expanded else n

    def chip(self, label, fill, right=""):
        label = clean(label)[:24]
        w = text_w(label) + 6
        rrect(self.d, self.x, self.y, self.x + w, self.y + 11, fill)
        draw_text(self.d, (self.x + 3, self.y), label, font=FONT, fill=INK)
        if right:
            right = clean(right)
            draw_text(self.d, (self.x + self.w - text_w(right), self.y), right, font=FONT, fill=GREY)
        self.y += 15

    def text(self, text, max_lines=10, color=None, indent=0):
        color = color or TEXT
        lines, cut = wrap(text, self.w - indent, self.limit(max_lines))
        self.truncated |= cut
        for line in lines:
            draw_text(self.d, (self.x + indent, self.y), line, font=FONT, fill=color)
            self.y += LINE
        self.y += 3

    def rich(self, text, max_lines=12):
        """Prose with ``` code blocks: the blocks get the dark code box, the rest is plain text."""
        parts = re.split(r"```[^\n]*\n?(.*?)(?:```|$)", str(text), flags=re.S)
        for i, part in enumerate(parts):
            part = part.strip("\n")
            if not part.strip():
                continue
            if i % 2:
                self.code(part.rstrip(), max_lines=10)
            else:
                self.text(md_plain(part.strip()), max_lines=max_lines)

    def code(self, text, max_lines=6):
        lines, cut = code_lines(text, self.w - 8, self.limit(max_lines))
        self.truncated |= cut
        h = len(lines) * LINE + 4
        rrect(self.d, self.x, self.y, self.x + self.w - 1, self.y + h, CODE_BG)
        for i, line in enumerate(lines):
            draw_text(self.d, (self.x + 4, self.y + 2 + i * LINE), line, font=FONT, fill=GREEN)
        self.y += h + 5

    def buttons(self, items):
        """items: list of (label, value, primary). Two short ones share a row."""
        row = []
        half = (self.w - 4) // 2
        for label, value, primary in items:
            label = clean(label)
            if text_w(label) + 8 <= half and len(row) < 2:
                row.append((label, value, primary))
                if len(row) == 2:
                    self._row(row, half)
                    row = []
            else:
                if row:
                    self._row(row, half)
                    row = []
                self._button(self.x, self.w, label, value, primary)
                self.y += 17
        if row:
            self._row(row, half)

    def option(self, label, value, primary, desc):
        """A full-width answer button with its description underneath."""
        self._button(self.x, self.w, clean(label), value, primary)
        self.y += 16
        if desc:
            self.text(desc, max_lines=3, color=GREY, indent=4)
            self.y -= 1
        else:
            self.y += 1

    def _row(self, row, half):
        if len(row) == 1:
            self._button(self.x, self.w, *row[0])
        else:
            self._button(self.x, half, *row[0])
            self._button(self.x + half + 4, half, *row[1])
        self.y += 17

    def _button(self, x, w, label, value, primary):
        fill, edge = (LAV, LAV_D) if primary else (SEC, SEC_D)
        y = self.y
        rrect(self.d, x, y, x + w - 1, y + 14, edge)
        rrect(self.d, x, y, x + w - 1, y + 12, fill)
        while text_w(label) > w - 6 and len(label) > 3:
            label = label[:-4] + "..."
        draw_text(self.d, (x + (w - text_w(label)) // 2, y + 1), label, font=FONT, fill=INK if primary else TEXT)
        self.hits.append((x, y, x + w - 1, y + 14, value))

    def link(self, label, value):
        w = text_w(label)
        x = self.x + (self.w - w) // 2
        draw_text(self.d, (x, self.y), label, font=FONT, fill=GREY)
        self.d.line([(x, self.y + 10), (x + w, self.y + 10)], fill=GREY)
        self.hits.append((x - 2, self.y - 1, x + w + 2, self.y + 11, value))
        self.y += 12

    def links(self, items):
        """Several small links in one row (wrapped onto more rows when they do not fit)."""
        rows, row = [], []
        for item in items:
            if row and sum(text_w(l) for l, _ in row + [item]) + 12 * len(row) > self.w:
                rows.append(row)
                row = []
            row.append(item)
        rows.append(row)
        if len(rows) > 1:
            for r in rows:
                self.links(r)
            return
        total = sum(text_w(l) for l, _ in items) + 12 * (len(items) - 1)
        x = self.x + (self.w - total) // 2
        for label, value in items:
            w = text_w(label)
            draw_text(self.d, (x, self.y), label, font=FONT, fill=GREY)
            self.d.line([(x, self.y + 10), (x + w, self.y + 10)], fill=GREY)
            self.hits.append((x - 2, self.y - 1, x + w + 2, self.y + 11, value))
            x += w + 12
        self.y += 12


def content(lay, spec):
    kind = spec["kind"]
    extra = []
    if kind == "ask":
        lay.chip(spec.get("header") or "Question", CHIP["ask"], spec.get("page", ""))
        lay.text(spec["question"], max_lines=12)
        descs = spec.get("descs") or [""] * len(spec["options"])
        if spec.get("multi"):
            picked = set(spec.get("picked") or [])
            lay.text("Pick one or more:", color=GREY)
            for o, desc in zip(spec["options"], descs):
                lay.option(("[x] " if o in picked else "[ ] ") + o, ("toggle", o), o in picked, desc)
            lay.buttons([("Confirm", ("confirm",), bool(picked))])
        else:
            for i, (o, desc) in enumerate(zip(spec["options"], descs)):
                lay.option(o, ("option", o), i == 0, desc)
        extra = [("Type answer...", "__type__"), ("Answer in terminal", TERMINAL)]
    elif kind == "perm":
        lay.chip(spec.get("tool", "Tool"), CHIP["perm"], spec.get("right", ""))
        lay.text(spec.get("prompt", "Allow this?"), max_lines=4)
        if spec.get("detail"):
            lay.code(spec["detail"])
        items = [("Allow", "allow", True), ("Deny", "deny", False)]
        if spec.get("can_always"):
            items.append(("Always allow", "always", False))
        lay.buttons(items)
        extra = [("Answer in terminal", TERMINAL)]
    else:
        lay.chip(spec.get("chip", "Done"), CHIP.get(kind, GREEN), spec.get("right", ""))
        if spec.get("md"):
            lay.rich(spec.get("text", ""), max_lines=spec.get("max_lines", 12))
        else:
            lay.text(spec.get("text", ""), max_lines=spec.get("max_lines", 8))
        lay.buttons([tuple(b) for b in spec.get("buttons") or [("OK", "ok", True)]])
    if lay.truncated or lay.expanded:
        extra.append(("Show less" if lay.expanded else "Show all", EXPAND))
    if extra:
        lay.links(extra)


def width_for(spec):
    text = " ".join(str(spec.get(k, "")) for k in ("question", "text", "detail", "prompt"))
    text += " ".join(spec.get("descs") or [])
    return WIDE if len(text) > 150 or spec.get("expanded") or (spec.get("md") and "```" in text) else WIDTH


def render(spec, unit=UNIT, tail="bottom", side="left"):
    """tail='bottom' points down-left (bubble above the pet), 'top' points up-left (bubble below)."""
    pad = 6
    width = width_for(spec)
    expanded = bool(spec.get("expanded"))
    probe = Layout(ImageDraw.Draw(Image.new("RGB", (width, 2000))), pad, pad, width - 2 * pad, expanded)
    content(probe, spec)
    h = probe.y - 3 + pad
    top = TAIL_H if tail == "top" else 0
    img = Image.new("RGBA", (width + 2, h + TAIL_H + 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    rrect(ImageDraw.Draw(shadow), 2, top + 2, width + 1, top + h + 1, SHADOW, cut=2)
    img.alpha_composite(shadow)
    d = ImageDraw.Draw(img)
    tail_x = 12
    if DARK:
        rrect(d, 0, top, width - 1, top + h - 1, OUTLINE, cut=2)
        for i in range(4):
            y = h + i * 2 if tail == "bottom" else TAIL_H - 2 - i * 2
            d.rectangle([tail_x - i * 2 - 1, y - 1, tail_x - i * 2 + 6 - i, y + 2], fill=OUTLINE)
        rrect(d, 1, top + 1, width - 2, top + h - 2, PAPER, cut=1)
    else:
        rrect(d, 0, top, width - 1, top + h - 1, PAPER, cut=2)
    for i in range(4):
        y = h + i * 2 if tail == "bottom" else TAIL_H - 2 - i * 2
        d.rectangle([tail_x - i * 2, y, tail_x - i * 2 + 5 - i, y + 1], fill=PAPER)
    lay = Layout(d, pad, top + pad, width - 2 * pad, expanded)
    content(lay, spec)
    if side == "right":
        y0, y1 = (h, img.height) if tail == "bottom" else (0, TAIL_H)
        strip = img.crop((0, y0, img.width, y1))
        img.paste(ImageOps.mirror(strip), (0, y0))
    big = img.resize((img.width * unit, img.height * unit), Image.NEAREST)
    hits = [(x0 * unit, y0 * unit, (x1 + 1) * unit, (y1 + 1) * unit, v) for x0, y0, x1, y1, v in lay.hits]
    return big, hits
