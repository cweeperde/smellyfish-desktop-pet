"""Calendar window: month and week view, calendar list (import, subscribe, export, remove) and the event editor."""

import datetime as dt
import uuid

from PySide6.QtCore import QDate, QRect, QSize, Qt, QTime
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from smellyfish.art import sprite
from smellyfish.features import calendar as calmod
from smellyfish.features.calendar import as_dt, fmt, parse
from smellyfish.ui import theme

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOUR_H = 44
TIME_W = 52
PAGE = sprite.Pose(
    ex=1,
    ey=-1,
    arm_f=("rest_l", "up_r"),
    parts=[(["RRRRRR", "WWWWWW", "WOWOWW", "WWWWWW", "WWOWOW", "WWWWWW"], sprite.BX + 16, sprite.BY)],
)


ICONS = {
    "clock": [".#####.", "#.....#", "#..#..#", "#..##.#", "#.....#", "#.....#", ".#####."],
    "pin": [".###.", "##.##", "#...#", "##.##", ".###.", "..#..", "..#.."],
}


def draw_icon(p, name, x, y, h, color):
    """A tiny pixel icon, vertically centred in a line of height h starting at y; returns its width."""
    rows = ICONS[name]
    top = y + (h - len(rows)) // 2
    c = QColor(color)
    for r, row in enumerate(rows):
        for col, ch in enumerate(row):
            if ch == "#":
                p.fillRect(x + col, top + r, 1, 1, c)
    return len(rows[0])


def swatch(color, selected):
    """A little color square for menus, with a frame around the chosen one."""
    from PySide6.QtGui import QIcon, QPixmap

    pix = QPixmap(18, 18)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.fillRect(2, 2, 14, 14, QColor(theme.LIGHT if selected else theme.DEEP))
    p.fillRect(4, 4, 10, 10, QColor(color))
    p.end()
    return QIcon(pix)


def qdate(d):
    return QDate(d.year, d.month, d.day)


def pydate(q):
    return dt.date(q.year(), q.month(), q.day())


def week_start(d):
    return d - dt.timedelta(days=d.weekday())


class Item:
    """One occurrence shown in a view."""

    def __init__(self, start, end, title, color, all_day, ev=None, cal=None, kind="event"):
        self.start, self.end, self.title, self.color = start, end, title, color
        self.all_day, self.ev, self.cal, self.kind = all_day, ev, cal, kind

    @property
    def place(self):
        return (self.ev or {}).get("location") or ""

    @property
    def label(self):
        text = self.title if self.all_day else f"{self.start:%H:%M} {self.title}"
        return f"{text} @ {self.place}" if self.place else text


def items_between(app, lo, hi):
    out = []
    for start, end, ev, cal in app.calendars.between(lo, hi):
        out.append(Item(start, end, ev["title"], cal["color"], ev.get("all_day"), ev, cal))
    if app.cfg.get("calendar_show_todos", True):
        for t in app.todos.open_items():
            if t.get("due"):
                s = dt.datetime.fromtimestamp(t["due"])
                if lo <= s < hi:
                    out.append(
                        Item(s, s + dt.timedelta(minutes=30), "To-do: " + t["text"], theme.WARN, False, kind="todo")
                    )
        for r in app.cfg.get("reminders") or []:
            s = dt.datetime.fromtimestamp(r["due"])
            if lo <= s < hi:
                out.append(
                    Item(s, s + dt.timedelta(minutes=30), "Reminder: " + r["text"], theme.WARN, False, kind="reminder")
                )
    out.sort(key=lambda i: (not i.all_day, i.start, i.title.lower()))
    return out


def _chip(p, rect, item, font_px=11, block=False):
    color = QColor(item.color)
    if item.kind != "event":
        p.setPen(QPen(color, 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect.adjusted(1, 1, -1, -1))
    else:
        bg = QColor(color)
        bg.setAlpha(70 if theme.IS_DARK else 90)
        p.fillRect(rect, bg)
        p.fillRect(QRect(rect.left(), rect.top(), 3, rect.height()), color)
    f = p.font()
    f.setPixelSize(font_px)
    p.setFont(f)
    inner = rect.adjusted(6, 1, -3, -1)
    elide = lambda text: p.fontMetrics().elidedText(text, Qt.ElideRight, max(10, inner.width()))
    if block:
        p.setPen(QColor(theme.TEXT))
        line = p.fontMetrics().height()
        short = inner.height() < 2 * line
        title = f"{item.title} @ {item.place}" if short and item.place else item.title
        p.drawText(
            QRect(inner.left(), inner.top(), inner.width(), line), Qt.AlignLeft | Qt.TextSingleLine, elide(title)
        )
        if short:
            return
        extra = [] if item.all_day else [("clock", f"{item.start:%H:%M} - {item.end:%H:%M}")]
        if item.place:
            extra.append(("pin", item.place))
        for n, (icon, text) in enumerate(extra, 1):
            if inner.height() >= (n + 1) * line:
                y = inner.top() + n * line
                w = draw_icon(p, icon, inner.left(), y, line, theme.MUTED) + 4
                p.setPen(QColor(theme.MUTED))
                shown = p.fontMetrics().elidedText(text, Qt.ElideRight, max(10, inner.width() - w))
                p.drawText(QRect(inner.left() + w, y, inner.width() - w, line), Qt.AlignLeft | Qt.TextSingleLine, shown)
        return
    p.setPen(QColor(theme.TEXT))
    p.drawText(inner, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextSingleLine, elide(item.label))


# ---------------------------------------------------------------- month view
class MonthView(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setMouseTracking(True)
        self.hits, self.day_rects = [], []
        self.setMinimumSize(380, 360)

    def first_day(self):
        d = self.win.day.replace(day=1)
        return week_start(d)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.FIELD))
        first = self.first_day()
        lo = dt.datetime.combine(first, dt.time())
        items = items_between(self.win.app, lo, lo + dt.timedelta(days=42))
        head = 22
        cw, ch = self.width() / 7, (self.height() - head) / 6
        f = QFont(p.font())
        f.setPixelSize(11)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        for i, name in enumerate(DAYS):
            p.drawText(QRect(round(i * cw), 0, round(cw), head), Qt.AlignCenter, name)
        self.hits, self.day_rects = [], []
        today = dt.date.today()
        per_day = {}
        for it in items:
            d0 = it.start.date()
            last = (it.end - dt.timedelta(seconds=1)).date() if it.end > it.start else d0
            d = max(d0, first)
            while d <= last and d < first + dt.timedelta(days=42):
                per_day.setdefault(d, []).append(it)
                d += dt.timedelta(days=1)
        for k in range(42):
            d = first + dt.timedelta(days=k)
            r = QRect(round((k % 7) * cw), round(head + (k // 7) * ch), round(cw), round(ch))
            self.day_rects.append((r, d))
            weekend = d.weekday() >= 5
            if d.month != self.win.day.month:
                p.fillRect(r, QColor(theme.BG))
            elif weekend:
                bg = QColor(theme.PANEL)
                p.fillRect(r, bg)
            p.setPen(QPen(QColor(theme.DEEP), 1))
            p.drawRect(r.adjusted(0, 0, -1, -1))
            num = QRect(r.left() + 4, r.top() + 3, 26, 17)
            f.setBold(True)
            f.setPixelSize(13)
            p.setFont(f)
            if d == today:
                p.fillRect(num.adjusted(-1, -1, 1, 1), QColor(theme.LAV))
                p.setPen(QColor(theme.INK))
            elif d == self.win.day:
                p.setPen(QPen(QColor(theme.LAV), 2))
                p.drawRect(r.adjusted(1, 1, -2, -2))
                p.setPen(QColor(theme.HEAD))
            else:
                p.setPen(QColor(theme.MUTED if d.month != self.win.day.month else theme.TEXT))
            p.drawText(num, Qt.AlignCenter, str(d.day))
            day_items = per_day.get(d, [])
            y = r.top() + 22
            room = max(0, int((r.bottom() - y - 2) // 17))
            shown = day_items if len(day_items) <= room else day_items[: max(0, room - 1)]
            for it in shown:
                rect = QRect(r.left() + 3, y, r.width() - 6, 15)
                _chip(p, rect, it)
                self.hits.append((rect, it))
                y += 17
            if len(shown) < len(day_items):
                p.setPen(QColor(theme.MUTED))
                f.setBold(False)
                f.setPixelSize(11)
                p.setFont(f)
                more = QRect(r.left() + 6, y, r.width() - 8, 15)
                p.drawText(more, Qt.AlignVCenter | Qt.AlignLeft, f"+{len(day_items) - len(shown)} more")
                self.hits.append((more, ("more", d)))
        p.end()

    def item_at(self, pos):
        return next((it for rect, it in self.hits if rect.contains(pos)), None)

    def day_at(self, pos):
        return next((d for rect, d in self.day_rects if rect.contains(pos)), None)

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        it = self.item_at(pos)
        if isinstance(it, tuple):
            self.win.show_week(it[1])
        elif it is not None:
            self.win.open_item(it)
        else:
            d = self.day_at(pos)
            if d is not None:
                self.win.day = d
                self.win.refresh()

    def mouseDoubleClickEvent(self, e):
        pos = e.position().toPoint()
        d = self.day_at(pos)
        if d is not None and self.item_at(pos) is None:
            self.win.new_event(dt.datetime.combine(d, dt.time(9, 0)))

    def mouseMoveEvent(self, e):
        it = self.item_at(e.position().toPoint())
        self.setCursor(Qt.PointingHandCursor if it is not None else Qt.ArrowCursor)
        self.setToolTip(self.win.tooltip(it) if isinstance(it, Item) else "")


# ---------------------------------------------------------------- week view
class WeekGrid(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.hits = []
        self.setMouseTracking(True)
        self.setMinimumHeight(24 * HOUR_H + 2)

    def sizeHint(self):
        return QSize(600, 24 * HOUR_H + 2)

    def col_w(self):
        return (self.width() - TIME_W) / self.win.span_days()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.FIELD))
        start = self.win.span_start()
        lo = dt.datetime.combine(start, dt.time())
        items = [
            i for i in items_between(self.win.app, lo, lo + dt.timedelta(days=self.win.span_days())) if not i.all_day
        ]
        cw = self.col_w()
        f = QFont(p.font())
        f.setPixelSize(11)
        p.setFont(f)
        today = dt.date.today()
        for k in range(self.win.span_days()):
            d = start + dt.timedelta(days=k)
            x = round(TIME_W + k * cw)
            if d.weekday() >= 5:
                p.fillRect(QRect(x, 0, round(cw), self.height()), QColor(theme.PANEL))
            if d == today:
                hl = QColor(theme.LAV)
                hl.setAlpha(28)
                p.fillRect(QRect(x, 0, round(cw), self.height()), hl)
        for h in range(25):
            y = h * HOUR_H
            p.setPen(QPen(QColor(theme.DEEP), 1))
            p.drawLine(TIME_W, y, self.width(), y)
            if h < 24:
                p.setPen(QColor(theme.MUTED))
                p.drawText(QRect(0, y + 2, TIME_W - 6, 14), Qt.AlignRight | Qt.AlignTop, f"{h:02d}:00")
        for k in range(self.win.span_days() + 1):
            x = round(TIME_W + k * cw)
            p.setPen(QPen(QColor(theme.DEEP), 1))
            p.drawLine(x, 0, x, self.height())
        self.hits = []
        for k in range(self.win.span_days()):
            d = start + dt.timedelta(days=k)
            day_lo = dt.datetime.combine(d, dt.time())
            day_hi = day_lo + dt.timedelta(days=1)
            todays = [i for i in items if i.start < day_hi and max(i.end, i.start + dt.timedelta(minutes=20)) > day_lo]
            for it, col, cols in self._columns(todays, day_lo, day_hi):
                s = max(it.start, day_lo)
                e = min(max(it.end, it.start + dt.timedelta(minutes=20)), day_hi)
                y0 = (s - day_lo).total_seconds() / 3600 * HOUR_H
                y1 = (e - day_lo).total_seconds() / 3600 * HOUR_H
                w = (cw - 4) / cols
                rect = QRect(
                    round(TIME_W + k * cw + 2 + col * w),
                    round(y0) + 1,
                    max(8, round(w) - 2),
                    max(15, round(y1 - y0) - 2),
                )
                _chip(p, rect, it, block=True)
                self.hits.append((rect, it))
        now = dt.datetime.now()
        if start <= now.date() < start + dt.timedelta(days=self.win.span_days()):
            k = (now.date() - start).days
            y = round((now - dt.datetime.combine(now.date(), dt.time())).total_seconds() / 3600 * HOUR_H)
            p.setPen(QPen(QColor(theme.BAD), 2))
            p.drawLine(round(TIME_W + k * cw), y, round(TIME_W + (k + 1) * cw), y)
        p.end()

    @staticmethod
    def _columns(items, lo, hi):
        """Overlapping events side by side: [(item, column, number of columns in its group)]."""
        out, group, ends = [], [], []

        def flush():
            n = max((c for _i, c in group), default=-1) + 1
            out.extend((i, c, n) for i, c in group)

        for it in sorted(items, key=lambda i: i.start):
            end = max(it.end, it.start + dt.timedelta(minutes=20))
            if group and it.start >= max(ends):
                flush()
                group, ends = [], []
            free = [c for c in range(len(ends)) if ends[c] <= it.start]
            col = free[0] if free else len(ends)
            if col == len(ends):
                ends.append(end)
            else:
                ends[col] = end
            group.append((it, col))
        if group:
            flush()
        return out

    def item_at(self, pos):
        return next((it for rect, it in reversed(self.hits) if rect.contains(pos)), None)

    def time_at(self, pos):
        if pos.x() < TIME_W:
            return None
        k = int((pos.x() - TIME_W) // self.col_w())
        mins = int(pos.y() / HOUR_H * 60) // 30 * 30
        d = self.win.span_start() + dt.timedelta(days=max(0, min(self.win.span_days() - 1, k)))
        return dt.datetime.combine(d, dt.time()) + dt.timedelta(minutes=max(0, min(23 * 60 + 30, mins)))

    def mousePressEvent(self, e):
        it = self.item_at(e.position().toPoint())
        if it is not None:
            self.win.open_item(it)

    def mouseDoubleClickEvent(self, e):
        pos = e.position().toPoint()
        if self.item_at(pos) is None and self.time_at(pos) is not None:
            self.win.new_event(self.time_at(pos))

    def mouseMoveEvent(self, e):
        it = self.item_at(e.position().toPoint())
        self.setCursor(Qt.PointingHandCursor if it is not None else Qt.ArrowCursor)
        self.setToolTip(self.win.tooltip(it) if it is not None else "")


class WeekHeader(QWidget):
    """Day names and the all-day lane above the scrolling week grid."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.hits = []
        self.setMouseTracking(True)

    def lanes(self):
        start = self.win.span_start()
        lo = dt.datetime.combine(start, dt.time())
        items = [i for i in items_between(self.win.app, lo, lo + dt.timedelta(days=self.win.span_days())) if i.all_day]
        rows = []
        for it in items:
            for row in rows:
                if all(it.start >= o.end or it.end <= o.start for o in row):
                    row.append(it)
                    break
            else:
                rows.append([it])
        return rows

    def sizeHint(self):
        return QSize(600, 26 + 18 * min(4, len(self.lanes())) + 4)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        start = self.win.span_start()
        cw = (self.width() - TIME_W - 14) / self.win.span_days()
        f = QFont(p.font())
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        today = dt.date.today()
        for k in range(self.win.span_days()):
            d = start + dt.timedelta(days=k)
            r = QRect(round(TIME_W + k * cw), 0, round(cw), 24)
            if d == today:
                p.fillRect(r.adjusted(2, 2, -2, -2), QColor(theme.LAV))
                p.setPen(QColor(theme.INK))
            else:
                p.setPen(QColor(theme.TEXT if d.weekday() < 5 else theme.MUTED))
            p.drawText(
                r,
                Qt.AlignCenter,
                f"{DAYS[d.weekday()]} {d.day}.{d.month}." if self.win.span_days() > 1 else d.strftime("%A, %d %B %Y"),
            )
        p.setPen(QColor(theme.MUTED))
        f.setBold(False)
        f.setPixelSize(10)
        p.setFont(f)
        p.drawText(QRect(0, 26, TIME_W - 6, 16), Qt.AlignRight | Qt.AlignVCenter, "all day")
        self.hits = []
        for n, row in enumerate(self.lanes()[:4]):
            for it in row:
                a = max(0, (it.start.date() - start).days)
                b = min(self.win.span_days(), (max(it.end - dt.timedelta(seconds=1), it.start).date() - start).days + 1)
                rect = QRect(round(TIME_W + a * cw) + 2, 26 + n * 18, max(10, round((b - a) * cw) - 4), 16)
                _chip(p, rect, it)
                self.hits.append((rect, it))
        p.end()

    def mousePressEvent(self, e):
        it = next((it for rect, it in self.hits if rect.contains(e.position().toPoint())), None)
        if it is not None:
            self.win.open_item(it)

    def mouseMoveEvent(self, e):
        it = next((it for rect, it in self.hits if rect.contains(e.position().toPoint())), None)
        self.setCursor(Qt.PointingHandCursor if it is not None else Qt.ArrowCursor)
        self.setToolTip(self.win.tooltip(it) if it is not None else "")


class WeekView(QWidget):
    def __init__(self, win):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.header = WeekHeader(win)
        self.grid = WeekGrid(win)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.grid)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self.header)
        lay.addWidget(self.scroll, 1)
        self.scrolled = False

    def refresh(self):
        self.header.updateGeometry()
        self.header.setFixedHeight(self.header.sizeHint().height())
        self.header.update()
        self.grid.update()
        if not self.scrolled:
            self.scrolled = True
            self.scroll.verticalScrollBar().setValue(7 * HOUR_H)


# ---------------------------------------------------------------- event editor
class EventDialog(QDialog):
    REPEATS = [
        ("Does not repeat", ""),
        ("Every day", "DAILY"),
        ("Every week", "WEEKLY"),
        ("Every month", "MONTHLY"),
        ("Every year", "YEARLY"),
    ]

    def __init__(self, win, ev=None, cal=None, start=None, occurrence=None):
        super().__init__(win)
        self.win, self.app = win, win.app
        self.ev, self.occurrence = ev, occurrence
        self.readonly = cal is not None and cal["kind"] == "sub"
        self.deleted = False
        self.setWindowTitle("Smellyfish - " + ("Event" if self.readonly else "Edit event" if ev else "New event"))
        theme.apply(self, self.app)
        self.setMinimumWidth(460)
        form = QFormLayout()
        form.setSpacing(8)
        self.title = QLineEdit(ev["title"] if ev else "")
        self.title.setPlaceholderText("What is happening?")
        self.title.setMaxLength(200)
        form.addRow("Title", self.title)
        self.cal = QComboBox()
        cals = [cal] if self.readonly else self.app.calendars.editable()
        for c in cals:
            self.cal.addItem(c["name"], c["id"])
        if cal is not None:
            self.cal.setCurrentIndex(max(0, self.cal.findData(cal["id"])))
        form.addRow("Calendar", self.cal)

        if ev:
            s, e = parse(ev["start"]), parse(ev["end"])
            if not isinstance(s, dt.datetime):
                e = e - dt.timedelta(days=1) if e > s else e
        else:
            s = start or dt.datetime.now().replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
            e = s + dt.timedelta(hours=1)
        self.all_day = QCheckBox("All day")
        self.all_day.setChecked(not isinstance(s, dt.datetime))
        form.addRow("", self.all_day)
        self.sd, self.st = QDateEdit(qdate(s)), QTimeEdit(QTime(as_dt(s).hour, as_dt(s).minute))
        self.ed, self.et = QDateEdit(qdate(e)), QTimeEdit(QTime(as_dt(e).hour, as_dt(e).minute))
        for w in (self.sd, self.ed):
            w.setCalendarPopup(True)
            w.setDisplayFormat("ddd dd.MM.yyyy")
        for w in (self.st, self.et):
            w.setDisplayFormat("HH:mm")
            w.setButtonSymbols(QAbstractSpinBox.NoButtons)
            w.setFixedWidth(80)
        row = QHBoxLayout()
        row.addWidget(self.sd, 1)
        row.addWidget(self.st)
        form.addRow("Starts", row)
        row = QHBoxLayout()
        row.addWidget(self.ed, 1)
        row.addWidget(self.et)
        form.addRow("Ends", row)
        self.sd.dateChanged.connect(self.start_moved)
        self.all_day.toggled.connect(self.sync_times)

        self.loc = QLineEdit(ev.get("location", "") if ev else "")
        form.addRow("Where", self.loc)
        self.notes = QPlainTextEdit(ev.get("notes", "") if ev else "")
        self.notes.setFixedHeight(70)
        form.addRow("Notes", self.notes)
        self.remind = QComboBox()
        for label, mins in calmod.REMIND:
            self.remind.addItem(label, mins)
        want = ev.get("remind") if ev else self.app.cfg.get("calendar_remind_min", 10)
        idx = self.remind.findData(want)
        if idx < 0 and want is not None:
            self.remind.addItem(f"{want} min before", want)
            idx = self.remind.count() - 1
        self.remind.setCurrentIndex(max(0, idx))
        form.addRow("Remind me", self.remind)

        self.rule = ev.get("rrule", "") if ev else ""
        simple = calmod.describe_rule(self.rule)
        self.repeat = QComboBox()
        for label, freq in self.REPEATS:
            self.repeat.addItem(label, freq)
        self.every = QSpinBox()
        self.every.setRange(1, 99)
        self.every.setPrefix("every ")
        self.until_on = QCheckBox("until")
        self.until = QDateEdit(qdate(s + dt.timedelta(days=90) if isinstance(s, dt.date) else s))
        self.until.setCalendarPopup(True)
        self.until.setDisplayFormat("dd.MM.yyyy")
        if simple is None:
            self.repeat.addItem("Custom repeat (from the import)", "custom")
            self.repeat.setCurrentIndex(self.repeat.count() - 1)
        else:
            freq, every, until = simple
            self.repeat.setCurrentIndex(max(0, self.repeat.findData(freq)))
            self.every.setValue(every)
            if until:
                self.until_on.setChecked(True)
                self.until.setDate(qdate(until))
        row = QHBoxLayout()
        row.addWidget(self.repeat, 1)
        row.addWidget(self.every)
        row.addWidget(self.until_on)
        row.addWidget(self.until)
        form.addRow("Repeat", row)
        self.repeat.currentIndexChanged.connect(self.sync_repeat)
        self.until_on.toggled.connect(self.sync_repeat)

        buttons = QHBoxLayout()
        if ev and not self.readonly:
            delete = QPushButton("Delete")
            delete.setObjectName("secondary")
            delete.clicked.connect(self.delete)
            buttons.addWidget(delete)
        buttons.addStretch(1)
        cancel = QPushButton("Close" if self.readonly else "Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        if not self.readonly:
            save = QPushButton("Save")
            save.setDefault(True)
            save.clicked.connect(self.save)
            buttons.addWidget(save)
        root = QVBoxLayout(self)
        root.addLayout(form)
        if self.readonly:
            note = QLabel("This event comes from a subscribed calendar and can only be changed at its source.")
            note.setObjectName("hint")
            note.setWordWrap(True)
            root.addWidget(note)
            for w in (
                self.title,
                self.cal,
                self.all_day,
                self.sd,
                self.st,
                self.ed,
                self.et,
                self.loc,
                self.repeat,
                self.every,
                self.until_on,
                self.until,
            ):
                w.setEnabled(False)
            self.notes.setReadOnly(True)
            self.remind.setEnabled(False)
        root.addLayout(buttons)
        self.sync_times()
        self.sync_repeat()
        self._span = as_dt(self.end_value()) - as_dt(self.start_value())

    def sync_times(self):
        timed = not self.all_day.isChecked()
        self.st.setVisible(timed)
        self.et.setVisible(timed)

    def sync_repeat(self):
        on = self.repeat.currentData() not in ("", "custom")
        for w in (self.every, self.until_on):
            w.setVisible(on)
        self.until.setVisible(on and self.until_on.isChecked())

    def start_value(self):
        d = pydate(self.sd.date())
        if self.all_day.isChecked():
            return d
        t = self.st.time()
        return dt.datetime.combine(d, dt.time(t.hour(), t.minute()))

    def end_value(self):
        d = pydate(self.ed.date())
        if self.all_day.isChecked():
            return d
        t = self.et.time()
        return dt.datetime.combine(d, dt.time(t.hour(), t.minute()))

    def start_moved(self, _q):
        span = getattr(self, "_span", None)
        if span is None:
            return
        end = as_dt(self.start_value()) + span
        self.ed.setDate(qdate(end))

    def save(self):
        title = " ".join(self.title.text().split())
        if not title:
            self.title.setFocus()
            return
        start, end = self.start_value(), self.end_value()
        if self.all_day.isChecked():
            end = end + dt.timedelta(days=1)
        if as_dt(end) < as_dt(start):
            QMessageBox.warning(self, "Smellyfish", "The event ends before it starts.")
            return
        freq = self.repeat.currentData()
        if freq == "custom":
            rule = self.rule
        else:
            until = pydate(self.until.date()) if self.until_on.isChecked() else None
            rule = calmod.simple_rule(freq, self.every.value(), until)
        ev = dict(
            self.ev or {},
            uid=(self.ev or {}).get("uid") or uuid.uuid4().hex,
            title=title,
            start=fmt(start),
            end=fmt(end),
            all_day=self.all_day.isChecked(),
            location=self.loc.text().strip(),
            notes=self.notes.toPlainText().strip()[:4000],
            remind=self.remind.currentData(),
            rrule=rule,
        )
        if rule != (self.ev or {}).get("rrule", "") or not rule:
            ev["exdates"] = [] if not rule else ev.get("exdates", [])
        self.app.calendars.save_event(self.cal.currentData(), ev)
        self.accept()

    def delete(self):
        only = None
        if self.ev.get("rrule") and self.occurrence is not None:
            box = QMessageBox(self)
            box.setWindowTitle("Smellyfish")
            box.setText("This event repeats. Delete only this one or all of them?")
            one = box.addButton("Only this one", QMessageBox.AcceptRole)
            box.addButton("All", QMessageBox.DestructiveRole)
            cancel = box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is cancel:
                return
            if box.clickedButton() is one:
                only = fmt(self.occurrence)
        self.app.calendars.delete_event(self.ev["uid"], only)
        self.deleted = True
        self.accept()


# ---------------------------------------------------------------- the window
class CalendarWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.day = dt.date.today()
        self.setWindowTitle("Smellyfish - Calendar")
        theme.apply(self, app)
        theme.listen(self.update_views)
        self.resize(980, 700)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        root.addWidget(theme.banner("Calendar", "Appointments, birthdays, deadlines", PAGE))

        bar = theme.FlowLayout()
        bar.setContentsMargins(14, 0, 14, 0)
        prev, nxt = QPushButton("<"), QPushButton(">")
        today = QPushButton("Today")
        for b in (prev, nxt, today):
            b.setObjectName("secondary")
        prev.clicked.connect(lambda: self.step(-1))
        nxt.clicked.connect(lambda: self.step(1))
        today.clicked.connect(self.go_today)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.month_btn, self.week_btn, self.day_btn = QPushButton("Month"), QPushButton("Week"), QPushButton("Day")
        for b, view in ((self.month_btn, "month"), (self.week_btn, "week"), (self.day_btn, "day")):
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, v=view: self.set_view(v))
        new = QPushButton("New event")
        new.clicked.connect(lambda: self.new_event(None))
        self.side_btn = QPushButton()
        self.side_btn.setObjectName("secondary")
        self.side_btn.setCheckable(True)
        self.side_btn.toggled.connect(self.toggle_side)
        bar.addWidget(self.side_btn)
        bar.addWidget(prev)
        bar.addWidget(today)
        bar.addWidget(nxt)
        bar.addWidget(self.title)
        bar.add_stretch()
        bar.addWidget(self.month_btn)
        bar.addWidget(self.week_btn)
        bar.addWidget(self.day_btn)
        bar.addWidget(new)
        root.addLayout(bar)

        body = QHBoxLayout()
        body.setContentsMargins(14, 0, 14, 0)
        body.setSpacing(10)
        self.side = QWidget()
        self.side.setFixedWidth(220)
        side = QVBoxLayout(self.side)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(6)
        head = QLabel("Calendars")
        head.setObjectName("title")
        side.addWidget(head)
        self.cals = QListWidget()
        self.cals.setFixedWidth(220)
        self.cals.itemChanged.connect(self.toggle_cal)
        self.cals.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cals.customContextMenuRequested.connect(self.cal_menu)
        self.cals.itemDoubleClicked.connect(lambda it: self.rename_cal(it.data(Qt.UserRole)))
        side.addWidget(self.cals, 1)
        self.todos_box = QCheckBox("Show to-dos and reminders")
        self.todos_box.setChecked(bool(app.cfg.get("calendar_show_todos", True)))
        self.todos_box.toggled.connect(lambda on: (app.cfg.set("calendar_show_todos", on), self.update_views()))
        side.addWidget(self.todos_box)
        for label, fn in (
            ("New calendar...", self.new_calendar),
            ("Import .ics file...", self.import_file),
            ("Subscribe to a link...", self.subscribe),
        ):
            b = QPushButton(label)
            b.setObjectName("secondary")
            b.clicked.connect(fn)
            side.addWidget(b)
        exp = QPushButton("Export...")
        exp.setObjectName("secondary")
        self.exp_menu = QMenu(exp)
        self.exp_menu.aboutToShow.connect(self.fill_export)
        exp.setMenu(self.exp_menu)
        exp.setProperty("menu", "1")
        side.addWidget(exp)
        hint = QLabel(
            "Right-click a calendar to rename, recolor, refresh or remove it. Removing a calendar only "
            "removes its own events."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setFixedWidth(220)
        side.addWidget(hint)
        body.addWidget(self.side)

        self.stack = QStackedWidget()
        self.month = MonthView(self)
        self.week = WeekView(self)
        self.stack.addWidget(self.month)
        self.stack.addWidget(self.week)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        open_side = bool(app.cfg.get("calendar_sidebar"))
        self.side_btn.setChecked(open_side)
        self.toggle_side(open_side, save=False)
        self.set_view(app.cfg.get("calendar_view") or "month", save=False)

    def toggle_side(self, on, save=True):
        self.side.setVisible(on)
        self.side_btn.setText("< Calendars" if on else "Calendars >")
        if save:
            self.app.cfg.set("calendar_sidebar", bool(on))

    # navigation
    def span_days(self):
        return 1 if self.view == "day" else 7

    def span_start(self):
        return self.day if self.view == "day" else week_start(self.day)

    def set_view(self, view, save=True):
        self.view = view if view in ("week", "day") else "month"
        self.stack.setCurrentWidget(self.month if self.view == "month" else self.week)
        for b, name in ((self.month_btn, "month"), (self.week_btn, "week"), (self.day_btn, "day")):
            b.setChecked(self.view == name)
            b.setObjectName("primary" if self.view == name else "secondary")
            b.style().unpolish(b)
            b.style().polish(b)
        if save:
            self.app.cfg.set("calendar_view", self.view)
        self.refresh()

    def step(self, n):
        if self.view in ("week", "day"):
            self.day += dt.timedelta(days=self.span_days() * n)
        else:
            m = self.day.month - 1 + n
            y = self.day.year + m // 12
            self.day = dt.date(y, m % 12 + 1, 1)
        self.refresh()

    def go_today(self):
        self.day = dt.date.today()
        self.refresh()

    def show_week(self, d):
        self.day = d
        self.set_view("day")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        elif e.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.step(-1)
        elif e.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self.step(1)
        else:
            super().keyPressEvent(e)

    def refresh(self):
        if self.view == "day":
            self.title.setText(self.day.strftime("%A, %d.%m.%Y"))
        elif self.view == "week":
            ws = week_start(self.day)
            we = ws + dt.timedelta(days=6)
            self.title.setText(f"{ws:%d.%m.} - {we:%d.%m.%Y}  (week {ws.isocalendar()[1]})")
        else:
            self.title.setText(self.day.strftime("%B %Y"))
        self.fill_cals()
        self.update_views()

    def update_views(self):
        self.month.update()
        self.week.refresh()

    # calendar list
    def fill_cals(self):
        self.cals.blockSignals(True)
        self.cals.clear()
        for c in self.app.calendars.meta:
            label = c["name"]
            if c["kind"] == "sub":
                label += "  (link)"
                if c.get("error"):
                    label += "  !"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, c["id"])
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if c.get("visible", True) else Qt.Unchecked)
            it.setForeground(QColor(c["color"]))
            tip = {
                "local": "Your default calendar",
                "own": "Your own calendar, you can add events to it",
                "import": "Imported from a file, editable",
                "sub": "Subscribed link, refreshed every hour, read-only",
            }[c["kind"]]
            if c.get("error"):
                tip += f"\nLast refresh failed: {c['error']}"
            it.setToolTip(tip)
            self.cals.addItem(it)
        self.cals.blockSignals(False)

    def toggle_cal(self, it):
        self.app.calendars.update(it.data(Qt.UserRole), visible=it.checkState() == Qt.Checked)
        self.app.calendar_changed()

    def cal_menu(self, pos):
        it = self.cals.itemAt(pos)
        if it is None:
            return
        cid = it.data(Qt.UserRole)
        cal = self.app.calendars.get(cid)
        m = QMenu(self)
        m.addAction("Rename...", lambda: self.rename_cal(cid))
        colors = m.addMenu("Color")
        for c, name in calmod.COLOR_NAMES:
            a = colors.addAction(swatch(c, c == cal["color"]), name)
            a.triggered.connect(lambda _c=False, col=c: self.set_color(cid, col))
        colors.addSeparator()
        colors.addAction(swatch(cal["color"], False), "Other color...", lambda: self.pick_color(cid))
        if cal["kind"] == "sub":
            m.addAction("Refresh now", lambda: self.app.calendars.fetch(cid))
            m.addAction("Change link...", lambda: self.change_link(cid))
        m.addAction("Export as .ics...", lambda: self.export([cid]))
        if cal["kind"] != "local":
            m.addSeparator()
            m.addAction("Remove this calendar...", lambda: self.remove_cal(cid))
        m.exec(self.cals.viewport().mapToGlobal(pos))

    def set_color(self, cid, color):
        self.app.calendars.update(cid, color=color)
        self.app.calendar_changed()

    def pick_color(self, cid):
        from PySide6.QtWidgets import QColorDialog

        c = QColorDialog.getColor(QColor(self.app.calendars.get(cid)["color"]), self, "Calendar color")
        if c.isValid():
            self.set_color(cid, c.name())

    def rename_cal(self, cid):
        cal = self.app.calendars.get(cid)
        name, ok = QInputDialog.getText(self, "Smellyfish - Rename calendar", "Name:", text=cal["name"])
        if ok and name.strip():
            self.app.calendars.update(cid, name=name.strip()[:60])
            self.app.calendar_changed()

    def remove_cal(self, cid):
        cal = self.app.calendars.get(cid)
        n = len(self.app.calendars.events.get(cid, []))
        ok = QMessageBox.question(
            self, "Smellyfish", f'Remove "{cal["name"]}" and its {n} events? Your other calendars stay as they are.'
        )
        if ok == QMessageBox.Yes:
            self.app.calendars.remove(cid)
            self.app.calendar_changed()

    def new_calendar(self):
        name, ok = QInputDialog.getText(self, "Smellyfish - New calendar", "Name (for example Birthdays or Work):")
        if not ok or not name.strip():
            return
        self.app.calendars.add(name.strip(), "own")
        self.app.calendar_changed()

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import a calendar", "", "Calendar (*.ics *.ical);;All files (*)")
        if not path:
            return
        try:
            cal = self.app.calendars.import_file(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Smellyfish", f"Could not import that file:\n{e}")
            return
        n = len(self.app.calendars.events[cal["id"]])
        QMessageBox.information(self, "Smellyfish", f'Imported {n} events into "{cal["name"]}".')
        self.app.calendar_changed()

    def subscribe(self):
        url, ok = QInputDialog.getText(
            self,
            "Smellyfish - Subscribe",
            "Calendar link (ends in .ics, webcal:// works too).\nIt is downloaded every hour; nothing else is sent:",
        )
        url = url.strip()
        if not ok or not url:
            return
        if not url.lower().startswith(("https://", "http://", "webcal://")):
            QMessageBox.warning(self, "Smellyfish", "The link has to start with https://, http:// or webcal://")
            return
        cal = self.app.calendars.add("Subscription", "sub", url=url)
        self.app.calendars.fetch(cal["id"])
        self.app.calendar_changed()

    def change_link(self, cid):
        cal = self.app.calendars.get(cid)
        url, ok = QInputDialog.getText(self, "Smellyfish - Calendar link", "Link:", text=cal.get("url", ""))
        if ok and url.strip():
            self.app.calendars.update(cid, url=url.strip(), fetched=0, error="")
            self.app.calendars.fetch(cid)
            self.app.calendar_changed()

    def fill_export(self):
        self.exp_menu.clear()
        self.exp_menu.addAction(
            "All calendars in one file...", lambda: self.export([c["id"] for c in self.app.calendars.meta])
        )
        self.exp_menu.addSeparator()
        for c in self.app.calendars.meta:
            self.exp_menu.addAction(
                c["name"].replace("&", "&&") + "...", lambda _c=False, cid=c["id"]: self.export([cid])
            )

    def export(self, cids):
        name = self.app.calendars.get(cids[0])["name"] if len(cids) == 1 else "smellyfish-calendars"
        safe = "".join(ch for ch in name if ch.isalnum() or ch in " -_").strip() or "calendar"
        path, _ = QFileDialog.getSaveFileName(self, "Export calendar", f"{safe}.ics", "Calendar (*.ics)")
        if not path:
            return
        try:
            self.app.calendars.export(cids, path)
        except OSError as e:
            QMessageBox.warning(self, "Smellyfish", f"Could not save the file:\n{e}")

    # events
    def tooltip(self, it):
        if it is None:
            return ""
        if it.all_day:
            when = f"{it.start:%a %d.%m.}"
            if (it.end - it.start).days > 1:
                when += f" - {(it.end - dt.timedelta(days=1)):%a %d.%m.}"
        else:
            when = f"{it.start:%a %d.%m. %H:%M} - {it.end:%H:%M}"
        lines = [it.title, when]
        if it.ev and it.ev.get("location"):
            lines.append(it.ev["location"])
        if it.cal:
            lines.append(it.cal["name"])
        return "\n".join(lines)

    def open_item(self, it):
        if it.kind == "todo":
            return self.app.open_todos()
        if it.kind == "reminder":
            return
        occurrence = it.start if not it.all_day else it.start.date()
        dlg = EventDialog(self, it.ev, it.cal, occurrence=occurrence)
        if dlg.exec():
            self.app.calendar_changed()

    def new_event(self, start):
        if start is None:
            base = self.day if self.day != dt.date.today() else None
            if base is not None:
                start = dt.datetime.combine(base, dt.time(9, 0))
        dlg = EventDialog(self, None, self.app.calendars.local(), start=start)
        if dlg.exec():
            self.app.calendar_changed()
