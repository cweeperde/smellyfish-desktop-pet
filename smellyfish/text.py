"""Small text helpers: counters, durations and bubble-safe summaries."""

import re


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
