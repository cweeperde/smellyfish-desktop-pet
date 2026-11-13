"""Calendars: a local one, imported .ics files and read-only subscriptions (live links).

The list of calendars lives in the settings ("calendars"); the events of each calendar live in their own file
(<home>/calendars/<id>.json), so removing a calendar never touches the others and the settings file stays small.
Times are stored as local wall-clock time: "YYYY-MM-DDTHH:MM" for timed events, "YYYY-MM-DD" for all-day ones.
"""

import datetime as dt
import json
import logging
import os
import re
import threading
import urllib.request
import uuid

from dateutil import rrule as rr
from dateutil import tz as dtz

from smellyfish.paths import HOME_DIR

log = logging.getLogger("smellyfish.calendar")

DIR = os.path.join(HOME_DIR, "calendars")
COLOR_NAMES = [
    ("#c492ec", "Lavender"),
    ("#78b8ff", "Sky"),
    ("#82e696", "Mint"),
    ("#ffb070", "Peach"),
    ("#ff8aa8", "Pink"),
    ("#ffd250", "Sun"),
    ("#7fdcd0", "Lagoon"),
    ("#b0a4c8", "Pebble"),
]
COLORS = [c for c, _name in COLOR_NAMES]
FREQS = ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]
REMIND = [
    ("No reminder", None),
    ("At start", 0),
    ("5 min before", 5),
    ("10 min before", 10),
    ("30 min before", 30),
    ("1 hour before", 60),
    ("1 day before", 1440),
]
MAX_EVENTS = 20000
FETCH_TIMEOUT = 20


# ---------------------------------------------------------------- time helpers
def fmt(d):
    return d.strftime("%Y-%m-%d") if not isinstance(d, dt.datetime) else d.strftime("%Y-%m-%dT%H:%M")


def parse(text):
    """'2026-11-07' -> date, '2026-11-07T14:30' -> naive local datetime."""
    if "T" in text:
        return dt.datetime.strptime(text[:16], "%Y-%m-%dT%H:%M")
    return dt.datetime.strptime(text[:10], "%Y-%m-%d").date()


def as_dt(d):
    return d if isinstance(d, dt.datetime) else dt.datetime(d.year, d.month, d.day)


def occ_key(ev, start):
    return f"{ev['uid']}@{fmt(start)}"


# ---------------------------------------------------------------- recurrence
def simple_rule(freq, interval=1, until=None):
    """RRULE text for the editor's simple repeat options."""
    if not freq:
        return ""
    rule = f"FREQ={freq}"
    if interval and interval > 1:
        rule += f";INTERVAL={int(interval)}"
    if until:
        rule += f";UNTIL={until.strftime('%Y%m%d')}T235959"
    return rule


def describe_rule(rule):
    """(freq, interval, until date) of an RRULE, or None when the editor cannot show it exactly."""
    if not rule:
        return "", 1, None
    parts = dict(p.split("=", 1) for p in rule.upper().split(";") if "=" in p)
    if set(parts) - {"FREQ", "INTERVAL", "UNTIL", "WKST"} or parts.get("FREQ") not in FREQS:
        return None
    until = None
    if parts.get("UNTIL"):
        try:
            until = dt.datetime.strptime(parts["UNTIL"][:8], "%Y%m%d").date()
        except ValueError:
            return None
    return parts["FREQ"], int(parts.get("INTERVAL", "1") or 1), until


def _rule_for(ev, start):
    rule = ev["rrule"]
    if isinstance(start, dt.datetime):
        rule = re.sub(r"UNTIL=(\d{8})(?!T)", r"UNTIL=\1T235959", rule)
    else:
        rule = re.sub(r"UNTIL=(\d{8})T\d{6}Z?", r"UNTIL=\1", rule)
    rule = re.sub(r"(UNTIL=\d{8}T\d{6})Z", r"\1", rule)
    return rr.rrulestr(rule, dtstart=as_dt(start), ignoretz=True)


def occurrences(ev, lo, hi):
    """Starts of the event between lo and hi (naive datetimes); an event that started before lo but is still
    running counts too."""
    start, end = parse(ev["start"]), parse(ev["end"])
    length = as_dt(end) - as_dt(start)
    if not ev.get("rrule"):
        return [start] if as_dt(start) < hi and as_dt(start) + max(length, dt.timedelta(minutes=1)) > lo else []
    try:
        rule = _rule_for(ev, start)
    except (ValueError, TypeError):
        return [start] if lo <= as_dt(start) < hi else []
    skip = set(ev.get("exdates") or [])
    out = []
    for when in rule.between(lo - length - dt.timedelta(seconds=1), hi, inc=True):
        if when + max(length, dt.timedelta(minutes=1)) <= lo or when >= hi:
            continue
        occ = when if isinstance(start, dt.datetime) else when.date()
        if fmt(occ) not in skip:
            out.append(occ)
        if len(out) > 400:
            break
    return out


# ---------------------------------------------------------------- ICS parsing
def _unfold(text):
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        elif raw:
            lines.append(raw)
    return lines


def _prop(line):
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    opts = {}
    for p in params:
        k, _, v = p.partition("=")
        opts[k.upper()] = v.strip('"')
    return name.upper(), opts, value


def _text(value):
    return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _zone(name):
    if not name:
        return None
    return dtz.gettz(name) or dtz.gettz(name.split("/")[-1].replace("_", " "))


def _when(value, opts):
    """An ICS date or date-time as a local date / naive local datetime."""
    value = value.strip()
    if opts.get("VALUE") == "DATE" or len(value) == 8:
        return dt.datetime.strptime(value[:8], "%Y%m%d").date()
    t = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        t = t.replace(tzinfo=dt.timezone.utc)
    else:
        zone = _zone(opts.get("TZID"))
        if zone is None:
            return t.replace(second=0)
        t = t.replace(tzinfo=zone)
    return t.astimezone(dtz.tzlocal()).replace(tzinfo=None, second=0)


def _duration(value):
    m = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value.strip())
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    w, d, h, mi, s = (int(g or 0) for g in m.groups()[1:])
    return sign * dt.timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


def parse_ics(text):
    """Returns (calendar name or None, events). Unknown parts of the file are skipped."""
    name, events, cur, alarm, depth = None, [], None, None, []
    overrides = []
    for line in _unfold(text):
        key, opts, value = _prop(line)
        if key == "BEGIN":
            depth.append(value.upper())
            if value.upper() == "VEVENT":
                cur = {"props": {}, "exdates": [], "alarm": None}
            elif value.upper() == "VALARM" and cur is not None:
                alarm = {}
            continue
        if key == "END":
            kind = depth.pop() if depth else ""
            if kind == "VALARM" and cur is not None and alarm is not None:
                trig = alarm.get("TRIGGER")
                if trig is not None and cur["alarm"] is None:
                    mins = round(-trig.total_seconds() / 60)
                    cur["alarm"] = mins if mins >= 0 else None
                alarm = None
            elif kind == "VEVENT" and cur is not None:
                ev = _event_from(cur)
                if ev is not None:
                    (overrides if ev.get("_override") else events).append(ev)
                cur = None
                if len(events) > MAX_EVENTS:
                    break
            continue
        if alarm is not None:
            if (
                key == "TRIGGER"
                and opts.get("VALUE", "DURATION") == "DURATION"
                and opts.get("RELATED", "START") == "START"
            ):
                alarm["TRIGGER"] = _duration(value)
            continue
        if cur is not None and depth and depth[-1] == "VEVENT":
            if key == "EXDATE":
                for v in value.split(","):
                    try:
                        cur["exdates"].append(fmt(_when(v, opts)))
                    except ValueError:
                        pass
            else:
                cur["props"][key] = (opts, value)
        elif key == "X-WR-CALNAME" and not name:
            name = _text(value).strip() or None
    by_uid = {e["uid"]: e for e in events}
    for ov in overrides:
        master = by_uid.get(ov["uid"])
        if master is not None:
            master.setdefault("exdates", []).append(ov.pop("_override"))
        ov.pop("_override", None)
        ov["uid"] = f"{ov['uid']}-{ov['start']}"
        events.append(ov)
    return name, events


def _event_from(cur):
    p = cur["props"]
    if "DTSTART" not in p or p.get("STATUS", ({}, ""))[1].upper() == "CANCELLED":
        return None
    try:
        start = _when(p["DTSTART"][1], p["DTSTART"][0])
        if "DTEND" in p:
            end = _when(p["DTEND"][1], p["DTEND"][0])
        elif "DURATION" in p and _duration(p["DURATION"][1]) is not None:
            end = start + _duration(p["DURATION"][1])
        else:
            end = start + (dt.timedelta(days=1) if not isinstance(start, dt.datetime) else dt.timedelta(0))
    except ValueError:
        return None
    if isinstance(start, dt.datetime) != isinstance(end, dt.datetime):
        end = start + (dt.timedelta(days=1) if not isinstance(start, dt.datetime) else dt.timedelta(hours=1))
    if as_dt(end) < as_dt(start):
        end = start
    ev = {
        "uid": (p.get("UID", ({}, ""))[1] or uuid.uuid4().hex),
        "title": _text(p.get("SUMMARY", ({}, ""))[1]) or "(no title)",
        "start": fmt(start),
        "end": fmt(end),
        "all_day": not isinstance(start, dt.datetime),
        "location": _text(p.get("LOCATION", ({}, ""))[1]),
        "notes": _text(p.get("DESCRIPTION", ({}, ""))[1])[:4000],
        "remind": cur["alarm"],
        "rrule": p.get("RRULE", ({}, ""))[1],
        "exdates": cur["exdates"],
    }
    if "RECURRENCE-ID" in p:
        try:
            ev["_override"] = fmt(_when(p["RECURRENCE-ID"][1], p["RECURRENCE-ID"][0]))
        except ValueError:
            return None
    return ev


# ---------------------------------------------------------------- ICS writing
def _esc(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    out, data = [], line.encode("utf-8")
    while len(data) > 74:
        cut = 74
        while cut > 0 and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(data[:cut].decode("utf-8"))
        data = b" " + data[cut:]
    out.append(data.decode("utf-8"))
    return "\r\n".join(out)


def _ics_time(text):
    d = parse(text)
    if isinstance(d, dt.datetime):
        return f":{d.strftime('%Y%m%dT%H%M%S')}"
    return f";VALUE=DATE:{d.strftime('%Y%m%d')}"


def to_ics(calendars):
    """calendars: [(name, events)]. Timed events are written as floating local time."""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Smellyfish//Calendar//EN", "CALSCALE:GREGORIAN"]
    if len(calendars) == 1:
        lines.append(f"X-WR-CALNAME:{_esc(calendars[0][0])}")
    for _name, events in calendars:
        for ev in events:
            lines += [
                "BEGIN:VEVENT",
                f"UID:{ev['uid']}",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{_esc(ev['title'])}",
                "DTSTART" + _ics_time(ev["start"]),
                "DTEND" + _ics_time(ev["end"]),
            ]
            if ev.get("location"):
                lines.append(f"LOCATION:{_esc(ev['location'])}")
            if ev.get("notes"):
                lines.append(f"DESCRIPTION:{_esc(ev['notes'])}")
            if ev.get("rrule"):
                lines.append(f"RRULE:{ev['rrule']}")
            for ex in ev.get("exdates") or []:
                lines.append("EXDATE" + _ics_time(ex))
            if ev.get("remind") is not None:
                lines += [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_esc(ev['title'])}",
                    f"TRIGGER:-PT{int(ev['remind'])}M",
                    "END:VALARM",
                ]
            lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- storage
class Calendars:
    """All calendars and their events. Not thread-safe: call from the Qt thread (fetch() runs the download in a
    thread and hands the result back through on_fetched)."""

    def __init__(self, cfg, on_fetched=None):
        self.cfg = cfg
        self.on_fetched = on_fetched
        self.meta = [dict(c) for c in (cfg.get("calendars") or []) if isinstance(c, dict) and c.get("id")]
        self.events = {}
        for c in self.meta:
            self.events[c["id"]] = self._load(c["id"])
        if not any(c["kind"] == "local" for c in self.meta):
            self.add("My calendar", "local", save=False)
        self._busy = set()

    def _path(self, cid):
        return os.path.join(DIR, f"{re.sub(r'[^a-z0-9]', '', cid)}.json")

    def _load(self, cid):
        try:
            with open(self._path(cid), encoding="utf-8") as f:
                data = json.load(f)
            return [e for e in data if isinstance(e, dict) and e.get("start") and e.get("end")]
        except (OSError, ValueError):
            return []

    def _write(self, cid):
        os.makedirs(DIR, exist_ok=True)
        tmp = self._path(cid) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.events.get(cid, []), f, ensure_ascii=False)
        os.replace(tmp, self._path(cid))

    def save_meta(self):
        self.cfg.set("calendars", [dict(c) for c in self.meta])

    def get(self, cid):
        return next((c for c in self.meta if c["id"] == cid), None)

    def local(self):
        return next(c for c in self.meta if c["kind"] == "local")

    def editable(self):
        return [c for c in self.meta if c["kind"] != "sub"]

    def add(self, name, kind, url="", events=None, save=True):
        used = {c["color"] for c in self.meta}
        color = next((c for c in COLORS if c not in used), COLORS[len(self.meta) % len(COLORS)])
        cal = {
            "id": uuid.uuid4().hex[:12],
            "name": name[:60] or "Calendar",
            "kind": kind,
            "color": color,
            "visible": True,
        }
        if kind == "sub":
            cal.update(url=url, refresh_min=60, fetched=0, error="")
        self.meta.append(cal)
        self.events[cal["id"]] = list(events or [])
        self._write(cal["id"])
        if save:
            self.save_meta()
        else:
            self.cfg["calendars"] = [dict(c) for c in self.meta]
        return cal

    def update(self, cid, **fields):
        cal = self.get(cid)
        if cal is not None:
            cal.update(fields)
            self.save_meta()

    def remove(self, cid):
        cal = self.get(cid)
        if cal is None or cal["kind"] == "local":
            return False
        self.meta = [c for c in self.meta if c["id"] != cid]
        self.events.pop(cid, None)
        try:
            os.remove(self._path(cid))
        except OSError:
            pass
        self.save_meta()
        return True

    def import_file(self, path):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            name, events = parse_ics(f.read())
        if not events:
            raise ValueError("No events found in this file.")
        base = name or os.path.splitext(os.path.basename(path))[0]
        return self.add(base, "import", events=events)

    # events
    def find(self, uid):
        for cid, events in self.events.items():
            for ev in events:
                if ev["uid"] == uid:
                    return cid, ev
        return None, None

    def save_event(self, cid, ev):
        """Adds or replaces an event (by uid); moves it when the calendar changed."""
        old_cid, _old = self.find(ev["uid"])
        if old_cid is not None and old_cid != cid:
            self.events[old_cid] = [e for e in self.events[old_cid] if e["uid"] != ev["uid"]]
            self._write(old_cid)
        items = [e for e in self.events.setdefault(cid, []) if e["uid"] != ev["uid"]] + [ev]
        self.events[cid] = items
        self._write(cid)

    def delete_event(self, uid, only=None):
        """only: the start (fmt) of one occurrence of a repeating event to skip instead of deleting all."""
        cid, ev = self.find(uid)
        if ev is None:
            return
        if only and ev.get("rrule"):
            ev.setdefault("exdates", []).append(only)
        else:
            self.events[cid] = [e for e in self.events[cid] if e["uid"] != uid]
        self._write(cid)

    def between(self, lo, hi, visible_only=True):
        """[(start, end, event, calendar)] sorted by start."""
        out = []
        for cal in self.meta:
            if visible_only and not cal.get("visible", True):
                continue
            for ev in self.events.get(cal["id"], []):
                for start in occurrences(ev, lo, hi):
                    length = as_dt(parse(ev["end"])) - as_dt(parse(ev["start"]))
                    end = as_dt(start) + length
                    out.append((as_dt(start), end, ev, cal))
        out.sort(key=lambda o: (o[0], not o[2].get("all_day"), o[2]["title"].lower()))
        return out

    def export(self, cids, path):
        cals = [(c["name"], self.events.get(c["id"], [])) for c in self.meta if c["id"] in cids]
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(to_ics(cals))

    # subscriptions
    def due_refresh(self, now):
        return [
            c
            for c in self.meta
            if c["kind"] == "sub"
            and c["id"] not in self._busy
            and now - float(c.get("fetched") or 0) > int(c.get("refresh_min") or 60) * 60
        ]

    def fetch(self, cid):
        cal = self.get(cid)
        if cal is None or cal["kind"] != "sub" or cid in self._busy:
            return
        self._busy.add(cid)
        url = cal["url"].strip()
        if url.lower().startswith("webcal://"):
            url = "https://" + url[9:]
        threading.Thread(target=self._download, args=(cid, url), daemon=True).start()

    def _download(self, cid, url):
        name, events, error = None, None, ""
        try:
            if not url.lower().startswith(("https://", "http://")):
                raise ValueError("The link has to start with https://, http:// or webcal://")
            req = urllib.request.Request(
                url, headers={"User-Agent": "Smellyfish calendar", "Accept": "text/calendar, */*"}
            )
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
                data = r.read(20 * 1024 * 1024 + 1)
            if len(data) > 20 * 1024 * 1024:
                raise ValueError("The calendar is too big (over 20 MB).")
            name, events = parse_ics(data.decode("utf-8-sig", errors="replace"))
            if not events and b"BEGIN:VCALENDAR" not in data[:4096].upper():
                raise ValueError("That link does not return a calendar (.ics).")
        except Exception as e:
            error = str(e)[:200] or e.__class__.__name__
            log.info("calendar subscription refresh failed: %s", e.__class__.__name__)
        if self.on_fetched:
            self.on_fetched(cid, name, events, error)

    def fetched(self, cid, name, events, error):
        """Called on the Qt thread with the download result."""
        import time

        self._busy.discard(cid)
        cal = self.get(cid)
        if cal is None:
            return
        cal["fetched"] = time.time()
        cal["error"] = error
        if events is not None:
            self.events[cid] = events
            self._write(cid)
            if name and cal.get("auto_name", True) and cal["name"] in ("", "Subscription"):
                cal["name"] = name[:60]
        self.save_meta()
