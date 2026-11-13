"""The little pills above the pet, drawn with a 3x5 pixel font."""

from PIL import Image, ImageDraw

GLYPHS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
    "!": [".#.", ".#.", ".#.", "...", ".#."],
    "m": ["...", "##.", "###", "#.#", "#.#"],
    ":": ["...", ".#.", "...", ".#.", "..."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "z": ["...", "###", ".#.", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "C": ["###", "#..", "#..", "#..", "###"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "S": ["###", "#..", "###", "..#", "###"],
    "G": ["###", "#..", "#.#", "#.#", "###"],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "P": ["###", "#.#", "###", "#..", "#.."],
    "s": ["...", ".##", "#..", "..#", "##."],
    "h": ["#..", "#..", "###", "#.#", "#.#"],
    "k": ["#..", "#.#", "##.", "#.#", "#.#"],
}


BADGE_ICONS = {
    "timer": ["#####", ".###.", "..#..", ".###.", "#####"],
    "sessions": ["##.##", "##.##", ".....", "##.##", "##.##"],
    "clicks": [".#.#.", "##.##", "#####", "#####", ".###."],
    "call": [".###.", "#...#", "#...#", "##.##", "##.##"],
    "msg": ["#####", "##.##", "#.#.#", "#...#", "#####"],
    "due": [".###.", "#.#.#", "#.###", "#...#", ".###."],
    "cal": ["#.#.#", "#####", "#...#", "#.#.#", "#####"],
    "note": ["..###", "..#.#", "..#..", "###..", "##..."],
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
    img.spans = []
    for item, p in zip(items, pills):
        img.alpha_composite(p, (x, 0))
        img.spans.append((x, x + p.width, item[2] if len(item) > 2 else None))
        x += p.width + 2
    tail = tuple(items[-1][1][:3]) + (255,)
    tx = img.width - 7
    for k in range(3):
        for dx in range(5 - 2 * k):
            img.putpixel((tx + k + dx, 9 + k), tail)
    return img
